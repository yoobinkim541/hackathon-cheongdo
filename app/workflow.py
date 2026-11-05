"""MAF workflow: executors and the graph for one consultation run."""

from __future__ import annotations

from agent_framework import (
    Case,
    Default,
    Executor,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)

from app import config, ingest, masking, prompts, render, rules, verify
from app.agents import call_agent
from app.runs import RunState, now_iso
from app.schemas import (
    DOMAINS,
    MATCH_STEP,
    SECTION_IDS,
    SECTION_TITLES,
    ApprovalDecision,
    ApprovalRequest,
    DraftDocuments,
    DraftReady,
    DraftSection,
    MaskedNote,
    MatchResult,
    ProfileReady,
    ProfileRequest,
    RunInput,
    TranscriptReady,
    UiEvent,
    VerifiedResult,
)


def _emitter(ctx: WorkflowContext):
    async def emit(event: UiEvent) -> None:
        await ctx.yield_output(event)

    return emit


async def _fatal(ctx: WorkflowContext, run: RunState, step: str, code: str, message: str) -> None:
    run.error_code = code
    await ctx.yield_output(UiEvent(type="error", step=step, data={"code": code, "message": message}))


class InputRouter(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="input_router")
        self.run = run

    @handler
    async def route(self, msg: RunInput, ctx: WorkflowContext[RunInput, UiEvent]) -> None:
        await ctx.send_message(msg)


class OcrExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="ocr")
        self.run = run

    @handler
    async def recognize(self, msg: RunInput, ctx: WorkflowContext[TranscriptReady, UiEvent]) -> None:
        run = self.run
        try:
            transcript = await ingest.ocr_image(run.media or b"")
        except ingest.IngestError as exc:
            await _fatal(ctx, run, self.id, "ai_unavailable", str(exc))
            return
        finally:
            run.media = None
        run.transcript_text = transcript.text
        run.transcript_uncertain = transcript.uncertain
        run.timings[self.id] = transcript.ms
        await ctx.yield_output(UiEvent(type="transcribed", step=self.id, data={
            "source": "image", "chars": len(transcript.text), "uncertain": transcript.uncertain[:50],
            "speakers": None, "ms": transcript.ms,
        }))
        await ctx.send_message(TranscriptReady(run_id=run.id, source="image", text=transcript.text))


class SttExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="stt")
        self.run = run

    @handler
    async def transcribe(self, msg: RunInput, ctx: WorkflowContext[TranscriptReady, UiEvent]) -> None:
        run = self.run
        try:
            transcript = await ingest.transcribe_audio(run.media or b"", run.media_format or "wav")
        except ingest.IngestError as exc:
            await _fatal(ctx, run, self.id, "ai_unavailable", str(exc))
            return
        finally:
            run.media = None
        run.transcript_text = transcript.text
        run.transcript_uncertain = transcript.uncertain
        run.timings[self.id] = transcript.ms
        await ctx.yield_output(UiEvent(type="transcribed", step=self.id, data={
            "source": "audio", "chars": len(transcript.text), "uncertain": transcript.uncertain[:50],
            "speakers": transcript.speakers, "ms": transcript.ms,
        }))
        await ctx.send_message(TranscriptReady(run_id=run.id, source="audio", text=transcript.text))


class IntakeExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="intake")
        self.run = run

    async def _mask(self, source: str, text: str, ctx: WorkflowContext[MaskedNote, UiEvent]) -> None:
        run = self.run
        result = masking.mask(text, source=source, known=run.pii_map, names=run.known_names)
        for span in result.spans:
            run.pii_map.setdefault(text[span.start:span.end], span.placeholder)
        run.mask_spans = [s.model_dump() for s in result.spans]
        await ctx.yield_output(UiEvent(type="masked", step=self.id, data={
            "before": text, "after": result.text,
            "spans": [{"kind": s.kind, "placeholder": s.placeholder} for s in result.spans],
        }))
        if result.residual:
            await _fatal(ctx, run, self.id, "pii_residual",
                         "가린 뒤에도 개인정보로 보이는 값이 남아 실행을 멈췄습니다. 메모를 확인해 주세요.")
            return
        run.masked_note = result.text
        await ctx.send_message(MaskedNote(run_id=run.id, source=source, text=result.text))

    @handler
    async def from_text(self, msg: RunInput, ctx: WorkflowContext[MaskedNote, UiEvent]) -> None:
        await self._mask("text", msg.text or "", ctx)

    @handler
    async def from_transcript(self, msg: TranscriptReady, ctx: WorkflowContext[MaskedNote, UiEvent]) -> None:
        await self._mask(msg.source, msg.text, ctx)


class NormalizerExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="normalizer")
        self.run = run

    @handler
    async def normalize(self, msg: MaskedNote, ctx: WorkflowContext[ProfileRequest, UiEvent]) -> None:
        run = self.run
        result = await call_agent(
            self.id, prompts.normalizer_prompt(msg.text, msg.source, run.transcript_uncertain), run,
            emit=_emitter(ctx), submitted=lambda: run.clean_note is not None,
        )
        if result.ok and run.clean_note is not None:
            remasked = masking.mask(run.clean_note.clean_text, source="text", known=run.pii_map, names=run.known_names)
            text = remasked.text
            await ctx.yield_output(UiEvent(type="normalized", step=self.id, data={
                "clean_text": text,
                "edits": [e.model_dump() for e in run.clean_note.edits],
                "uncertain": run.clean_note.uncertain,
                "skipped": False,
            }))
            await ctx.send_message(ProfileRequest(run_id=run.id, source=msg.source, text=text, normalized=True))
            return
        await ctx.yield_output(UiEvent(type="step_failed", step=self.id, data={
            "code": result.error_code or "other", "message": "메모 정리를 건너뛰고 인식 원문으로 진행합니다.",
        }))
        await ctx.yield_output(UiEvent(type="normalized", step=self.id, data={
            "clean_text": msg.text, "edits": [], "uncertain": run.transcript_uncertain, "skipped": True,
        }))
        await ctx.send_message(ProfileRequest(run_id=run.id, source=msg.source, text=msg.text, normalized=False))


class ProfilerExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="profiler")
        self.run = run

    async def _profile(self, text: str, ctx: WorkflowContext[ProfileReady, UiEvent]) -> None:
        run = self.run
        run.masked_note = text
        result = await call_agent(
            self.id, prompts.profiler_prompt(text), run,
            emit=_emitter(ctx), submitted=lambda: run.profile is not None,
        )
        if not result.ok or run.profile is None:
            await _fatal(ctx, run, self.id, result.error_code or "other", "가구 정보를 구조화하지 못했습니다.")
            return
        await ctx.yield_output(UiEvent(type="profile", step=self.id, data={"profile": run.profile.model_dump()}))
        await ctx.send_message(ProfileReady(run_id=run.id, profile=run.profile))

    @handler
    async def from_masked(self, msg: MaskedNote, ctx: WorkflowContext[ProfileReady, UiEvent]) -> None:
        await self._profile(msg.text, ctx)

    @handler
    async def from_normalized(self, msg: ProfileRequest, ctx: WorkflowContext[ProfileReady, UiEvent]) -> None:
        await self._profile(msg.text, ctx)


class MatchExecutor(Executor):
    def __init__(self, run: RunState, domain: str) -> None:
        super().__init__(id=MATCH_STEP[domain])
        self.run = run
        self.domain = domain

    @handler
    async def match(self, msg: ProfileReady, ctx: WorkflowContext[MatchResult, UiEvent]) -> None:
        run = self.run
        try:
            result = await call_agent(
                self.id, prompts.match_prompt(self.domain, msg.profile, run.masked_note or ""), run,
                emit=_emitter(ctx), submitted=lambda: self.domain in run.match_submissions,
            )
            ok, code = result.ok, result.error_code
        except Exception:  # noqa: BLE001 - a branch must always reach the fan-in
            ok, code = False, "other"
        submission = run.match_submissions.get(self.domain)
        if not ok:
            await ctx.yield_output(UiEvent(type="step_failed", step=self.id, data={
                "code": code or "other", "message": "이 분야는 규칙 판정만으로 채웁니다.",
            }))
        await ctx.send_message(MatchResult(
            domain=self.domain, status="ok" if ok and submission else "failed", error_code=code, submission=submission,
        ))


class VerifierExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="verifier")
        self.run = run

    @handler
    async def check(self, msgs: list[MatchResult], ctx: WorkflowContext[VerifiedResult, UiEvent]) -> None:
        run = self.run
        schemes = rules.load_schemes()
        for domain in DOMAINS:
            for scheme_id in verify.coverage_gaps(domain, run.decisions, schemes):
                scheme = rules.scheme_by_id(scheme_id)
                if scheme and run.profile is not None:
                    run.record_decision(rules.evaluate(scheme, run.profile), source="verifier", step=self.id)
        verified = verify.verify(msgs, run.decisions, run.audit, run.audit_complete, schemes)
        run.verified = verified
        await ctx.yield_output(UiEvent(type="verified", step=self.id, data=verified.model_dump()))
        await ctx.send_message(verified)


def fallback_draft(run: RunState) -> DraftDocuments:
    """Deterministic draft used when the documenter agent cannot submit one."""
    verified = run.verified or VerifiedResult()
    items = verified.eligible + verified.unknown
    lines = [f"- {i.scheme_name}({'규칙상 충족' if i.status == 'eligible' else '확인 필요'}, 판정 {i.decision_id})" for i in items]
    questions = [q for i in verified.unknown for q in i.follow_up_questions]
    profile = run.profile
    basic = "가구 정보 없음" if profile is None else (
        f"나이 {profile.age if profile.age is not None else '미확인'}세, 가구 유형 {profile.household_type or '미확인'}, "
        f"가구원 {profile.household_size if profile.household_size is not None else '미확인'}명, 주거 {profile.housing or '미확인'}"
    )
    texts = {
        "record.basic_info": basic,
        "record.summary": (run.masked_note or "")[:600],
        "record.needs": ", ".join((profile.crisis_events + profile.isolation_signals) if profile else []) or "추가 확인 필요",
        "record.linked_schemes": "\n".join(lines) or "연계 제도 없음",
        "record.follow_up": "\n".join(questions) or "없음",
        "referral.agency": "[기관명]",
        "referral.subject": basic,
        "referral.schemes": "\n".join(lines) or "의뢰 제도 없음",
        "referral.officer": "[담당자]",
    }
    cited = [i.decision_id for i in items]
    return DraftDocuments(
        sections=[DraftSection(id=sid, text=texts[sid], cited_decisions=cited if "schemes" in sid else []) for sid in SECTION_IDS],
        follow_up_questions=questions,
    )


class DocumenterExecutor(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="documenter")
        self.run = run

    @handler
    async def write(self, verified: VerifiedResult, ctx: WorkflowContext[DraftReady, UiEvent]) -> None:
        run = self.run
        result = await call_agent(
            self.id, prompts.documenter_prompt(verified, run.profile, run.masked_note or ""), run,
            emit=_emitter(ctx), submitted=lambda: run.draft is not None,
        )
        if not result.ok or run.draft is None:
            await ctx.yield_output(UiEvent(type="step_failed", step=self.id, data={
                "code": result.error_code or "other", "message": "초안 작성 에이전트가 실패해 판정 결과로 기본 초안을 만들었습니다.",
            }))
            run.draft = fallback_draft(run)
        by_id = {s.id: s for s in run.draft.sections}
        complete = [by_id.get(sid) or DraftSection(id=sid, text="") for sid in SECTION_IDS]
        run.draft = run.draft.model_copy(update={"sections": complete})
        await ctx.yield_output(UiEvent(type="draft", step=self.id, data=draft_event_data(run.draft)))
        await ctx.send_message(DraftReady(run_id=run.id, draft=run.draft))


def draft_event_data(draft: DraftDocuments) -> dict:
    return {
        "sections": [
            {"id": s.id, "title": SECTION_TITLES.get(s.id, s.id), "text": s.text, "cited_decisions": s.cited_decisions}
            for s in draft.sections
        ],
        "follow_up_questions": draft.follow_up_questions,
    }


def approval_request_for(run: RunState, draft: DraftDocuments) -> ApprovalRequest:
    verified = run.verified or VerifiedResult()
    scheme_ids = [i.scheme_id for i in verified.eligible + verified.unknown]
    return ApprovalRequest(
        run_id=run.id,
        scheme_ids=scheme_ids,
        documents_summary=["상담기록지(5개 구획)", f"서비스 연계 의뢰서(제도 {len(scheme_ids)}개)"],
        draft_snapshot=draft,
    )


def finalize(run: RunState, request: ApprovalRequest, decision: ApprovalDecision):
    scheme_ids = decision.scheme_ids if decision.scheme_ids is not None else request.scheme_ids
    edited = {k: v for k, v in decision.edited_sections.items() if k in SECTION_IDS}
    return render.render_final(request.draft_snapshot, edited, run.verified or VerifiedResult(), scheme_ids, now_iso())


class ReferralGate(Executor):
    def __init__(self, run: RunState) -> None:
        super().__init__(id="referral_gate")
        self.run = run

    @handler
    async def ask_approval(self, msg: DraftReady, ctx: WorkflowContext[None, UiEvent]) -> None:
        await ctx.request_info(approval_request_for(self.run, msg.draft), ApprovalDecision)

    @response_handler
    async def on_decision(
        self, request: ApprovalRequest, decision: ApprovalDecision, ctx: WorkflowContext[None, UiEvent]
    ) -> None:
        run = self.run
        if not decision.approved:
            await ctx.yield_output(UiEvent(type="approval_kept", step=self.id, data={}))
            return
        try:
            final = finalize(run, request, decision)
        except ValueError as exc:
            await _fatal(ctx, run, self.id, "input_invalid", str(exc))
            return
        run.final_documents = final
        await ctx.yield_output(UiEvent(type="finalized", step=self.id, data=final.model_dump()))


def build_workflow(run: RunState) -> Workflow:
    router, ocr, stt = InputRouter(run), OcrExecutor(run), SttExecutor(run)
    intake, normalizer, profiler = IntakeExecutor(run), NormalizerExecutor(run), ProfilerExecutor(run)
    matchers = [MatchExecutor(run, d) for d in DOMAINS]
    verifier, documenter, gate = VerifierExecutor(run), DocumenterExecutor(run), ReferralGate(run)
    everyone = [router, ocr, stt, intake, normalizer, profiler, *matchers, verifier, documenter]
    return (
        WorkflowBuilder(start_executor=router, intermediate_output_from=everyone, output_from=[gate],
                        max_iterations=config.MAX_ATTEMPTS * 20)
        .add_switch_case_edge_group(router, [
            Case(condition=lambda m: m.source == "image", target=ocr),
            Case(condition=lambda m: m.source == "audio", target=stt),
            Default(target=intake),
        ])
        .add_edge(ocr, intake)
        .add_edge(stt, intake)
        .add_edge(intake, normalizer, condition=lambda m: m.source != "text")
        .add_edge(intake, profiler, condition=lambda m: m.source == "text")
        .add_edge(normalizer, profiler)
        .add_fan_out_edges(profiler, matchers)
        .add_fan_in_edges(matchers, verifier)
        .add_edge(verifier, documenter)
        .add_edge(documenter, gate)
        .build()
    )

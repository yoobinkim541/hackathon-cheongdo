"""RunService: the only entry point that starts, resumes, replays and evaluates runs and changes run status."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from functools import lru_cache
from pathlib import Path

from app import config, ingest, masking, rules, telemetry
from app.agents import HUB
from app.events import map_workflow_event
from app.runs import REGISTRY, EvalState, RunState, now_iso
from app.schemas import (
    PROFILE_RULE_FIELDS,
    ApprovalDecision,
    ApprovalRequest,
    EvalCase,
    Readiness,
    ReplayEvent,
    ReplayFile,
    ReplaySnapshot,
    RunInput,
    UiEvent,
)
from app.workflow import build_workflow, draft_event_data, finalize

log = logging.getLogger("dongheng.service")
REPLAY_DIR = config.DATA_DIR / "replays"
REPLAY_MAX_GAP_MS = 900


@lru_cache(maxsize=1)
def load_cases() -> dict[str, EvalCase]:
    raw = json.loads((config.DATA_DIR / "eval_cases.json").read_text(encoding="utf-8"))
    return {c["id"]: EvalCase(**c) for c in raw}


def sample_path(case: EvalCase) -> Path | None:
    if not case.media_path:
        return None
    path = (config.ROOT / case.media_path).resolve()
    return path if path.is_file() and path.parent == (config.DATA_DIR / "samples").resolve() else None


def load_replay(case_id: str) -> ReplayFile | None:
    path = REPLAY_DIR / f"{case_id}.json"
    if not path.is_file():
        return None
    return ReplayFile.model_validate_json(path.read_text(encoding="utf-8"))


class RunService:
    def __init__(self) -> None:
        self.readiness = Readiness()
        self.live_slots = asyncio.Semaphore(config.LIVE_CONCURRENCY)
        self._sweeper: asyncio.Task | None = None
        self.eval_running = False

    # ---------- lifecycle ----------

    async def startup(self, settings: config.Settings = config.SETTINGS) -> None:
        telemetry.setup(settings)
        r = Readiness(checked_at=now_iso(), ai_services_enabled=settings.enable_ai_services)
        try:
            rules.load_schemes()
            load_cases()
            r.data_ok = True
        except Exception as exc:  # noqa: BLE001
            log.exception("data load failed")
            r.data_ok = False
            r.copilot_error = f"data: {type(exc).__name__}"
        if not settings.disable_copilot:
            try:
                await HUB.start(settings)
                r.copilot_started = True
                auth = await HUB.client.get_auth_status()
                r.copilot_authenticated = bool(getattr(auth, "isAuthenticated", False))
                r.copilot_model = HUB.model
            except Exception as exc:  # noqa: BLE001
                log.exception("copilot start failed")
                r.copilot_error = type(exc).__name__
        if settings.enable_ai_services and settings.azure_ai_endpoint:
            try:
                await ingest.check_token()
                r.ai_services_token_ok = True
            except Exception as exc:  # noqa: BLE001
                r.ai_services_error = type(exc).__name__
        self.readiness = r
        self._sweeper = asyncio.create_task(self._sweep_loop())

    async def shutdown(self) -> None:
        if self._sweeper:
            self._sweeper.cancel()
        for run in list(REGISTRY.runs.values()):
            await self._dispose(run)
        await HUB.stop()

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            for run in REGISTRY.expired_runs():
                await self._dispose(run, expired=True)
            for ev in REGISTRY.expired_evals():
                REGISTRY.evals.pop(ev.id, None)
                ev.log.close()

    async def _dispose(self, run: RunState, expired: bool = False) -> None:
        if expired and run.status not in {"finalized", "drafted", "failed"}:
            run.emit(UiEvent(type="done", data={"status": "expired"}))
        REGISTRY.remove_run(run.id)
        if run.task and not run.task.done():
            run.task.cancel()
        for session in run.sessions.values():
            await HUB.delete_session(getattr(session, "service_session_id", None))
        run.sessions.clear()
        run.media = None

    # ---------- start ----------

    def create_run(
        self, *, source: str, sid: str, text: str | None = None, media: bytes | None = None,
        media_format: str | None = None, case_id: str | None = None, mode: str = "live", purpose: str = "live",
    ) -> RunState:
        names: list[str] = []
        if case_id:
            names = load_cases()[case_id].names
        run = REGISTRY.create_run(
            source=source, mode=mode, purpose=purpose, case_id=case_id, owner_sid=sid,
            raw_text=text, media=media, media_format=media_format, known_names=names,
            status="replaying" if mode == "replay" else "running",
        )
        return run

    def start(self, run: RunState) -> None:
        coro = self._replay(run) if run.mode == "replay" else self._live(run)
        run.task = asyncio.create_task(coro)

    def start_case(self, case_id: str, sid: str, mode: str = "live", purpose: str = "live") -> RunState:
        case = load_cases()[case_id]
        if mode == "live" and not self.readiness.copilot_ready and load_replay(case_id):
            mode = "replay"
        source, media, fmt, text = "text", None, None, case.note
        if case.input_type in ("image", "audio") and mode == "live":
            path = sample_path(case)
            ai_ok = config.SETTINGS.enable_ai_services and self.readiness.ai_services_token_ok
            if path and ai_ok:
                source, media = case.input_type, path.read_bytes()
                fmt = "jpeg" if case.input_type == "image" else path.suffix.lstrip(".").lower()
                text = None
        run = self.create_run(source=source, sid=sid, text=text, media=media, media_format=fmt,
                              case_id=case_id, mode=mode, purpose=purpose)
        self.start(run)
        return run

    # ---------- live ----------

    async def _live(self, run: RunState) -> None:
        async with self.live_slots:
            with telemetry.tracer().start_as_current_span("dongheng.run") as span:
                span.set_attribute("app.run_id", run.id)
                span.set_attribute("app.mode", run.mode)
                span.set_attribute("app.source", run.source)
                run.log.trace_id = telemetry.current_trace_id()
                run.emit(UiEvent(type="run_started", data={"source": run.source, "case_id": run.case_id, "mode": run.mode}))
                try:
                    workflow = build_workflow(run)
                    run.workflow = workflow
                    message = RunInput(run_id=run.id, source=run.source, text=run.raw_text)
                    await self._consume(run, workflow.run(message, stream=True))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    log.exception("workflow start failed")
                    self._finish(run, "failed", "other", f"워크플로를 시작하지 못했습니다({type(exc).__name__}).")
        if run.status == "running":
            self._finish(run, "failed", run.error_code or "other", "실행이 예상치 않게 끝났습니다.")

    async def _consume(self, run: RunState, stream) -> None:
        started: dict[str, float] = {}
        try:
            async for ev in stream:
                etype = getattr(ev, "type", None)
                if etype == "request_info":
                    request = ev.data
                    run.pending_request_id = ev.request_id
                    run.approval_scheme_ids = list(getattr(request, "scheme_ids", []) or [])
                    run.set_status("awaiting_approval")
                    run.emit(UiEvent(type="approval_required", step="referral_gate", data={
                        "request_id": ev.request_id,
                        "scheme_ids": run.approval_scheme_ids,
                        "documents_summary": list(getattr(request, "documents_summary", []) or []),
                    }))
                    continue
                if etype == "failed":
                    run.error_code = run.error_code or "other"
                    continue
                for ui in map_workflow_event(ev):
                    if ui.type == "step_started" and ui.step:
                        started[ui.step] = time.monotonic()
                    elif ui.type == "step_completed" and ui.step in started:
                        ui.data["ms"] = run.timings.get(ui.step) or int((time.monotonic() - started[ui.step]) * 1000)
                        run.timings.setdefault(ui.step, ui.data["ms"])
                    run.emit(ui)
                    if ui.type == "error":
                        self._finish(run, "failed")
                    elif ui.type == "finalized":
                        self._finish(run, "finalized")
                    elif ui.type == "approval_kept":
                        self._finish(run, "drafted")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as an error
            log.exception("workflow stream failed")
            if run.status in {"running", "resuming"}:
                self._finish(run, "failed", "other", f"워크플로 실행 중 오류가 발생했습니다({type(exc).__name__}).")

    def _finish(self, run: RunState, status: str, code: str | None = None, message: str | None = None) -> None:
        if run.status in {"finalized", "drafted", "failed", "expired"}:
            return
        if status == "failed" and code:
            run.emit(UiEvent(type="error", data={"code": code, "message": message or "실행에 실패했습니다."}))
        run.set_status(status)  # type: ignore[arg-type]
        run.emit(UiEvent(type="done", data={"status": status}))

    # ---------- approval ----------

    def respond(self, run: RunState, request_id: str, decision: ApprovalDecision) -> str | None:
        """Returns an error code, or None when the response was accepted."""
        if run.status != "awaiting_approval" or run.pending_request_id != request_id:
            return "state_conflict"
        allowed = set(run.approval_scheme_ids)
        if decision.scheme_ids is not None and not set(decision.scheme_ids) <= allowed:
            return "input_invalid"
        run.pending_request_id = None
        run.set_status("resuming")
        if run.mode == "replay" or run.workflow is None:
            run.task = asyncio.create_task(self._respond_replay(run, decision))
        else:
            run.task = asyncio.create_task(self._consume(run, run.workflow.run(responses={request_id: decision}, stream=True)))
        return None

    async def _respond_replay(self, run: RunState, decision: ApprovalDecision) -> None:
        if not decision.approved:
            run.emit(UiEvent(type="approval_kept", step="referral_gate"))
            self._finish(run, "drafted")
            return
        request = ApprovalRequest(run_id=run.id, scheme_ids=run.approval_scheme_ids, documents_summary=[],
                                  draft_snapshot=run.draft)
        try:
            final = finalize(run, request, decision)
        except ValueError as exc:
            self._finish(run, "failed", "input_invalid", str(exc))
            return
        run.final_documents = final
        run.emit(UiEvent(type="finalized", step="referral_gate", data=final.model_dump()))
        self._finish(run, "finalized")

    # ---------- replay ----------

    async def _replay(self, run: RunState) -> None:
        replay = load_replay(run.case_id or "")
        if replay is None:
            self._finish(run, "failed", "other", "저장된 실행이 없습니다.")
            return
        run.emit(UiEvent(type="run_started", data={"source": run.source, "case_id": run.case_id, "mode": "replay"}))
        last = 0
        for ev in replay.events:
            gap = min(max(ev.t_ms - last, 0), REPLAY_MAX_GAP_MS)
            last = ev.t_ms
            if gap:
                await asyncio.sleep(gap / 1000)
            if ev.type in ("approval_required", "run_started", "done"):
                continue
            run.emit(UiEvent(type=ev.type, step=ev.step, data=ev.data))
        snap = replay.snapshot
        run.verified, run.draft, run.profile = snap.verified, snap.draft, snap.profile
        run.approval_scheme_ids = list(snap.approval_request.scheme_ids)
        run.pending_request_id = str(uuid.uuid4())
        run.set_status("awaiting_approval")
        run.emit(UiEvent(type="approval_required", step="referral_gate", data={
            "request_id": run.pending_request_id,
            "scheme_ids": run.approval_scheme_ids,
            "documents_summary": snap.approval_request.documents_summary,
        }))

    async def record_replay(self, case_id: str, sid: str = "recorder") -> ReplayFile:
        run = self.start_case(case_id, sid, mode="live", purpose="record")
        await run.task
        if run.status != "awaiting_approval" or run.verified is None or run.draft is None:
            raise RuntimeError(f"{case_id}: run ended as {run.status}")
        t0 = None
        events: list[ReplayEvent] = []
        for entry in run.log.entries:
            ts = time.mktime(time.strptime(entry["ts"][:19], "%Y-%m-%dT%H:%M:%S")) * 1000 + int(entry["ts"][20:23])
            t0 = ts if t0 is None else t0
            events.append(ReplayEvent(type=entry["type"], step=entry["step"], data=entry["data"], t_ms=int(ts - t0)))
        from app.workflow import approval_request_for

        snapshot = ReplaySnapshot(
            verified=run.verified, draft=run.draft, approval_request=approval_request_for(run, run.draft), profile=run.profile,
        )
        await self._dispose(run)
        return ReplayFile(case_id=case_id, recorded_at=now_iso(), events=events, snapshot=snapshot)

    # ---------- evaluation ----------

    def start_eval(self, sid: str) -> EvalState:
        ev = REGISTRY.create_eval(owner_sid=sid)
        self.eval_running = True
        ev.task = asyncio.create_task(self._eval(ev))
        return ev

    async def _eval(self, ev: EvalState) -> None:
        cases = list(load_cases().values())
        results: list[dict] = []
        slots = asyncio.Semaphore(config.EVAL_CONCURRENCY)
        deadline = time.monotonic() + config.EVAL_DEADLINE_SECONDS

        async def one(case: EvalCase) -> None:
            async with slots:
                ev.log.append(UiEvent(type="case_started", data={"case_id": case.id, "title": case.title}))
                result = await self._eval_case(case, ev.owner_sid, deadline)
                results.append(result)
                ev.log.append(UiEvent(type="case_completed", data=result))

        try:
            await asyncio.gather(*(one(c) for c in cases))
            ev.log.append(UiEvent(type="eval_summary", data=summarize(results)))
            ev.log.append(UiEvent(type="done", data={"status": "finalized"}))
        except Exception as exc:  # noqa: BLE001
            log.exception("eval failed")
            ev.log.append(UiEvent(type="error", data={"code": "other", "message": f"평가 중 오류({type(exc).__name__})"}))
            ev.log.append(UiEvent(type="done", data={"status": "failed"}))
        finally:
            ev.done = True
            self.eval_running = False

    async def _eval_case(self, case: EvalCase, sid: str, deadline: float) -> dict:
        started = time.monotonic()
        run = None
        replayed = False
        if self.readiness.copilot_ready and time.monotonic() < deadline:
            run = self.start_case(case.id, sid, mode="live", purpose="eval")
            try:
                await asyncio.wait_for(asyncio.shield(run.task), max(deadline - time.monotonic(), 1))
            except TimeoutError:
                pass
            if run.status != "awaiting_approval" or run.verified is None:
                replayed = True
        else:
            replayed = True
        ms = int((time.monotonic() - started) * 1000)
        if replayed:
            replay = load_replay(case.id)
            verified = replay.snapshot.verified if replay else None
            profile = replay.snapshot.profile if replay else None
            metrics = case_metrics(case, verified, profile, None, None, {}, {})
        else:
            metrics = case_metrics(case, run.verified, run.profile, run, run.transcript_text, run.timings, run.decisions)
        if run is not None:
            await self._dispose(run)
        return {"case_id": case.id, "title": case.title, "replayed": replayed, "ms": ms, **metrics}


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _compact(text: str) -> str:
    return "".join(ch for ch in text if not ch.isspace() and ch not in ":")


def case_metrics(case, verified, profile, run, transcript, timings, decisions) -> dict:
    expected_found = set(case.expected_eligible) | set(case.expected_unknown)
    if verified is None:
        return {"recall": None, "precision": None, "evidence_match": None, "stage_ms": {}, "mask_residual": None,
                "mask_recall": None, "mask_false_positive": None, "cer": None, "auto_filled": None,
                "missing_fields": None, "verifier_filled": None}
    pred_elig = {i.scheme_id for i in verified.eligible}
    pred_found = pred_elig | {i.scheme_id for i in verified.unknown}
    recall = _ratio(len(expected_found & pred_found), len(expected_found))
    precision = _ratio(len(pred_elig & set(case.expected_eligible)), len(pred_elig)) if pred_elig else (1.0 if not case.expected_eligible else 0.0)
    shown = verified.eligible + verified.unknown
    evidence = None
    if decisions:
        good = sum(1 for i in shown if (d := decisions.get(i.decision_id)) and d.scheme_id == i.scheme_id and d.status == i.status)
        evidence = _ratio(good, len(shown)) if shown else 1.0
    mask_residual = mask_recall = mask_fp = None
    if run is not None and run.masked_note is not None:
        masked = run.masked_note
        mask_residual = len(masking.find_residual(masked))
        pii_texts = [p.text for p in case.pii_spans]
        hidden = sum(1 for t in pii_texts if t not in masked)
        mask_recall = _ratio(hidden, len(pii_texts)) if pii_texts else 1.0
        originals = {s.get("placeholder") for s in run.mask_spans}
        source_text = run.raw_text or run.transcript_text or ""
        fp = sum(1 for s in run.mask_spans if not any(t in source_text[s["start"]:s["end"]] or source_text[s["start"]:s["end"]] in t for t in pii_texts))
        mask_fp = fp if originals is not None else 0
    cer = None
    if transcript and case.reference_text:
        ref = _compact(case.reference_text)
        cer = _ratio(levenshtein(_compact(transcript), ref), len(ref))
    auto = missing = None
    if profile is not None:
        auto = sum(1 for f in PROFILE_RULE_FIELDS if getattr(profile, f) is not None)
        missing = len(PROFILE_RULE_FIELDS) - auto
    return {
        "recall": recall, "precision": precision, "evidence_match": evidence, "stage_ms": dict(timings),
        "mask_residual": mask_residual, "mask_recall": mask_recall, "mask_false_positive": mask_fp, "cer": cer,
        "auto_filled": auto, "missing_fields": missing, "verifier_filled": len(verified.verifier_filled),
    }


def summarize(results: list[dict]) -> dict:
    live = [r for r in results if not r["replayed"]]

    def avg(key):
        vals = [r[key] for r in live if r.get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    return {
        "cases": len(results),
        "live_cases": len(live),
        "recall": avg("recall"),
        "precision": avg("precision"),
        "evidence_match": avg("evidence_match"),
        "avg_ms": avg("ms"),
        "mask_residual_total": sum(r.get("mask_residual") or 0 for r in live),
        "mask_recall": avg("mask_recall"),
        "cer_avg": avg("cer"),
    }


SERVICE = RunService()

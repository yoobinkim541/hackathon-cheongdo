"""Function tools exposed to the Copilot agents. Every write is guarded by run state, step and attempt."""

import json
from typing import Annotated

from agent_framework import FunctionInvocationContext, tool
from pydantic import ValidationError

from app import rules, textnum, verify
from app.runs import REGISTRY, RunState
from app.schemas import (
    MATCH_STEP,
    PROFILE_RULE_FIELDS,
    SECTION_IDS,
    STEP_DOMAIN,
    CaseProfile,
    CleanNote,
    Domain,
    DraftDocuments,
    MatchSubmission,
    SchemeSummary,
)

EXPIRED = "실행이 만료되었습니다. 더 이상 도구를 호출하지 말고 끝내세요."
MAX_SUBMIT_REJECTIONS = 2


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _guard(ctx: FunctionInvocationContext, steps: tuple[str, ...], write: bool) -> tuple[RunState | None, str | None]:
    kwargs = ctx.kwargs or {}
    run = REGISTRY.get_run(kwargs.get("run_id", ""))
    if run is None:
        return None, EXPIRED
    step = kwargs.get("step")
    if step not in steps:
        return None, f"이 도구는 {', '.join(steps)} 단계에서만 쓸 수 있습니다."
    if write:
        if run.status != "running" or kwargs.get("phase") != "workflow":
            return None, "지금은 기록할 수 없는 상태입니다."
        if kwargs.get("attempt") != run.attempts.get(step):
            return None, "이전 시도의 호출이라 기록하지 않았습니다."
    run.touch()
    return run, None


def _coerce(model, value):
    """MAF passes nested tool arguments as plain dicts; validate them into the Pydantic model."""
    if isinstance(value, model):
        return value, None
    try:
        return model.model_validate(value), None
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []))
        return None, f"인자 형식이 올바르지 않습니다({where}: {first.get('msg', '')}). 고쳐 다시 호출하세요."


@tool
async def record_clean_note(
    note: Annotated[CleanNote, "정리한 방문 메모, 바꾼 구간, 불확실 구간"],
    ctx: FunctionInvocationContext,
) -> str:
    """정리한 방문 메모를 기록한다. 원문에 없는 숫자를 새로 쓰면 거부된다."""
    run, err = _guard(ctx, ("normalizer",), write=True)
    if err:
        return err
    note, err = _coerce(CleanNote, note)
    if err:
        return err
    added = textnum.new_numbers(run.masked_note or "", note.clean_text)
    if added:
        return f"거부: 원문에 없는 숫자 {sorted(added)}가 생겼습니다. 원문에 있는 숫자만 쓰고 다시 제출하세요."
    run.clean_note = note
    return "기록했습니다."


@tool
async def record_case_profile(
    profile: Annotated[CaseProfile, "메모에서 읽은 판정 입력값. 모르는 값은 null"],
    ctx: FunctionInvocationContext,
) -> str:
    """방문 메모에서 구조화한 가구 정보를 기록하고 누락 필드를 돌려준다."""
    run, err = _guard(ctx, ("profiler",), write=True)
    if err:
        return err
    profile, err = _coerce(CaseProfile, profile)
    if err:
        return err
    missing = [f for f in PROFILE_RULE_FIELDS if getattr(profile, f) is None]
    profile = profile.model_copy(update={"missing_fields": missing})
    run.profile = profile
    return _dump({"recorded": True, "missing_fields": missing})


@tool
async def search_schemes(
    domain: Annotated[Domain, "분야: living, health, care"],
    ctx: FunctionInvocationContext,
) -> str:
    """분야의 복지 제도 목록(ID, 이름, 요약, 필요한 입력 필드)을 돌려준다."""
    allowed = tuple(MATCH_STEP.values())
    run, err = _guard(ctx, allowed, write=False)
    if err:
        return err
    step_domain = STEP_DOMAIN[ctx.kwargs["step"]]
    if domain != step_domain:
        return f"이 단계의 분야는 {step_domain}입니다."
    items = [
        SchemeSummary(id=s.id, name=s.name, summary=s.summary, required_fields=s.required_fields).model_dump()
        for s in rules.load_schemes()
        if s.domain == domain
    ]
    return _dump(items)


@tool
async def check_eligibility(
    scheme_id: Annotated[str, "판정할 제도 ID"],
    ctx: FunctionInvocationContext,
) -> str:
    """실행 상태의 가구 정보로 제도 자격을 규칙 함수로 판정하고 decision_id와 조건별 근거를 돌려준다."""
    allowed = tuple(MATCH_STEP.values())
    run, err = _guard(ctx, allowed, write=True)
    if err:
        return err
    step = ctx.kwargs["step"]
    scheme = rules.scheme_by_id(scheme_id)
    if scheme is None:
        return f"알 수 없는 제도 ID입니다: {scheme_id}"
    if scheme.domain != STEP_DOMAIN[step]:
        return "이 단계의 분야가 아닌 제도입니다."
    if run.profile is None:
        return "가구 정보가 아직 없습니다."
    record = run.record_decision(rules.evaluate(scheme, run.profile), source="tool", step=step)
    return record.model_dump_json()


@tool
async def submit_matches(
    submission: Annotated[MatchSubmission, "추천 목록. 각 항목은 check_eligibility가 돌려준 decision_id와 조건 ID를 인용"],
    ctx: FunctionInvocationContext,
) -> str:
    """분야 매칭 결과(추천 제도 목록)를 제출한다."""
    allowed = tuple(MATCH_STEP.values())
    run, err = _guard(ctx, allowed, write=True)
    if err:
        return err
    submission, err = _coerce(MatchSubmission, submission)
    if err:
        return err
    step = ctx.kwargs["step"]
    domain = STEP_DOMAIN[step]
    problems = [
        f"{rec.scheme_id}: {reason}"
        for rec in submission.recommendations
        if (reason := verify.check_citations(rec, run.decisions, domain))
    ]
    rejections = run.submit_rejections.get(step, 0)
    if problems and rejections < MAX_SUBMIT_REJECTIONS:
        run.submit_rejections[step] = rejections + 1
        return "거부: " + "; ".join(problems) + ". 판정 기록과 맞게 고쳐 다시 제출하세요."
    run.match_submissions[domain] = submission
    return "제출했습니다."


@tool
async def lookup_decision(
    decision_id: Annotated[str, "판정 ID(d1, d2 …)"],
    ctx: FunctionInvocationContext,
) -> str:
    """같은 실행의 판정 기록 하나를 읽는다."""
    run, err = _guard(ctx, ("documenter",), write=False)
    if err:
        return err
    record = run.decisions.get(decision_id)
    return record.model_dump_json() if record else f"판정 기록이 없습니다: {decision_id}"


@tool
async def submit_draft(
    draft: Annotated[DraftDocuments, "상담기록지·의뢰서 구획별 초안"],
    ctx: FunctionInvocationContext,
) -> str:
    """상담기록지와 서비스 연계 의뢰서 초안을 구획별로 제출한다."""
    run, err = _guard(ctx, ("documenter",), write=True)
    if err:
        return err
    draft, err = _coerce(DraftDocuments, draft)
    if err:
        return err
    unknown = [s.id for s in draft.sections if s.id not in SECTION_IDS]
    missing_refs = [d for s in draft.sections for d in s.cited_decisions if d not in run.decisions]
    rejections = run.submit_rejections.get("documenter", 0)
    if (unknown or missing_refs) and rejections < MAX_SUBMIT_REJECTIONS:
        run.submit_rejections["documenter"] = rejections + 1
        parts = []
        if unknown:
            parts.append(f"알 수 없는 구획 ID {unknown}")
        if missing_refs:
            parts.append(f"없는 판정 ID {missing_refs}")
        return "거부: " + ", ".join(parts) + f". 구획 ID는 {list(SECTION_IDS)} 중에서 쓰세요."
    sections = [s for s in draft.sections if s.id in SECTION_IDS]
    run.draft = draft.model_copy(update={"sections": sections})
    return "제출했습니다."


TOOLS = {
    "record_clean_note": record_clean_note,
    "record_case_profile": record_case_profile,
    "search_schemes": search_schemes,
    "check_eligibility": check_eligibility,
    "submit_matches": submit_matches,
    "lookup_decision": lookup_decision,
    "submit_draft": submit_draft,
}

"""모듈 경계를 넘는 모든 타입(스파인 AD-2). 이 파일은 계약 변경 요청으로만 바꾼다."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------- 리터럴

Domain = Literal["living", "health", "care"]
Step = Literal[
    "input_router",
    "ocr",
    "stt",
    "intake",
    "normalizer",
    "profiler",
    "match_living",
    "match_health",
    "match_care",
    "verifier",
    "documenter",
    "referral_gate",
    "ask",
]
SectionId = Literal[
    "record.basic_info",
    "record.summary",
    "record.needs",
    "record.linked_schemes",
    "record.follow_up",
    "referral.agency",
    "referral.subject",
    "referral.schemes",
    "referral.officer",
]
Decision = Literal["eligible", "unknown", "ineligible"]
RunStatus = Literal[
    "queued",
    "running",
    "replaying",
    "awaiting_approval",
    "resuming",
    "finalized",
    "drafted",
    "failed",
    "replaced",
    "expired",
]
InputSource = Literal["text", "image", "audio"]
Mode = Literal["live", "replay"]
Phase = Literal["workflow", "ask"]
Purpose = Literal["live", "eval"]
ErrorCode = Literal[
    "rate_limit",
    "timeout",
    "tool_missing",
    "other",
    "pii_residual",
    "input_invalid",
    "recognition_failed",
]
HouseholdType = Literal["독거", "부부", "조손", "한부모", "기타"]
Disability = Literal["없음", "경증", "중증"]
Housing = Literal["자가", "전세", "월세", "무상"]

DOMAINS: tuple[Domain, ...] = ("living", "health", "care")
MATCH_STEPS: dict[Domain, Step] = {
    "living": "match_living",
    "health": "match_health",
    "care": "match_care",
}
SECTION_IDS: tuple[SectionId, ...] = (
    "record.basic_info",
    "record.summary",
    "record.needs",
    "record.linked_schemes",
    "record.follow_up",
    "referral.agency",
    "referral.subject",
    "referral.schemes",
    "referral.officer",
)
RULE_FIELDS: tuple[str, ...] = (
    "age",
    "household_type",
    "household_size",
    "monthly_income_krw",
    "disability",
    "housing",
)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------- 제도·판정


class SchemeRule(Model):
    condition_id: str
    field: str | None = None
    op: str
    value: Any = None
    ratio: float | None = None


class Scheme(Model):
    id: str
    name: str
    domain: Domain
    summary: str
    rules: list[SchemeRule]
    required_fields: list[str]
    source_url: str
    checked_at: str
    is_example: bool = True


class SchemeCatalog(Model):
    median_income_krw: dict[int, int]
    median_income_source_url: str
    checked_at: str
    schemes: list[Scheme]


class SchemeSummary(Model):
    id: str
    name: str
    summary: str
    required_fields: list[str]


class ConditionResult(Model):
    id: str
    met: bool | None = None
    used_values: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class RuleOutcome(Model):
    scheme_id: str
    decision: Decision
    conditions: list[ConditionResult]
    missing_fields: list[str] = Field(default_factory=list)
    source_url: str


class DecisionRecord(Model):
    decision_id: str
    scheme_id: str
    domain: Domain
    decision: Decision
    conditions: list[ConditionResult]
    missing_fields: list[str] = Field(default_factory=list)
    source_url: str
    source: Literal["tool", "verifier"]


# --------------------------------------------------------------------- 프로필


class CaseProfile(Model):
    age: int | None = None
    household_type: HouseholdType | None = None
    household_size: int | None = None
    monthly_income_krw: int | None = None
    assets_krw: int | None = None
    disability: Disability | None = None
    chronic_illness: list[str] | None = None
    housing: Housing | None = None
    monthly_rent_krw: int | None = None
    caregiver_available: bool | None = None
    isolation_signals: list[str] | None = None
    crisis_events: list[str] | None = None
    missing_fields: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------- 가리기·인식


class PiiSpan(Model):
    start: int
    end: int
    kind: Literal["rrn", "phone", "account", "address", "name"]
    placeholder: str | None = None


class MaskResult(Model):
    masked_text: str
    spans: list[PiiSpan] = Field(default_factory=list)
    pii_map: dict[str, str] = Field(default_factory=dict)
    residual: list[PiiSpan] = Field(default_factory=list)


class TextSpan(Model):
    start: int
    end: int


class Transcript(Model):
    text: str
    uncertain: list[TextSpan] = Field(default_factory=list)
    speakers: int | None = None
    duration_ms: int | None = None
    chars: int = 0


class NoteEdit(Model):
    original: str
    replacement: str
    reason: str


class CleanNote(Model):
    clean_text: str
    edits: list[NoteEdit] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------- 워크플로 메시지


class RunInput(Model):
    source: InputSource = "text"
    note: str | None = None
    media: bytes | None = Field(default=None, exclude=True, repr=False)
    media_type: str | None = None
    case_id: str | None = None
    origin_run_id: str | None = None


class RecognizedText(Model):
    source: InputSource
    text: str
    transcript: Transcript


class MaskedNote(Model):
    source: InputSource
    masked_text: str


class ProfileReady(Model):
    run_id: str


class Recommendation(Model):
    scheme_id: str
    decision_id: str
    status: Decision
    condition_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    priority: int | None = None


class MatchSubmission(Model):
    recommendations: list[Recommendation] = Field(default_factory=list)


class MatchResult(Model):
    domain: Domain
    status: Literal["ok", "failed"]
    error_code: ErrorCode | None = None
    submission: MatchSubmission | None = None


class MatchChain(Model):
    results: list[MatchResult] = Field(default_factory=list)


class RemovedItem(Model):
    scheme_id: str
    decision_id: str | None = None
    reason: str


class VerifiedItem(Model):
    decision: DecisionRecord
    explanation: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    priority: int | None = None


class VerifiedResult(Model):
    eligible: list[VerifiedItem] = Field(default_factory=list)
    needs_check: list[VerifiedItem] = Field(default_factory=list)
    ineligible: list[VerifiedItem] = Field(default_factory=list)
    removed: list[RemovedItem] = Field(default_factory=list)
    failed_domains: list[Domain] = Field(default_factory=list)
    supplemented: list[str] = Field(default_factory=list)
    audit_rule_skipped: list[Step] = Field(default_factory=list)

    def passed_scheme_ids(self) -> list[str]:
        return [i.decision.scheme_id for i in self.eligible + self.needs_check]


class DraftDocuments(Model):
    sections: dict[SectionId, str]
    follow_up_questions: dict[str, list[str]] = Field(default_factory=dict)


class DraftReady(Model):
    draft: DraftDocuments


# --------------------------------------------------------------------- 승인·확정


class ApprovalRequest(Model):
    run_id: str
    scheme_ids: list[str]
    documents_summary: str
    draft_snapshot: DraftDocuments


class ApprovalDecision(Model):
    request_id: str
    approved: bool
    edited_sections: dict[SectionId, str] = Field(default_factory=dict)
    scheme_ids: list[str] | None = None


class FinalDocuments(Model):
    sections: dict[SectionId, str]
    scheme_ids: list[str]
    finalized_at: datetime


# --------------------------------------------------------------------- 에이전트 호출


class InvocationKwargs(Model):
    run_id: str
    step: Step
    phase: Phase = "workflow"


class AuditEntry(Model):
    tool: str
    call_id: str | None = None
    decision_id: str | None = None


class StepAudit(Model):
    entries: list[AuditEntry] = Field(default_factory=list)
    calls: int = 0
    results: int = 0
    complete: bool = True


class AgentCallResult(Model):
    ok: bool
    error_code: ErrorCode | None = None
    attempts: int = 0
    text: str = ""


# --------------------------------------------------------------------- 이벤트

UiEventType = Literal[
    "masked",
    "transcribed",
    "normalized",
    "step_started",
    "step_completed",
    "step_failed",
    "step_retry",
    "token",
    "tool_call",
    "tool_result",
    "usage",
    "verified",
    "draft",
    "approval_required",
    "finalized",
    "approval_kept",
    "error",
    "replaced",
    "queued",
    "done",
    "case_started",
    "case_completed",
    "eval_summary",
]


class UiEvent(Model):
    type: UiEventType
    step: Step | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Envelope(Model):
    run_id: str
    seq: int
    ts: str
    type: UiEventType
    step: Step | None = None
    mode: Mode
    trace_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class MaskedData(Model):
    before: str
    after: str
    spans: list[PiiSpan]


class TranscribedData(Model):
    chars: int
    uncertain: list[TextSpan]
    speakers: int | None = None
    ms: int


class NormalizedData(Model):
    clean_text: str
    edits: list[NoteEdit] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    skipped: bool = False


class StepCompletedData(Model):
    ms: int | None = None


class StepFailedData(Model):
    code: ErrorCode
    message: str
    retryable: bool = False


class StepRetryData(Model):
    attempt: int
    reason: str


class TokenData(Model):
    text: str
    ask_id: str | None = None


class ToolCallData(Model):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ask_id: str | None = None


class ToolResultData(Model):
    tool: str
    decision_id: str | None = None
    ask_id: str | None = None


class UsageData(Model):
    input: int = 0
    output: int = 0
    ask_id: str | None = None


class ApprovalRequiredData(Model):
    request_id: str
    scheme_ids: list[str]
    documents_summary: str


class ReplacedData(Model):
    run_id: str
    reason: str


class QueuedData(Model):
    position: int


class ErrorData(Model):
    code: ErrorCode
    message: str
    retryable: bool = False


class DoneData(Model):
    status: RunStatus


# --------------------------------------------------------------------- 재생·평가


class ReplayEvent(Model):
    type: UiEventType
    step: Step | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    t_ms: int


class ReplaySnapshot(Model):
    verified: VerifiedResult
    draft: DraftDocuments
    approval_request: ApprovalRequest


class ReplayFile(Model):
    case_id: str
    recorded_at: str
    events: list[ReplayEvent]
    snapshot: ReplaySnapshot


class ExpectedPii(Model):
    start: int
    end: int
    kind: Literal["rrn", "phone", "account", "address", "name"]


class EvalCase(Model):
    case_id: str
    title: str
    summary: str
    input_type: InputSource
    note: str
    media_path: str | None = None
    reference_text: str | None = None
    expected_profile: dict[str, Any]
    expected_eligible: list[str]
    expected_unknown: list[str]
    expected_ineligible: list[str]
    pii_spans: list[ExpectedPii]


class CaseMetrics(Model):
    case_id: str
    replayed: bool = False
    recall: float | None = None
    precision: float | None = None
    grounding: float | None = None
    total_ms: int | None = None
    step_ms: dict[str, int] = Field(default_factory=dict)
    pii_recall: float | None = None
    pii_false_positives: int = 0
    pii_residual: int = 0
    autofilled_fields: int = 0
    manual_fields: int = 0
    supplemented: int = 0
    removed: int = 0
    cer: float | None = None
    required_field_matches: int | None = None


class EvalSummary(Model):
    cases: list[CaseMetrics]
    live_count: int
    replay_count: int
    recall: float | None = None
    precision: float | None = None
    grounding: float | None = None
    p50_ms: int | None = None
    p95_ms: int | None = None


# --------------------------------------------------------------------- 기타


class Readiness(Model):
    copilot_started: bool = False
    auth_ok: bool = False
    model_ok: bool = False
    ai_services_ok: bool | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.copilot_started and self.auth_ok and self.model_ok and not self.errors


class Features(Model):
    image_input: bool = False
    audio_input: bool = False
    browser_recording: bool = False
    ask: bool = False
    reapproval: bool = False


class ApiError(Model):
    code: ErrorCode | Literal["not_found", "conflict", "rate_limited", "not_implemented"]
    message: str

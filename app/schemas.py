"""All types that cross module boundaries."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Domain = Literal["living", "health", "care"]
DOMAINS: tuple[Domain, ...] = ("living", "health", "care")
Source = Literal["text", "image", "audio"]
Status = Literal["eligible", "ineligible", "unknown"]
RunStatus = Literal["running", "replaying", "awaiting_approval", "resuming", "finalized", "drafted", "failed", "expired"]
Mode = Literal["live", "replay"]
ErrorCode = Literal[
    "rate_limit", "timeout", "tool_missing", "pii_residual", "input_invalid", "ai_unavailable", "copilot_unavailable", "other"
]

STEP_IDS = (
    "input_router", "ocr", "stt", "intake", "normalizer", "profiler",
    "match_living", "match_health", "match_care", "verifier", "documenter", "referral_gate",
)
MATCH_STEP = {"living": "match_living", "health": "match_health", "care": "match_care"}
STEP_DOMAIN = {v: k for k, v in MATCH_STEP.items()}

SECTION_IDS = (
    "record.basic_info", "record.summary", "record.needs", "record.linked_schemes", "record.follow_up",
    "referral.agency", "referral.subject", "referral.schemes", "referral.officer",
)
SECTION_TITLES = {
    "record.basic_info": "기본 정보",
    "record.summary": "상담 내용 요약",
    "record.needs": "욕구 분류",
    "record.linked_schemes": "연계 제도",
    "record.follow_up": "확인 필요 항목과 다음 방문 질문",
    "referral.agency": "의뢰 기관",
    "referral.subject": "대상자 요약",
    "referral.schemes": "의뢰 제도와 근거 조건",
    "referral.officer": "담당자",
}
PROFILE_RULE_FIELDS = ("age", "household_type", "household_size", "monthly_income_krw", "disability", "housing")


# ---------- domain data ----------

class Scheme(BaseModel):
    id: str
    name: str
    domain: Domain
    summary: str
    rule: str
    params: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[str]
    source_url: str
    checked_at: str
    is_example: bool = True


class SchemeSummary(BaseModel):
    id: str
    name: str
    summary: str
    required_fields: list[str]


class CaseProfile(BaseModel):
    age: int | None = Field(None, description="대상자 나이(세). 모르면 null")
    household_type: Literal["독거", "부부", "조손", "한부모", "기타"] | None = Field(None, description="가구 유형")
    household_size: int | None = Field(None, description="가구원 수")
    monthly_income_krw: int | None = Field(None, description="가구 월 소득(원). 모르면 null")
    assets_krw: int | None = Field(None, description="재산 추정(원)")
    disability: Literal["없음", "경증", "중증"] | None = Field(None, description="장애 정도")
    chronic_illness: list[str] = Field(default_factory=list, description="만성 질환")
    housing: Literal["자가", "전세", "월세", "무상"] | None = Field(None, description="주거 형태")
    monthly_rent_krw: int | None = Field(None, description="월세(원)")
    caregiver_available: bool | None = Field(None, description="돌봐 줄 가족·보호자 유무")
    isolation_signals: list[str] = Field(default_factory=list, description="고립 신호")
    crisis_events: list[str] = Field(default_factory=list, description="실직·질병·사망 같은 위기 사건")
    current_benefits: list[str] = Field(default_factory=list, description="메모에 받고 있다고 적힌 복지 제도 이름(예: 기초연금)")
    missing_fields: list[str] = Field(default_factory=list, description="메모에서 알 수 없는 필드")


class ConditionResult(BaseModel):
    id: str
    label: str
    met: bool | None
    used_value: str | None = None


class EligibilityResult(BaseModel):
    scheme_id: str
    scheme_name: str
    domain: Domain
    status: Status
    conditions: list[ConditionResult]
    missing_fields: list[str] = Field(default_factory=list)
    source_url: str


class DecisionRecord(EligibilityResult):
    decision_id: str
    source: Literal["tool", "verifier"]
    step: str


# ---------- model submissions (tool arguments) ----------

class Recommendation(BaseModel):
    scheme_id: str = Field(description="추천하는 제도 ID")
    decision_id: str = Field(description="check_eligibility가 돌려준 decision_id")
    condition_ids: list[str] = Field(default_factory=list, description="근거로 인용하는 조건 ID(판정 기록의 conditions[].id)")
    explanation: str = Field(description="담당자에게 보일 짧은 설명")
    follow_up_questions: list[str] = Field(default_factory=list, description="확인 필요일 때 다음 방문 질문")
    priority: int = Field(1, description="1이 가장 우선")


class MatchSubmission(BaseModel):
    recommendations: list[Recommendation]


class Edit(BaseModel):
    original: str
    replacement: str
    reason: str


class Span(BaseModel):
    start: int
    end: int
    text: str


class CleanNote(BaseModel):
    clean_text: str = Field(description="정리한 방문 메모")
    edits: list[Edit] = Field(default_factory=list, description="바꾼 구간")
    uncertain: list[str] = Field(default_factory=list, description="확인이 필요한 구간의 글")


class DraftSection(BaseModel):
    id: str = Field(description="구획 ID: " + ", ".join(SECTION_IDS))
    text: str
    cited_decisions: list[str] = Field(default_factory=list)


class DraftDocuments(BaseModel):
    sections: list[DraftSection]
    follow_up_questions: list[str] = Field(default_factory=list)


# ---------- workflow messages ----------

class RunInput(BaseModel):
    run_id: str
    source: Source
    text: str | None = None


class Transcript(BaseModel):
    source: Literal["image", "audio"]
    text: str
    uncertain: list[str] = Field(default_factory=list)
    speakers: int | None = None
    duration_ms: int | None = None
    ms: int = 0


class TranscriptReady(BaseModel):
    run_id: str
    source: Source
    text: str


class MaskSpan(BaseModel):
    kind: Literal["rrn", "phone", "account", "address", "name"]
    start: int
    end: int
    placeholder: str


class MaskResult(BaseModel):
    text: str
    spans: list[MaskSpan]
    residual: list[str] = Field(default_factory=list)


class MaskedNote(BaseModel):
    run_id: str
    source: Source
    text: str


class ProfileRequest(BaseModel):
    run_id: str
    source: Source
    text: str
    normalized: bool = False


class ProfileReady(BaseModel):
    run_id: str
    profile: CaseProfile


class MatchResult(BaseModel):
    domain: Domain
    status: Literal["ok", "failed"]
    error_code: str | None = None
    submission: MatchSubmission | None = None


class VerifiedItem(BaseModel):
    scheme_id: str
    scheme_name: str
    domain: Domain
    status: Status
    decision_id: str
    condition_ids: list[str]
    explanation: str
    follow_up_questions: list[str] = Field(default_factory=list)
    source: Literal["model", "verifier"]
    missing_fields: list[str] = Field(default_factory=list)


class RemovedItem(BaseModel):
    scheme_id: str
    decision_id: str | None
    reason: str


class VerifiedResult(BaseModel):
    eligible: list[VerifiedItem] = Field(default_factory=list)
    unknown: list[VerifiedItem] = Field(default_factory=list)
    ineligible: list[VerifiedItem] = Field(default_factory=list)
    removed: list[RemovedItem] = Field(default_factory=list)
    failed_domains: list[str] = Field(default_factory=list)
    verifier_filled: list[str] = Field(default_factory=list)
    audit_rule_skipped: list[str] = Field(default_factory=list)


class DraftReady(BaseModel):
    run_id: str
    draft: DraftDocuments


class ApprovalRequest(BaseModel):
    run_id: str
    scheme_ids: list[str]
    documents_summary: list[str]
    draft_snapshot: DraftDocuments


class ApprovalDecision(BaseModel):
    approved: bool
    edited_sections: dict[str, str] = Field(default_factory=dict)
    scheme_ids: list[str] | None = None


class FinalSection(BaseModel):
    id: str
    title: str
    text: str


class FinalDocuments(BaseModel):
    record: list[FinalSection]
    referral: list[FinalSection]
    scheme_ids: list[str]
    finalized_at: str


# ---------- events ----------

class UiEvent(BaseModel):
    type: str
    step: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    tool: str
    call_id: str | None = None
    decision_id: str | None = None
    has_result: bool = False


class AgentCallResult(BaseModel):
    ok: bool
    error_code: str | None = None
    attempts: int = 0
    ms: int = 0
    text: str = ""


# ---------- replay / eval ----------

class ReplayEvent(BaseModel):
    type: str
    step: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    t_ms: int = 0


class ReplaySnapshot(BaseModel):
    verified: VerifiedResult
    draft: DraftDocuments
    approval_request: ApprovalRequest
    profile: CaseProfile | None = None


class ReplayFile(BaseModel):
    case_id: str
    recorded_at: str
    events: list[ReplayEvent]
    snapshot: ReplaySnapshot


class PiiSpan(BaseModel):
    kind: str
    text: str


class EvalCase(BaseModel):
    id: str
    title: str
    household: str
    input_type: Source = "text"
    note: str
    media_path: str | None = None
    reference_text: str | None = None
    expected_profile: dict[str, Any] = Field(default_factory=dict)
    expected_eligible: list[str] = Field(default_factory=list)
    expected_unknown: list[str] = Field(default_factory=list)
    expected_ineligible: list[str] = Field(default_factory=list)
    pii_spans: list[PiiSpan] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)


class Readiness(BaseModel):
    process_ok: bool = True
    data_ok: bool = False
    copilot_started: bool = False
    copilot_authenticated: bool = False
    copilot_model: str | None = None
    copilot_error: str | None = None
    ai_services_enabled: bool = False
    ai_services_token_ok: bool = False
    ai_services_error: str | None = None
    checked_at: str | None = None

    @property
    def copilot_ready(self) -> bool:
        return self.copilot_started and self.copilot_authenticated

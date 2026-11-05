"""Evidence verification of match recommendations (TRD 3.4). Pure functions only."""

from __future__ import annotations

from app.schemas import (
    DOMAINS,
    MATCH_STEP,
    AuditEntry,
    DecisionRecord,
    MatchResult,
    Recommendation,
    RemovedItem,
    Scheme,
    VerifiedItem,
    VerifiedResult,
)

FIELD_LABELS = {
    "age": "나이",
    "household_type": "가구 유형",
    "household_size": "가구원 수",
    "monthly_income_krw": "월 소득",
    "assets_krw": "재산 규모",
    "disability": "장애 여부와 정도",
    "chronic_illness": "만성 질환",
    "housing": "주거 형태",
    "monthly_rent_krw": "월세 금액",
    "caregiver_available": "돌봐 줄 가족·보호자 유무",
    "isolation_signals": "고립 신호",
    "crisis_events": "위기 사건",
    "current_benefits": "받는 중인 제도",
}
STATUS_LABELS = {"eligible": "대상 가능성 높음", "unknown": "확인 필요", "ineligible": "대상 아님"}
_FILLED_PRIORITY = 1000


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _object_particle(word: str) -> str:
    last = word[-1] if word else ""
    if "가" <= last <= "힣":
        return "을" if (ord(last) - 0xAC00) % 28 else "를"
    return "을(를)"


def follow_up_questions(missing_fields: list[str]) -> list[str]:
    """Korean next-visit prompts for missing profile fields, e.g. "월 소득을 확인해야 합니다"."""
    return [f"{field_label(f)}{_object_particle(field_label(f))} 확인해야 합니다" for f in missing_fields]


def coverage_gaps(domain: str, decisions: dict[str, DecisionRecord], schemes: list[Scheme]) -> list[str]:
    """Scheme IDs of the domain that have no decision record yet."""
    decided = {d.scheme_id for d in decisions.values()}
    return [s.id for s in schemes if s.domain == domain and s.id not in decided]


def check_citations(rec: Recommendation, decisions: dict[str, DecisionRecord], domain: str) -> str | None:
    """Return a Korean reason when the recommendation's citations do not match the decision record."""
    if not rec.scheme_id or not rec.decision_id:
        return "제도 ID 또는 판정 ID가 없습니다"
    decision = decisions.get(rec.decision_id)
    if decision is None:
        return f"판정 기록에 없는 판정 ID({rec.decision_id})를 인용했습니다"
    if decision.scheme_id != rec.scheme_id:
        return f"판정 {rec.decision_id}은(는) {rec.scheme_id}가 아니라 {decision.scheme_id}의 판정입니다"
    if decision.domain != domain:
        return f"판정 {rec.decision_id}은(는) 이 분야의 제도가 아닙니다"
    known = {c.id for c in decision.conditions}
    unknown_ids = [c for c in rec.condition_ids if c not in known]
    if unknown_ids:
        return f"판정 기록에 없는 조건 ID({', '.join(unknown_ids)})를 인용했습니다"
    if decision.status == "ineligible":
        return "대상 아님으로 판정된 제도는 추천할 수 없습니다"
    return None


def _default_conditions(decision: DecisionRecord) -> list[str]:
    wanted = {"eligible": True, "unknown": None, "ineligible": False}[decision.status]
    ids = [c.id for c in decision.conditions if c.met is wanted]
    return ids or [c.id for c in decision.conditions]


def _default_explanation(decision: DecisionRecord) -> str:
    if decision.status == "eligible":
        return "규칙 판정에서 조건을 모두 충족했습니다."
    if decision.status == "unknown":
        missing = ", ".join(field_label(f) for f in decision.missing_fields) or "일부 조건"
        return f"확인이 필요한 항목이 있습니다: {missing}."
    unmet = ", ".join(c.label for c in decision.conditions if c.met is False) or "일부 조건"
    return f"충족하지 않는 조건: {unmet}."


def _item_from_decision(decision: DecisionRecord) -> VerifiedItem:
    return VerifiedItem(
        scheme_id=decision.scheme_id,
        scheme_name=decision.scheme_name,
        domain=decision.domain,
        status=decision.status,
        decision_id=decision.decision_id,
        condition_ids=_default_conditions(decision),
        explanation=_default_explanation(decision),
        follow_up_questions=follow_up_questions(decision.missing_fields) if decision.status == "unknown" else [],
        source="verifier" if decision.source == "verifier" else "model",
        missing_fields=list(decision.missing_fields),
    )


def _item_from_recommendation(rec: Recommendation, decision: DecisionRecord) -> VerifiedItem:
    questions = list(rec.follow_up_questions)
    if decision.status == "unknown" and not questions:
        questions = follow_up_questions(decision.missing_fields)
    return VerifiedItem(
        scheme_id=rec.scheme_id,
        scheme_name=decision.scheme_name,
        domain=decision.domain,
        status=decision.status,
        decision_id=rec.decision_id,
        condition_ids=list(rec.condition_ids),
        explanation=rec.explanation,
        follow_up_questions=questions,
        source="model",
        missing_fields=list(decision.missing_fields),
    )


def verify(
    matches: list[MatchResult],
    decisions: dict[str, DecisionRecord],
    audit: dict[str, list[AuditEntry]],
    audit_complete: dict[str, bool],
    schemes: list[Scheme],
) -> VerifiedResult:
    """Apply TRD 3.4 rules 1-5 and 7, then represent every remaining decision."""
    result = VerifiedResult()
    items: dict[str, VerifiedItem] = {}
    priority: dict[str, int] = {}

    for match in matches:
        if match.status == "failed" or match.submission is None:
            if match.domain not in result.failed_domains:
                result.failed_domains.append(match.domain)
            continue
        step = MATCH_STEP[match.domain]
        check_audit = audit_complete.get(step, False)
        if not check_audit and step not in result.audit_rule_skipped:
            result.audit_rule_skipped.append(step)
        received = {e.decision_id for e in audit.get(step, []) if e.decision_id and e.has_result}
        for rec in sorted(match.submission.recommendations, key=lambda r: r.priority):
            reason = check_citations(rec, decisions, match.domain)
            if reason is None and check_audit and rec.decision_id not in received:
                reason = "모델이 도구 결과로 받지 않은 판정을 인용했습니다"
            if reason is None and rec.scheme_id in items:
                reason = "같은 제도를 중복 추천했습니다"
            if reason is not None:
                result.removed.append(
                    RemovedItem(scheme_id=rec.scheme_id, decision_id=rec.decision_id or None, reason=reason)
                )
                continue
            items[rec.scheme_id] = _item_from_recommendation(rec, decisions[rec.decision_id])
            priority[rec.scheme_id] = rec.priority

    latest: dict[str, DecisionRecord] = {}
    for decision in decisions.values():
        latest[decision.scheme_id] = decision
    for scheme_id, decision in latest.items():
        if scheme_id not in items:
            items[scheme_id] = _item_from_decision(decision)
            priority[scheme_id] = _FILLED_PRIORITY

    order = {s.id: i for i, s in enumerate(schemes)}

    def sort_key(item: VerifiedItem) -> tuple[int, int, int, str]:
        return (DOMAINS.index(item.domain), priority[item.scheme_id], order.get(item.scheme_id, len(order)), item.scheme_id)

    for item in sorted(items.values(), key=sort_key):
        getattr(result, item.status).append(item)
    for decision in decisions.values():
        if decision.source == "verifier" and decision.scheme_id not in result.verifier_filled:
            result.verifier_filled.append(decision.scheme_id)
    return result

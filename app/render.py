"""Deterministic rendering of approved documents. Pure functions only."""

from __future__ import annotations

from app.schemas import SECTION_IDS, SECTION_TITLES, DraftDocuments, FinalDocuments, FinalSection, VerifiedResult
from app.verify import STATUS_LABELS, field_label


def referral_schemes_text(verified: VerifiedResult, scheme_ids: list[str]) -> str:
    """One line per approved scheme with its status and cited condition IDs."""
    items = {item.scheme_id: item for item in verified.eligible + verified.unknown}
    lines = []
    for scheme_id in scheme_ids:
        item = items[scheme_id]
        line = f"- {item.scheme_name} ({STATUS_LABELS[item.status]}) / 판정 {item.decision_id}"
        if item.condition_ids:
            line += f" / 근거 조건: {', '.join(item.condition_ids)}"
        if item.status == "unknown" and item.missing_fields:
            line += f" / 확인 필요 항목: {', '.join(field_label(f) for f in item.missing_fields)}"
        lines.append(line)
    return "\n".join(lines)


def render_final(
    draft: DraftDocuments,
    edited_sections: dict[str, str],
    verified: VerifiedResult,
    scheme_ids: list[str],
    now_iso: str,
) -> FinalDocuments:
    """Build the final record and referral. Raises ValueError if scheme_ids leave the verified set."""
    allowed = {item.scheme_id for item in verified.eligible + verified.unknown}
    outside = [s for s in scheme_ids if s not in allowed]
    if outside:
        raise ValueError(f"검증을 통과하지 않은 제도는 확정할 수 없습니다: {', '.join(outside)}")
    drafted = {section.id: section.text for section in draft.sections}
    record: list[FinalSection] = []
    referral: list[FinalSection] = []
    for section_id in SECTION_IDS:
        if section_id == "referral.schemes":
            edited = edited_sections.get(section_id, "").strip()
            generated = referral_schemes_text(verified, scheme_ids)
            text = "\n\n".join(part for part in (edited, generated) if part)
        else:
            text = edited_sections.get(section_id, drafted.get(section_id, ""))
        section = FinalSection(id=section_id, title=SECTION_TITLES[section_id], text=text)
        (record if section_id.startswith("record.") else referral).append(section)
    return FinalDocuments(record=record, referral=referral, scheme_ids=list(scheme_ids), finalized_at=now_iso)

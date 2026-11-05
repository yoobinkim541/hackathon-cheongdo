"""Pure eligibility rules over CaseProfile. Only load_schemes reads a file; no network."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from app.config import DATA_DIR
from app.schemas import CaseProfile, ConditionResult, EligibilityResult, Scheme

# 2026 기준 중위소득(원/월). 보건복지부고시 제2025-135호
# https://www.law.go.kr/LSW//admRulInfoP.do?admRulSeq=2100000262584
MEDIAN_INCOME_2026: dict[int, int] = {
    1: 2_564_238,
    2: 4_199_292,
    3: 5_359_036,
    4: 6_494_738,
    5: 7_556_719,
    6: 8_555_952,
}
MEDIAN_INCOME_SOURCE = "https://www.law.go.kr/LSW//admRulInfoP.do?admRulSeq=2100000262584"

SEVERE_OR_MILD = ("중증", "경증")


def median_income(size: int) -> int:
    """Monthly median income for a household; 7인 이상은 6인 + (6인-5인)×(n-6)."""
    if size < 1:
        raise ValueError("household_size must be >= 1")
    if size <= 6:
        return MEDIAN_INCOME_2026[size]
    step = MEDIAN_INCOME_2026[6] - MEDIAN_INCOME_2026[5]
    return MEDIAN_INCOME_2026[6] + step * (size - 6)


def income_threshold(size: int, percent: int) -> int:
    """Selection threshold in won, truncated (e.g. 1인 32% → 820,556)."""
    return median_income(size) * percent // 100


def _won(value: int) -> str:
    return f"{value:,}원"


# ---------- condition builders ----------

def _cid(scheme: Scheme, name: str) -> str:
    return f"{scheme.id}.{name}"


def _age_min(scheme: Scheme, profile: CaseProfile, minimum: int) -> ConditionResult:
    label = f"나이 {minimum}세 이상"
    if profile.age is None:
        return ConditionResult(id=_cid(scheme, "age"), label=label, met=None)
    met = profile.age >= minimum
    op = "≥" if met else "<"
    return ConditionResult(
        id=_cid(scheme, "age"), label=label, met=met, used_value=f"나이 {profile.age}세 {op} 기준 {minimum}세"
    )


def _income_pct(scheme: Scheme, profile: CaseProfile, percent: int, lower_percent: int | None = None) -> ConditionResult:
    if lower_percent is None:
        label = f"월 소득이 기준 중위소득 {percent}% 이하"
    else:
        label = f"월 소득이 기준 중위소득 {lower_percent}% 초과 {percent}% 이하"
    cid = _cid(scheme, "income")
    income, size = profile.monthly_income_krw, profile.household_size
    if income is None or size is None or size < 1:
        return ConditionResult(id=cid, label=label, met=None)
    upper = income_threshold(size, percent)
    if income > upper:
        return ConditionResult(
            id=cid, label=label, met=False, used_value=f"월 소득 {_won(income)} > 기준 {_won(upper)}({size}인 {percent}%)"
        )
    if lower_percent is not None:
        lower = income_threshold(size, lower_percent)
        if income <= lower:
            return ConditionResult(
                id=cid, label=label, met=False,
                used_value=f"월 소득 {_won(income)} ≤ 하한 {_won(lower)}({size}인 {lower_percent}%)",
            )
        return ConditionResult(
            id=cid, label=label, met=True,
            used_value=f"{_won(lower)} < 월 소득 {_won(income)} ≤ 기준 {_won(upper)}({size}인 {percent}%)",
        )
    return ConditionResult(
        id=cid, label=label, met=True, used_value=f"월 소득 {_won(income)} ≤ 기준 {_won(upper)}({size}인 {percent}%)"
    )


def _income_fixed(scheme: Scheme, profile: CaseProfile) -> ConditionResult:
    """Income against a fixed 선정기준액: params single_max, optional couple_max (부부가구)."""
    single = int(scheme.params["single_max"])
    couple = int(scheme.params.get("couple_max", single))
    label = f"월 소득이 선정기준액 이하(단독 {_won(single)}" + (f", 부부 {_won(couple)})" if couple != single else ")")
    cid = _cid(scheme, "income")
    income = profile.monthly_income_krw
    if income is None:
        return ConditionResult(id=cid, label=label, met=None)
    htype = profile.household_type
    if htype is None:
        # Decidable without household type only at the extremes.
        if income <= min(single, couple):
            return ConditionResult(id=cid, label=label, met=True, used_value=f"월 소득 {_won(income)} ≤ 기준 {_won(min(single, couple))}")
        if income > max(single, couple):
            return ConditionResult(id=cid, label=label, met=False, used_value=f"월 소득 {_won(income)} > 기준 {_won(max(single, couple))}")
        return ConditionResult(id=cid, label=label, met=None)
    limit, kind = (couple, "부부") if htype == "부부" else (single, "단독")
    met = income <= limit
    op = "≤" if met else ">"
    return ConditionResult(id=cid, label=label, met=met, used_value=f"월 소득 {_won(income)} {op} 기준 {_won(limit)}({kind})")


def _living_alone(scheme: Scheme, profile: CaseProfile) -> ConditionResult:
    label = "혼자 사는 가구(독거)"
    cid = _cid(scheme, "living_alone")
    if profile.household_type is None:
        return ConditionResult(id=cid, label=label, met=None)
    return ConditionResult(id=cid, label=label, met=profile.household_type == "독거", used_value=f"가구 유형 {profile.household_type}")

# 긴급복지지원법 제2조의 위기 사유를 가리키는 말. 모델이 뽑은 위기 사건 문구를 코드가 이 목록으로만 판정한다.
CRISIS_KEYWORDS = ("실직", "폐업", "휴업", "사망", "화재", "학대", "폭력", "이혼", "가출", "구금", "단전", "단수", "퇴거", "입원", "중한 질병", "중한 부상")


def _crisis_reason(scheme: Scheme, profile: CaseProfile) -> ConditionResult:
    label = "위기 사유(실직·폐업·주소득자 사망·중한 질병 등)"
    cid = _cid(scheme, "crisis")
    hits = [e for e in profile.crisis_events if any(k in e for k in CRISIS_KEYWORDS)]
    if not hits:
        return ConditionResult(id=cid, label=label, met=None)
    return ConditionResult(id=cid, label=label, met=True, used_value="위기 사건 " + ", ".join(hits))



def _housing_rented(scheme: Scheme, profile: CaseProfile) -> ConditionResult:
    allowed = tuple(scheme.params.get("housing", ("전세", "월세")))
    label = "주거 형태가 " + "·".join(allowed)
    cid = _cid(scheme, "housing")
    if profile.housing is None:
        return ConditionResult(id=cid, label=label, met=None)
    return ConditionResult(id=cid, label=label, met=profile.housing in allowed, used_value=f"주거 형태 {profile.housing}")


def _disability_severe(scheme: Scheme, profile: CaseProfile) -> ConditionResult:
    label = "중증 장애"
    cid = _cid(scheme, "disability")
    if profile.disability is None:
        return ConditionResult(id=cid, label=label, met=None)
    return ConditionResult(id=cid, label=label, met=profile.disability == "중증", used_value=f"장애 정도 {profile.disability}")


def _vulnerable(scheme: Scheme, profile: CaseProfile) -> ConditionResult:
    minimum = int(scheme.params["age_min"])
    label = f"{minimum}세 이상 또는 장애인 포함"
    cid = _cid(scheme, "vulnerable")
    age, dis = profile.age, profile.disability
    if age is not None and age >= minimum:
        return ConditionResult(id=cid, label=label, met=True, used_value=f"나이 {age}세 ≥ 기준 {minimum}세")
    if dis in SEVERE_OR_MILD:
        return ConditionResult(id=cid, label=label, met=True, used_value=f"장애 정도 {dis}")
    if age is not None and dis == "없음":
        return ConditionResult(id=cid, label=label, met=False, used_value=f"나이 {age}세 < 기준 {minimum}세, 장애 없음")
    return ConditionResult(id=cid, label=label, met=None)


# ---------- rules ----------

Rule = Callable[[Scheme, CaseProfile], list[ConditionResult]]


def rule_income_pct(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_income_pct(scheme, profile, int(scheme.params["percent"]))]


def rule_income_pct_range(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_income_pct(scheme, profile, int(scheme.params["percent"]), int(scheme.params["lower_percent"]))]


def rule_income_pct_crisis(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_income_pct(scheme, profile, int(scheme.params["percent"])), _crisis_reason(scheme, profile)]


def rule_income_pct_housing(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_income_pct(scheme, profile, int(scheme.params["percent"])), _housing_rented(scheme, profile)]


def rule_income_pct_vulnerable(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_income_pct(scheme, profile, int(scheme.params["percent"])), _vulnerable(scheme, profile)]


def rule_disability_pension(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [
        _disability_severe(scheme, profile),
        _age_min(scheme, profile, int(scheme.params["age_min"])),
        _income_fixed(scheme, profile),
    ]


def rule_age(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_age_min(scheme, profile, int(scheme.params["age_min"]))]


def rule_age_income(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_age_min(scheme, profile, int(scheme.params["age_min"])), _income_fixed(scheme, profile)]


def rule_age_alone(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [_age_min(scheme, profile, int(scheme.params["age_min"])), _living_alone(scheme, profile)]


def rule_age_alone_income(scheme: Scheme, profile: CaseProfile) -> list[ConditionResult]:
    return [
        _age_min(scheme, profile, int(scheme.params["age_min"])),
        _living_alone(scheme, profile),
        _income_fixed(scheme, profile),
    ]


RULES: dict[str, Rule] = {
    "income_pct": rule_income_pct,
    "income_pct_range": rule_income_pct_range,
    "income_pct_crisis": rule_income_pct_crisis,
    "income_pct_housing": rule_income_pct_housing,
    "income_pct_vulnerable": rule_income_pct_vulnerable,
    "disability_pension": rule_disability_pension,
    "age": rule_age,
    "age_income": rule_age_income,
    "age_alone": rule_age_alone,
    "age_alone_income": rule_age_alone_income,
}


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[Scheme, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(Scheme.model_validate(item) for item in raw)


def load_schemes(path: Path | str = DATA_DIR / "schemes.json") -> list[Scheme]:
    return list(_load(str(path)))


def scheme_by_id(scheme_id: str) -> Scheme | None:
    return {s.id: s for s in _load(str(DATA_DIR / "schemes.json"))}.get(scheme_id)


def schemes_by_domain(domain: str) -> list[Scheme]:
    return [s for s in _load(str(DATA_DIR / "schemes.json")) if s.domain == domain]


def evaluate(scheme: Scheme, profile: CaseProfile) -> EligibilityResult:
    """Order: any known condition false → ineligible; any required field missing → unknown; else eligible."""
    conditions = RULES[scheme.rule](scheme, profile)
    receiving = [b for b in profile.current_benefits if len(b.strip()) >= 3 and (scheme.name in b or b.strip() in scheme.name)]
    if receiving:
        conditions.append(ConditionResult(id=_cid(scheme, "not_receiving"), label="이미 받는 중이 아님", met=False,
                                          used_value="받는 중 " + ", ".join(receiving)))
    missing = [f for f in scheme.required_fields if getattr(profile, f) is None]
    if any(c.met is False for c in conditions):
        status = "ineligible"
    elif missing or any(c.met is None for c in conditions):
        status = "unknown"
        if not missing:
            # Undecided condition on an optional input (e.g. disability for energy_voucher).
            missing = [f for f in scheme.params.get("optional_fields", []) if getattr(profile, f) in (None, [])]
    else:
        status = "eligible"
    return EligibilityResult(
        scheme_id=scheme.id,
        scheme_name=scheme.name,
        domain=scheme.domain,
        status=status,
        conditions=conditions,
        missing_fields=missing,
        source_url=scheme.source_url,
    )

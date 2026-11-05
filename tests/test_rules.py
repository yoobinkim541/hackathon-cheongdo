import json
import re

import pytest

from app import rules
from app.config import DATA_DIR
from app.schemas import PROFILE_RULE_FIELDS, CaseProfile, EvalCase

EXPECTED_IDS = {
    "livelihood_benefit": "living", "housing_benefit": "living", "emergency_livelihood": "living", "energy_voucher": "living",
    "medical_benefit": "health", "copay_reduction": "health", "disability_pension": "health", "health_checkup_visit": "health",
    "basic_pension": "care", "elderly_care_service": "care", "emergency_safety_service": "care", "senior_job_public": "care",
    "lonely_death_prevention": "care",
}


def scheme(sid: str):
    found = rules.scheme_by_id(sid)
    assert found is not None
    return found


def test_all_schemes_load_with_valid_rules():
    schemes = rules.load_schemes()
    assert {s.id: s.domain for s in schemes} == EXPECTED_IDS
    for s in schemes:
        assert s.rule in rules.RULES
        assert set(s.required_fields) <= set(PROFILE_RULE_FIELDS)
        assert s.source_url.startswith("https://")
        assert s.is_example and s.checked_at == "2026-11-05"
    assert len(rules.schemes_by_domain("care")) == 5


def test_median_income_table():
    assert rules.income_threshold(1, 32) == 820_556
    assert rules.median_income(7) == 8_555_952 + (8_555_952 - 7_556_719)


def test_livelihood_boundary_exact_and_one_above():
    s = scheme("livelihood_benefit")
    at = rules.evaluate(s, CaseProfile(household_size=1, monthly_income_krw=820_556))
    assert at.status == "eligible"
    assert at.conditions[0].used_value == "월 소득 820,556원 ≤ 기준 820,556원(1인 32%)"
    above = rules.evaluate(s, CaseProfile(household_size=1, monthly_income_krw=820_557))
    assert above.status == "ineligible"


def test_unknown_when_income_missing():
    r = rules.evaluate(scheme("livelihood_benefit"), CaseProfile(household_size=1))
    assert r.status == "unknown"
    assert r.missing_fields == ["monthly_income_krw"]
    assert r.conditions[0].met is None


def test_ineligible_wins_over_unknown():
    # income missing but age known and too young
    r = rules.evaluate(scheme("basic_pension"), CaseProfile(age=50, household_type="독거"))
    assert r.status == "ineligible"
    assert "monthly_income_krw" in r.missing_fields


def test_copay_range():
    s = scheme("copay_reduction")
    at40 = rules.income_threshold(2, 40)
    at50 = rules.income_threshold(2, 50)
    assert rules.evaluate(s, CaseProfile(household_size=2, monthly_income_krw=at40)).status == "ineligible"
    assert rules.evaluate(s, CaseProfile(household_size=2, monthly_income_krw=at40 + 1)).status == "eligible"
    assert rules.evaluate(s, CaseProfile(household_size=2, monthly_income_krw=at50)).status == "eligible"
    assert rules.evaluate(s, CaseProfile(household_size=2, monthly_income_krw=at50 + 1)).status == "ineligible"


def test_basic_pension_couple_threshold():
    s = scheme("basic_pension")
    assert rules.evaluate(s, CaseProfile(age=70, household_type="부부", monthly_income_krw=3_952_000)).status == "eligible"
    assert rules.evaluate(s, CaseProfile(age=70, household_type="독거", monthly_income_krw=2_470_001)).status == "ineligible"


def test_energy_voucher_optional_disability():
    s = scheme("energy_voucher")
    r = rules.evaluate(s, CaseProfile(age=40, household_size=1, monthly_income_krw=500_000))
    assert r.status == "unknown" and r.missing_fields == ["disability"]
    r = rules.evaluate(s, CaseProfile(age=70, household_size=1, monthly_income_krw=500_000))
    assert r.status == "eligible"


def test_emergency_livelihood_needs_legal_crisis_reason():
    s = scheme("emergency_livelihood")
    base = dict(household_size=1, monthly_income_krw=500_000)
    r = rules.evaluate(s, CaseProfile(**base))
    assert r.status == "unknown" and r.missing_fields == ["crisis_events"]
    r = rules.evaluate(s, CaseProfile(**base, crisis_events=["만성 질환으로 병원비 부담"]))
    assert r.status == "unknown"
    r = rules.evaluate(s, CaseProfile(**base, crisis_events=["공장 폐업으로 실직"]))
    assert r.status == "eligible"
    r = rules.evaluate(s, CaseProfile(household_size=1, monthly_income_krw=5_000_000, crisis_events=["실직"]))
    assert r.status == "ineligible"


def test_scheme_already_received_is_ineligible():
    s = scheme("basic_pension")
    base = dict(age=78, household_type="독거", household_size=1, monthly_income_krw=680_000)
    assert rules.evaluate(s, CaseProfile(**base)).status == "eligible"
    r = rules.evaluate(s, CaseProfile(**base, current_benefits=["기초연금"]))
    assert r.status == "ineligible" and r.conditions[-1].id == "basic_pension.not_receiving"
    assert rules.evaluate(s, CaseProfile(**base, current_benefits=["연금"])).status == "eligible"


@pytest.mark.parametrize("s", rules.load_schemes(), ids=lambda s: s.id)
def test_condition_id_format(s):
    for c in rules.evaluate(s, CaseProfile()).conditions:
        assert re.fullmatch(rf"{s.id}\.[a-z_]+", c.id)


def test_eval_case_expectations_match_rules():
    raw = json.loads((DATA_DIR / "eval_cases.json").read_text(encoding="utf-8"))
    cases = [EvalCase.model_validate(c) for c in raw]
    assert [c.id for c in cases] == [f"case{i}" for i in range(1, 6)]
    for case in cases:
        profile = CaseProfile(**case.expected_profile)
        got = {"eligible": [], "unknown": [], "ineligible": []}
        for s in rules.load_schemes():
            got[rules.evaluate(s, profile).status].append(s.id)
        assert set(got["eligible"]) == set(case.expected_eligible), case.id
        assert set(got["unknown"]) == set(case.expected_unknown), case.id
        assert set(got["ineligible"]) == set(case.expected_ineligible), case.id
        for span in case.pii_spans:
            assert span.text in case.note
        if case.input_type != "text":
            assert case.media_path and case.reference_text == case.note

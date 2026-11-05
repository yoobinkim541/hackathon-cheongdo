---
id: T03
title: 자격 규칙 함수와 제도 데이터
sprint: S1
priority: P0
cut_rank: 0
deps: [T00]
owns: [app/rules.py, data/schemes.json, tests/test_rules.py]
verify: ["python -m pytest -q tests/test_rules.py"]
features: [F4, F5, F6]
flag: null
---

# T03 — 규칙

## 목표

13개 제도의 판정 규칙을 순수 함수로 만들고, 기준값을 담은 `data/schemes.json`을 작성한다. 이 함수만 `eligible`/`ineligible`/`unknown`을 만든다.

## 근거

- TRD 4.1절, 4.2절 전체(제도 ID·조건·선행 판정·단순화)
- 스파인 AD-3(ID), AD-5(판정 순서)
- PRD 6절(제도 13개 고정)

## 계약

- `load_catalog(path) -> SchemeCatalog`: 파일을 읽어 검증한다. 제도가 13개가 아니거나 ID가 AD-3 목록과 다르면 `ValueError`.
- `evaluate(scheme, profile, catalog) -> RuleOutcome`: 순수 함수. 전역 가변 상태 없음.
- `schemes_for(domain, catalog) -> list[Scheme]`.
- `FIELD_QUESTIONS`: 규칙이 읽는 6개 필드마다 다음 방문 질문 1개(예: `monthly_income_krw` → "가구의 월 소득(근로·연금·용돈 포함)은 얼마인가요?").

## 동작

- 판정 순서(AD-5): 알려진 값으로 불충족 조건이 하나라도 있으면 `ineligible` → 아니면 `required_fields` 중 `None`이 있으면 `unknown`(그 필드를 `missing_fields`로) → 아니면 `eligible`.
- 소득 기준: `floor(median_income_krw[min(household_size, 7)] * ratio)` 이하(≤). 8인 이상은 7인 값을 쓰고 `ConditionResult.note`에 적는다.
- 선행 판정(`recipient`, `tier`, `pension`)은 같은 프로필로 선행 제도 `evaluate`를 내부 호출한다. 선행 결과가 `unknown`이면 그 조건도 `met=None`. `used_values`에 선행 제도 ID와 결과를 적는다.
- 장애인연금·기초연금의 가구 구분: 독거 → 단독, 부부 → 부부 기준액, 그 밖 → `unknown`.
- `condition_id`는 `{scheme_id}.{접미사}`. 접미사는 TRD 4.2의 이름(`income`, `housing`, `age`, `recipient`, `vulnerable`, `target`, `tier`, `pension`, `living_alone`, `disability`)을 쓴다.
- `schemes.json` 기준값은 TRD 4.2의 출처에서 가져오고 `source_url`·`checked_at`을 채운다. 모든 항목 `is_example: true`.

## 수용 기준(테스트)

1. `load_catalog()`가 13개 제도를 읽고, 분야별 개수가 4·4·5다.
2. 1인 가구 월 소득이 생계급여 기준액과 같으면 `eligible`, 1원 많으면 `ineligible`(경계값).
3. 소득 `None`, 나이 70인 1인 가구: 생계급여 `unknown`, `missing_fields == ["monthly_income_krw"]`.
4. 나이 40(알려진 불충족) + 소득 `None`: 기초연금 `ineligible`(`ineligible` 우선).
5. 에너지바우처: 생계급여 `eligible`이고 나이 70이면 `eligible`. 생계급여가 `unknown`이면 `unknown`.
6. 노인일자리: 기초연금 `unknown`이면 `unknown`, `used_values`에 `basic_pension`이 있다.
7. 가구 유형 `조손`의 장애인연금 소득 조건은 `met=None`.
8. 8인 가구는 7인 기준을 쓰고 `note`가 비어 있지 않다.
9. 모든 `ConditionResult.id`가 `{scheme_id}.` 접두사를 가진다.
10. `FIELD_QUESTIONS`의 키가 규칙 필드 6개와 같다.
11. `conftest.profile_case1`로 13개 제도를 평가하면 예외 없이 13개 결과가 나온다.

## 하지 않는 것

- `decision_id` 발급(T06 `record_decision`), 재산 환산, 위기 사유·고립 신호 판정(규칙이 읽지 않는다).

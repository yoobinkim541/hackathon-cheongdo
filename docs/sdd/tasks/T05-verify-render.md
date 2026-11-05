---
id: T05
title: 근거 검증과 확정 문서 조립
sprint: S1
priority: P0
cut_rank: 0
deps: [T00, T03]
owns: [app/verify.py, app/render.py, tests/test_verify.py, tests/test_render.py]
verify: ["python -m pytest -q tests/test_verify.py tests/test_render.py"]
features: [F5, F6, F8]
flag: null
---

# T05 — 검증·확정

## 목표

Verifier 대조 규칙 1~8과 확정 문서 템플릿을 순수 함수로 만든다. 이 두 파일은 모델·MAF·네트워크를 모른다.

## 근거

- TRD 3.4절 규칙 1~8, 3.5절 4·6번
- 스파인 AD-1(세 함수 분리), AD-6(Verifier 순서), AD-13
- TRD 9절 "인쇄 문서" 순서

## 계약

- `coverage_gaps(decisions, catalog, domains) -> list[str]`: `domains` 분야의 제도 중 `decisions`에 판정 기록이 없는 `scheme_id`(카탈로그 순서).
- `check_citations(rec, decisions, domain) -> str | None`: 규칙 1~3을 한 추천에 적용하고 어긋나면 사람이 읽을 이유 문자열. 그 분야 제도가 아니면 거부. `submit_matches`(T09)와 `verify()`가 같은 함수를 쓴다.
- `verify(matches, decisions, audit, catalog) -> VerifiedResult`
  - 규칙 1~4: `check_citations` 실패 → `removed`(이유 포함).
  - 규칙 5: `unknown` → `needs_check`.
  - 규칙 6은 여기서 하지 않는다(실행기가 `coverage_gaps` 결과로 판정을 채운 뒤 호출한다). 다만 `source="verifier"` 판정은 추천이 없어도 해당 분류에 `VerifiedItem`으로 넣고 `supplemented`에 ID를 적는다.
  - 규칙 7: `audit[step].complete`이면 추천의 `decision_id`가 `audit[step].entries`에 있어야 한다. 불완전하면 그 단계는 건너뛰고 `audit_rule_skipped`에 단계 이름.
  - 규칙 8: `needs_check` 항목에 질문이 없으면 `missing_fields`마다 `rules.FIELD_QUESTIONS`의 질문을 넣는다.
  - `failed_domains`: `status="failed"`인 `MatchResult`의 분야.
  - 같은 `scheme_id`가 여러 번 나오면 첫 유효 추천만 쓴다.
  - 분류 안의 순서는 추천의 `priority` 오름차순, 없으면 카탈로그 순서.
- `render_final(draft_snapshot, edited_sections, verified, scheme_ids) -> FinalDocuments`
  - `edited_sections` 키가 `SectionId`가 아니면 `ValueError`, `scheme_ids`가 `verified.eligible ∪ needs_check`의 부분집합이 아니면 `ValueError`.
  - 결과 구획 = 스냅샷 구획을 `edited_sections`로 덮어쓴 것. 순서는 TRD 9절(상담기록지 5개 → 의뢰서 4개).
  - `referral.schemes` 구획 끝에 각 제도의 근거 조건 ID 목록을 코드가 덧붙인다(모델 문장과 구분).
  - `finalized_at`은 인자로 받지 않고 호출자가 넘긴 시각이 아니라 `datetime.now(timezone.utc)`. 테스트는 이 필드를 비교하지 않는다.

## 수용 기준(테스트)

1. 판정 기록에 없는 `decision_id` 인용 → `removed`, 이유에 ID가 있다.
2. 기록의 결과가 `eligible`인데 추천이 `unknown` → `removed`.
3. 기록에 없는 `condition_id` → `removed`.
4. 다른 분야 제도를 인용한 추천 → `check_citations`가 이유를 돌려준다.
5. 감사 기록 완결 + 모델이 받지 않은 `decision_id` → `removed`. 같은 상황에서 `complete=False` → 유지되고 `audit_rule_skipped`에 단계.
6. `source="verifier"` 판정은 규칙 7 대상이 아니고 `supplemented`에 있다.
7. 질문 없는 `unknown` 항목에 `FIELD_QUESTIONS` 질문이 하나 이상 들어간다.
8. 실패한 분야가 `failed_domains`에 있다.
9. `render_final`: 허용되지 않은 구획 키 → `ValueError`. 통과 집합 밖 `scheme_ids` → `ValueError`. 정상 입력이면 9개 구획이 TRD 9절 순서로 나온다.
10. 스냅샷 생성 뒤 원본 `DraftDocuments`를 바꿔도 `render_final` 결과는 스냅샷 기준이다.

## 하지 않는 것

- 판정 기록 추가(실행기·T06), 이벤트 발행, HTML 인쇄 화면(T19).

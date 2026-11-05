---
id: T19
title: UI 결과·근거 패널, 초안 편집, 승인 창, 인쇄 문서
sprint: S2
priority: P0
cut_rank: 0
deps: [T08]
owns: [app/static/js/results.js, app/static/js/drafts.js, app/static/print.css, tests/test_static_results.py]
verify: ["python -m pytest -q tests/test_static_results.py"]
features: [F5, F6, F7, F8]
flag: null
---

# T19 — UI 결과·승인

## 목표

결과 구획(제도 분류, 근거 패널, 검증에서 제외됨), 초안 구획별 편집·되돌리기, 승인 창, 확정 문서 인쇄 화면을 만든다.

## 근거

- PRD 3절 4~6번, 7절
- TRD 9절 "결과", "초안 수정", "승인 거부", "인쇄 문서", 3.5절
- 스파인 AD-3 구획 ID

## 계약

- `results.js` `mount(ctx)`: `verified` 이벤트로 세 분류("자격 충족", "확인 필요", "해당 없음(이유)")를 그리고, 항목을 누르면 충족·미충족 조건, `used_values`, 출처 링크, `decision_id`를 펼친다. `removed`는 "검증에서 제외됨" 목록, `supplemented`는 "규칙으로 보완" 배지, `failed_domains`는 분야 경고. 모든 모델 설명 문장에 "AI 초안" 배지, 판정에는 "규칙 판정" 배지.
- `drafts.js` `mount(ctx)`: `draft` 이벤트로 9개 구획을 `<textarea>`로 보인다. 구획마다 "되돌리기"(AI 초안으로). 바뀐 구획만 모아 `edited_sections`. "의뢰서 확정" → `approval_required` 내용(문서 2종, 포함 제도)을 보여 주는 `<dialog>` → 승인·거부 → `api.sendApproval(runId, {request_id, approved, edited_sections})`. `finalized` → 인쇄 화면(`print.css`), `approval_kept` → "초안" 배지와 "확정 취소됨". 409 응답이면 "이미 처리된 승인 요청" 안내.
- 확정 전 초안에는 "AI 초안" 워터마크, 확정 문서에는 없다.

## 동작

- 승인 창은 키보드로 열고 닫힌다(`Esc`, 포커스 가두기). 첫 포커스는 "거부"(위험한 작업 전 확인).
- 재생 모드에서도 같은 흐름이다(서버가 처리).

## 수용 기준(정적 검사)

1. `drafts.js`에 9개 구획 ID 문자열이 모두 있다.
2. `drafts.js`가 `sendApproval`을 쓰고 `edited_sections`를 보낸다.
3. `results.js`에 "검증에서 제외됨", "AI 초안", "규칙 판정", "확인 필요" 문자열이 있다.
4. `<dialog>`(또는 `role="dialog"`)과 `aria-modal`이 있다.
5. `print.css`에 `@media print`가 있다.

## 하지 않는 것

- 타임라인(T08), 후속 질문 칩(T17), 평가 화면(T15).

---
id: T18
title: 거부 뒤 같은 실행에서 다시 승인 요청
sprint: S3
priority: P1
cut_rank: 6
deps: [T12]
owns: [app/executors/gate.py, tests/test_gate.py]
verify: ["python -m pytest -q tests/test_gate.py tests/test_workflow.py"]
features: [F8]
flag: ENABLE_REAPPROVAL
---

# T18 — 재승인

## 목표

`ENABLE_REAPPROVAL`이 참이면, 담당자가 거부한 뒤 초안을 더 고쳐 같은 실행에서 다시 확정할 수 있게 `ReferralGate`가 승인 요청을 다시 건다.

## 근거

- TRD 3.5절 4번(재요청과 대안 간선)
- 스파인 AD-13 "거부", Open Questions 1행
- T01 결과 Q1

## 계약

- `@response_handler` 거부 분기: `approval_kept`를 낸 뒤, 플래그가 참이면 같은 핸들러에서 `ctx.request_info(ApprovalRequest(... draft_snapshot=거부 시점 스냅샷에 edited_sections를 반영한 것))`를 다시 건다.
- T01 Q1이 "안 됨"이면 이 태스크는 대안 없이 플래그를 꺼진 채로 두고 `done`한다(문서의 "하지 않는 것"으로 처리). 대안 간선은 만들지 않는다(시간 대비 가치가 낮다).

## 수용 기준(테스트)

1. 플래그 참: 거부 → `approval_kept` → 새 `request_info`(다른 `request_id`) → 승인 → `finalized`.
2. 두 번째 요청의 스냅샷에 첫 거부 때 보낸 `edited_sections`가 반영돼 있다.
3. 플래그 거짓: 거부 → `approval_kept` 하나로 끝나고 새 요청이 없다.
4. `tests/test_workflow.py`가 여전히 통과한다.

## 하지 않는 것

- 상태 전이(T12가 `request_info` 이벤트를 보고 `awaiting_approval`로 돌린다).

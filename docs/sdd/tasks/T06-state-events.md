---
id: T06
title: 실행 상태 레지스트리와 이벤트 로그
sprint: S1
priority: P0
cut_rank: 0
deps: [T00]
owns: [app/runs.py, app/events.py, tests/test_runs.py, tests/test_events.py]
verify: ["python -m pytest -q tests/test_runs.py tests/test_events.py"]
features: [F1, F8, F10, F11]
flag: null
---

# T06 — 상태·이벤트

## 목표

실행 상태(`RunState`, `EvalState`)와 유일한 레지스트리 `REGISTRY`, 실행별 이벤트 로그(`EventLog`)와 MAF 이벤트 → SSE 이벤트 변환기를 만든다.

## 근거

- 스파인 AD-4(필드와 쓰는 주체, 동기 메서드), AD-8(매퍼·이벤트 로그·SSE), AD-13(`claim_approval`), AD-14(TTL·정리 두 단계), 실행 상태 다이어그램
- TRD 3.2절 "실행 상태", 5절 표 5와 SSE 봉투

## 계약

- `RunState` 필드: `run_id`, `case_id`, `source`, `mode`, `purpose`(`live`·`eval`), `status`, `created_at`, `last_active`, `pending_request_id`, `pending_request`(`ApprovalRequest`), `runtime`(워크플로·태스크, 임의 객체), `timings: dict[Step,int]`, `masked_note`, `pii_map`, `transcript`, `clean_note`, `profile`, `decisions: list[DecisionRecord]`, `match_submissions: dict[Domain, MatchSubmission]`, `submit_rejects: dict[Step,int]`, `verified`, `draft`, `final_documents`, `sessions: dict[Step, object]`, `audit: dict[Step, StepAudit]`, `usage: dict[Step, UsageData]`, `log: EventLog`, `ask_busy: bool`.
- 메서드(모두 동기, 내부 `await` 없음):
  - `record_decision(outcome, domain, source) -> DecisionRecord`: `d1`, `d2`… 발급, 추가만 한다.
  - `decision(decision_id) -> DecisionRecord | None`
  - `set_status(new)`: 상태도에 없는 전이는 `ValueError`.
  - `claim_approval(request_id) -> bool`: `pending_request_id`와 같으면 비우고 `resuming`으로 바꾸고 `True`. 아니면 `False`.
  - `replace_session(step)`: `sessions[step]`을 지운다(다음 `call_agent`가 새로 만든다).
  - `touch()`: `last_active` 갱신.
- `Registry`: `create_run(**kw) -> RunState`, `get(run_id)`, `create_eval() -> EvalState`, `get_eval(eval_id)`, `index_session(session_id, run_id)`, `by_session(session_id)`, `evict(now) -> list[RunState]`, `clear()`, `on_evict: Callable[[RunState], Awaitable] | None`. `REGISTRY = Registry()`는 모듈에 하나.
- `EventLog`: `append(ev: UiEvent, *, run_id, mode, trace_id) -> Envelope`(단조 증가 `seq`, `ts` UTC ISO 8601), `read_after(seq) -> list[Envelope]`, `async wait(after_seq, timeout) -> list[Envelope]`, `close(status)`(이후 `append`는 `done` 하나만 허용, 이미 닫혔으면 무시), `closed`, `mode`(첫 `append`의 모드로 고정, 다른 모드 `append`는 `ValueError`).
- `map_workflow_event(ev) -> list[UiEvent]`: AD-8 규칙 그대로. 알 수 없는 이벤트는 빈 목록.
- `map_agent_update(update, step, ask_id=None) -> list[UiEvent]`: 텍스트 → `token{text}`, `function_call` → `tool_call{tool,args}`, `function_result` → `tool_result{tool,decision_id?}`(결과에 `decision_id`가 있으면 꺼낸다), usage → `usage{input,output}`. `ask_id`가 있으면 `data`에 넣는다.
- `to_sse(env) -> str`: `id: {seq}\nevent: {type}\ndata: {json}\n\n`.

## 동작

- `evict(now)`: 마지막 활동 30분이 지났고 진행 중 상태(`queued`·`running`·`resuming`·`replaying`)가 아니면, 또는 생성 45분이 지났으면 색인에서 빼고 `log.close("expired")`를 부른 뒤 지운 목록을 돌려준다. `on_evict`는 호출하지 않는다(비동기 정리는 T12가 돌려받은 목록으로 한다).
- `EvalState`: `eval_id`, `created_at`, `log`, `cases: list[CaseMetrics]`, `status`.

## 수용 기준(테스트)

1. `record_decision` 세 번 → `d1`, `d2`, `d3`, `decisions` 길이 3.
2. `set_status`: `queued→running→awaiting_approval→resuming→finalized` 통과. `queued→finalized`는 `ValueError`.
3. `claim_approval`: 맞는 ID는 한 번만 `True`, 두 번째는 `False`(이중 제출). 틀린 ID는 `False`.
4. `EventLog`: `seq`가 1부터 단조 증가, `read_after(2)`가 3번부터. 닫은 뒤 `done` 외 `append`는 무시되고 `done`은 한 번만.
5. `wait`가 새 이벤트 도착 시 즉시 돌아오고, 없으면 시간 초과 뒤 빈 목록.
6. 한 로그에 `live` 뒤 `replay` 이벤트 → `ValueError`.
7. `evict`: 31분 지난 `awaiting_approval` 실행은 지워지고 로그가 `expired`로 닫힌다. 31분 지난 `running`은 남는다. 46분 지난 `running`은 지워진다.
8. `map_workflow_event`: `UiEvent` 데이터는 그대로, `executor_invoked`는 `step_started`(`data == {}`), `request_info`는 `approval_required`. 원본 `.data`가 결과에 들어가지 않는다.
9. `map_agent_update`: 텍스트·도구 호출·도구 결과(`decision_id` 추출)·usage가 각각 맞는 타입으로 바뀐다.
10. `to_sse` 출력이 봉투 형식과 같다.

## 하지 않는 것

- 상태 전이 판단(언제 바꿀지는 T12), SSE HTTP 응답(T12), 재생(T14).

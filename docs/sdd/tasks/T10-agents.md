---
id: T10
title: 에이전트 6개, 권한·도구 노출, call_agent, 관측 기본
sprint: S2
priority: P0
cut_rank: 0
deps: [T01, T09]
owns: [app/agents.py, app/context.py, app/telemetry.py, tests/fakes.py, tests/test_agents.py, tests/test_call_agent.py]
verify: ["python -m pytest -q tests/test_agents.py tests/test_call_agent.py"]
features: [F3, F4, F7, F9, F14]
flag: null
---

# T10 — 에이전트

## 목표

공유 `CopilotClient` 하나에 붙는 `GitHubCopilotAgent` 6개를 만들고, 모든 에이전트 호출이 거치는 `call_agent`(시간 제한·재시도·오류 분류·감사 기록)를 구현한다. `StepTimingMiddleware`와 텔레메트리 설정도 여기서 한다.

## 근거

- TRD 2절(공유 클라이언트), 3.6절 전체, 3.8절 미들웨어, 7절 첫 문단
- 스파인 AD-10 `call_agent`, AD-12 허용 목록
- `docs/reference/copilot-sdk.md`, `docs/reference/agent-framework.md`
- T01 결과 Q2·Q3·Q4·Q5

## 계약

- `TOOL_ALLOWLIST`: AD-12 표 그대로(단계 이름 → 도구 이름).
- `make_permission_handler(step)`: 요청 종류가 `custom-tool`이고 도구 이름이 허용 목록에 있으면 `PermissionDecisionApproveOnce()`, 아니면 `PermissionDecisionReject`. 거부는 span 속성·로그에 남긴다. 실행 상태를 조회하지 않는다.
- `build_agents(client, settings) -> dict[Step, agent]`: `normalizer`, `profiler`, `match_living`, `match_health`, `match_care`, `documenter`. 각각 `default_options`에 `model`, `reasoning_effort`(지원할 때만), `system_message={"mode":"replace","content":INSTRUCTIONS[step]}`(Q5 실패면 `customize`), `available_tools=["custom:"+n for n in TOOL_ALLOWLIST[step]]`, `on_permission_request`. 미들웨어 `StepTimingMiddleware`. 훅·컨텍스트 공급자는 T16이 붙인다(이 태스크는 붙일 자리만 둔다).
- `call_agent(agent, prompt, run, step, *, emit, phase="workflow") -> AgentCallResult`:
  - `InvocationKwargs(run_id, step, phase)`를 `function_invocation_kwargs`로 넘기고 `session=run.sessions[step]`(없으면 새로 만들어 넣는다).
  - `asyncio.timeout(AGENT_TIMEOUT_S)` 안에서 `agent.run(prompt, stream=True, ...)`의 갱신마다 `await emit(update)`.
  - 갱신의 `function_call`·`function_result`로 `run.audit[step]`을 쌓는다(호출 수 ≠ 결과 수면 `complete=False`).
  - 시도는 최대 `AGENT_MAX_ATTEMPTS`(2). 시간 초과·예외·제출 도구 미호출(`step`의 제출 도구가 이번 시도에서 한 번도 성공하지 않음)이면 `client.delete_session(service_session_id)` → `run.replace_session(step)` → `emit(UiEvent("step_retry", step, {attempt, reason}))` → 다시.
  - 오류 분류: 메시지·상태 코드에 429·rate·quota → `rate_limit`, 시간 초과 → `timeout`, 제출 없음 → `tool_missing`, 나머지 `other`.
  - `asyncio.CancelledError`는 잡지 않는다.
- `StepTimingMiddleware`: 실행마다 span 속성 `app.run_id`, `app.step`, `app.mode`를 달고 소요 ms를 `run.timings[step]`, usage를 `run.usage[step]`에 기록.
- `telemetry.setup(settings)`: 연결 문자열이 있으면 `configure_azure_monitor()` 뒤 MAF `enable_instrumentation(enable_sensitive_data=False)`. 없으면 아무것도 하지 않는다. `span()`, `current_trace_id()`.
- `tests/fakes.py`: T00이 만든 가짜를 `call_agent` 테스트에 맞게 확장한다(시간 초과 흉내, 예외 흉내, 도구 호출 흉내).

## 수용 기준(테스트, 네트워크 없음)

1. 권한 처리기: `match_living` 처리기가 `custom-tool`/`check_eligibility`는 승인, `custom-tool`/`submit_draft`·`shell`·`write`·`url`은 거부.
2. `build_agents(FakeCopilotClient, settings)`가 6개를 만들고, 각 `available_tools`가 `TOOL_ALLOWLIST`와 같다.
3. 모든 에이전트의 `system_message.mode`가 `replace`(또는 T01 Q5 결과에 따른 `customize`).
4. `call_agent`: 첫 시도 시간 초과 → `delete_session` 호출, `step_retry` 1회 emit, 두 번째 성공 → `ok=True, attempts=2`.
5. 두 번 다 실패 → `ok=False`, 분류가 맞다(429 메시지 → `rate_limit`).
6. 제출 도구를 부르지 않는 가짜 → `tool_missing`.
7. 도구 호출 2개·결과 1개 → `run.audit[step].complete is False`.
8. `function_invocation_kwargs`에 `run_id`, `step`, `phase`가 들어간다.
9. 취소 시 `CancelledError`가 그대로 올라간다.

## 하지 않는 것

- 세션 훅·`VerifiedDecisionsProvider`(T16), 실행기(T11), 실제 Copilot 호출(G1 배포 확인에서 본다).

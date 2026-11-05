---
id: T16
title: VerifiedDecisionsProvider와 Copilot 세션 훅
sprint: S3
priority: P1
cut_rank: 9
deps: [T12]
owns: [app/context.py, app/agents.py, tests/test_context.py, tests/test_hooks.py]
verify: ["python -m pytest -q tests/test_context.py tests/test_hooks.py tests/test_agents.py tests/test_call_agent.py"]
features: [F7, F9]
flag: ENABLE_CONTEXT_PROVIDER
---

# T16 — 공급자·훅

## 목표

두 MAF·SDK 기능을 플래그 뒤에 붙인다. (1) `ENABLE_CONTEXT_PROVIDER`: Documenter 실행 전 같은 실행의 검증 통과 판정 목록을 지시문에 덧붙이는 `ContextProvider`. (2) `ENABLE_SESSION_HOOKS`(cut_rank 8): 관측 전용 `on_post_tool_use`·`on_error_occurred` 훅.

## 근거

- TRD 3.6절 "세션 훅", 3.8절 공급자
- 스파인 AD-12(훅은 관측 전용, `on_pre_tool_use` 금지, 상태 조회 금지)
- `docs/reference/agent-framework.md`(ContextProvider `before_run`)

## 계약

- `VerifiedDecisionsProvider.before_run(...)`: 호출 문맥의 `run_id`로 `run.verified`를 찾아 제도 ID·결과·`decision_id`·확인 필요 필드를 짧은 표로 만든다. 실행이 없거나 `verified`가 없으면 아무것도 덧붙이지 않는다. 이 공급자는 상태를 읽기만 한다.
- `build_agents`: `ENABLE_CONTEXT_PROVIDER`면 Documenter에 공급자를 붙인다. 꺼져 있으면 T11의 "프롬프트에 직접 넣기" 경로가 쓰인다(두 경로가 동시에 판정 목록을 넣지 않게 Documenter 실행기는 플래그를 보고 `decisions_text`를 `None`으로 넘긴다 — T11이 이미 그렇게 했는지 확인하고, 안 되어 있으면 요청을 낸다).
- 훅: `ENABLE_SESSION_HOOKS`면 `default_options["hooks"] = {"on_post_tool_use": ..., "on_error_occurred": ...}`. `on_post_tool_use`는 도구 이름과 결과의 `decision_id`를 현재 span 속성에, `on_error_occurred`는 `errorContext`와 오류 종류를 span 속성·로그에. 실행 상태를 조회하거나 바꾸지 않는다.

## 수용 기준(테스트)

1. 공급자: `verified`가 있는 실행 → 덧붙인 지시문에 통과 판정의 `decision_id`가 모두 있고, `removed` 항목의 ID는 없다.
2. 공급자: 실행 없음 → 덧붙임 없음, 예외 없음.
3. 플래그 꺼짐 → Documenter에 공급자가 없다. 켜짐 → 있다.
4. 훅 플래그 꺼짐 → `default_options`에 `hooks`가 없다. 켜짐 → 두 키만 있고 `on_pre_tool_use`가 없다.
5. 훅 함수가 `REGISTRY`를 조회하지 않는다(가짜 레지스트리 호출 수 0).
6. T10 테스트(`test_agents.py`, `test_call_agent.py`)가 여전히 통과한다.

## 배포 확인(G2)

- 플래그를 켠 배포에서 사례 1 초안이 생성되고, Application Insights trace에 `decision_id` span 속성이 보인다(훅 켰을 때).

## 하지 않는 것

- 감사 기록(이미 `call_agent`가 스트림에서 만든다), 승인 훅.

---
title: 'Adversarial review — ARCHITECTURE-SPINE (동행노트 백엔드)'
reviewer: adversary
target: ../ARCHITECTURE-SPINE.md
inputs: [TRD.md, SPEC.md, docs/reference/agent-framework.md, docs/reference/copilot-sdk.md]
date: '2026-11-05'
verdict: '조건부 불합격 — AD 문구를 모두 지켜도 서로 맞물리지 않는 구현 쌍이 최소 6곳 생긴다. 아래 Critical·High 7건을 AD로 닫기 전에는 병렬 작업을 시작하면 안 된다.'
---

# 적대적 아키텍처 검토 — 동행노트 백엔드 스파인

## 0. 방법과 판정

검토 방식: 한 단계 아래 단위(모듈·함수·실행 경로) 두 개를 골라, 두 팀원이 **모든 AD를 문자 그대로 지키면서** 각자 합리적으로 만들었을 때 서로 맞지 않는 구현이 나오는지 만들어 본다. 라이브러리 동작은 `docs/reference/*.md`의 확인 결과만 근거로 쓰고, 문서에 없는 것은 `[미확인]`으로 표시한다.

**판정:** 층 구조(AD-1), 스키마 단일 소유(AD-2), 판정 단일화(AD-5), 확정 경로(AD-13)는 견고하다. 그러나 스파인은 "누가 쓰는가"는 정했지만 "**언제·어떤 키로 찾는가**"와 "**누가 누구를 어떤 시그니처로 부르는가**"를 비워 두었다. 그 결과 (1) 훅이 실행을 찾지 못하는 경합, (2) `call_agent`와 스트리밍 `yield_output`의 시그니처 불일치, (3) 매칭 결과의 이중 경로와 `verify()` 시그니처 누락, (4) 실행 중 재생 전환 시 이벤트·상태 혼합, (5) 승인 재개 경합과 상태 전이 주체 부재, (6) `/ask`가 승인 대기 중 초안을 바꿀 수 있는 경로가 열려 있다.

### 요약 표

| # | 구멍 | 충돌 단위 쌍 | 심각도 |
|---|---|---|---|
| H1 | 훅·권한 처리기의 `sessionId`→실행 조회 경합 | `agents.py` 훅 ↔ `runs.py` 색인 ↔ `workflow.py` 실행기 | **Critical** |
| H2 | `call_agent` ↔ 실행기 스트리밍 계약 불일치 | `agents.call_agent` ↔ `workflow.*Executor` ↔ `service.ask` | **High** |
| H3 | 매칭 결과 이중 경로, `verify()` 시그니처에 프로필 없음, 규칙 6의 판정 ID 발급 | `tools.submit_matches` ↔ `workflow.MatchExecutor/VerifierExecutor` ↔ `verify.py` | **High** |
| H4 | 실행 중 재생 전환(`running → replaying`) | `service` 재생 ↔ 진행 중 워크플로 ↔ `EventLog` ↔ UI | **High** |
| H5 | 승인 재개 경합, 상태 전이 호출 주체 부재 | `main`/`service.respond` ↔ 서비스 소비 루프 ↔ `ReferralGate` ↔ `runs` | **High** |
| H6 | `/ask`가 Documenter 세션으로 `submit_draft`를 호출해 승인 대기 초안을 바꿈, `/ask` 이벤트 경로 미정 | `service.ask` ↔ `tools.submit_draft` ↔ `ReferralGate` ↔ `main` SSE | **High** |
| H7 | 재생 파일: 기록 ↔ 재생의 형식·상태 복원 불일치 | 기록 스크립트 ↔ `service` 재생 ↔ 승인 템플릿 | **High** |
| H8 | 30분 TTL이 진행 중 실행·SSE를 지움 | `RunRegistry` TTL ↔ 백그라운드 태스크 ↔ SSE 핸들러 ↔ 도구 | Medium-High |
| H9 | 평가가 실시간 세마포어·재생 전환·완료 조건과 충돌 | `service.start_eval` ↔ `service.start` ↔ 세마포어 | Medium-High |
| H10 | 레지스트리 접근 경로·`function_invocation_kwargs` 형식·동기 함수 원자성 전제 | `tools.py` ↔ `runs.py` ↔ `context.StepTimingMiddleware` ↔ `service` | Medium |
| H11 | 이벤트 매퍼 입력 타입·`W_OutT` 선언·게이트 출력 구분 | `workflow` 실행기 ↔ `events.map_workflow_event` | Medium |
| H12 | `sessions` 필드 쓰기 주체 3곳, RunState의 MAF 객체 보관 위치 | `call_agent` ↔ 실행기 ↔ 미들웨어 ↔ `service` | Medium |
| H13 | 제출 도구의 "새 숫자" 검사 기준 원문 미정 | `tools.submit_matches/submit_draft` ↔ 프롬프트 ↔ `schemes.json` | Medium |
| H14 | SSE 종료·heartbeat·`done` 위치 | `main` SSE ↔ `service` 소비 루프 ↔ UI `EventSource` | Medium |
| H15 | ID 어휘 공백: 분야 ID, 라우터 단계, `/ask` 단계 | `data/schemes.json` ↔ `tools.search_schemes` ↔ AD-3 | Medium |
| H16 | `schemas.py` 최초 작성자 경합, 새 모듈 층 배정 규칙 없음 | 모든 팀원 | Medium |
| H17 | Copilot CLI 세션 상태가 디스크에 남음(AD-14와 모순) | `agents.py` 클라이언트 ↔ AD-14 | Medium |
| H18 | `/ask` 가리기와 `pii_map` 단일 쓰기 충돌 | `service.ask` ↔ `masking.mask` ↔ AD-4 | Low-Medium |
| H19 | 상태도 누락 전이와 TRD 충돌(Profiler 실패 → 재생) | `runs` 상태도 ↔ TRD 표 2 ↔ `service` | Low-Medium |

---

## H1. 훅·권한 처리기의 `sessionId` → 실행 조회 경합 — **Critical**

**충돌 단위:** `agents.py`의 `on_post_tool_use`·`on_error_occurred`(앱 시작 시 1회 생성, 모든 실행 공유) ↔ `runs.py`의 `sessionId` 색인(AD-4) ↔ `workflow.py` 에이전트 실행기.

**라이브러리 사실:**
- 훅 입력에는 `sessionId`만 있고 앱 kwargs가 없다(copilot-sdk.md 3.8).
- `AgentSession.service_session_id`는 MAF가 `agent.run()` **안에서** `create_session`을 끝낸 뒤에 채운다(agent-framework.md 2.2-3). 실행기는 스트림의 첫 갱신을 받기 전까지 이 ID를 볼 수 없다.
- SDK 훅·도구 처리기는 CLI 이벤트 디스패치에서 호출되고, 실행기의 `async for`는 큐를 통해 갱신을 받는다. 순서 보장이 없다.

**어긋나는 구현:**
- 팀원 A(workflow): 첫 갱신을 받은 뒤 `registry.index_session(run.sessions[step].service_session_id, run_id)`를 호출. AD-4 위반 없음.
- 팀원 B(agents): `on_post_tool_use`에서 `registry.by_session(input["sessionId"])`로 실행을 찾고 없으면 무시. AD-4 위반 없음.
- 결과: 매칭 에이전트가 첫 턴에 바로 `search_schemes`→`check_eligibility`를 부르면 첫 몇 건의 훅이 색인 등록보다 먼저 실행되어 **감사 기록이 일부만** 남는다. TRD 3.4 규칙 7은 "감사 기록이 비면 건너뛴다"만 정했으므로, 부분 감사 기록이면 **모델이 실제로 받은 판정을 인용한 정상 추천이 제거**된다. 근거 일치율 100% 지표와 재현율이 동시에 깨진다.
- 같은 경합이 `on_error_occurred`에도 있다. `rate_limit` 기록이 사라지면 `call_agent`의 오류 분류가 `other`가 되고, AD-10의 "데모 사례 rate_limit → 재생 전환"이 일어나지 않는다. F11(필수)이 시연 중에 동작하지 않는다.
- 권한 처리기도 같은 문제다. AD-12는 "공통 `on_permission_request`"라고 했지만, 처리기 입력은 `(request, {"session_id"})`뿐이라 **어느 단계의 허용 목록을 적용할지 알 수 없다.** 팀원은 결국 6개 단계 허용 목록의 합집합으로 검사하게 되고, 매칭 에이전트가 `submit_draft` 권한을 승인받는 구성이 AD-12 문구상 허용된다(숨김은 `available_tools`가 막지만, 거부·숨김 이중 방어라는 AD-12의 목적이 무너진다).

**닫는 AD (AD-12 강화 + 신규 AD-16):**

> ### AD-16 — 실행별 콜백은 클로저로 주입한다 [PROPOSED]
> - **Binds:** agents, tools, runs, workflow, service, F5 규칙 7, F11
> - **Prevents:** 훅·권한 처리기가 `sessionId`로 실행을 찾다가 색인 등록 전 호출을 놓쳐 감사 기록이 부분만 남거나 `rate_limit`을 놓치는 것
> - **Rule:** 훅(`on_post_tool_use`, `on_error_occurred`)과 `on_permission_request`는 앱 시작 시 만들지 않는다. `agents.session_options(run, step)`이 `(run, step)`을 클로저로 잡은 콜백과 그 단계의 `available_tools`를 만들고, `call_agent`가 `agent.run(..., options=session_options(run, step))`로 실행마다 넘긴다. `sessionId`→실행 색인은 두지 않는다. 최소 샘플에서 `options`의 `hooks`·`on_permission_request`가 `create_session`과 `resume_session` 양쪽에 전달되는지 확인한다. 확인에 실패하면: 감사 기록은 실행기가 스트림의 `function_result` 콘텐츠로 `run.record_audit()`에 쓰고, `on_post_tool_use`는 span 속성만 남긴다.
> - **Rule(규칙 7 보강):** 감사 기록에는 `complete: bool`을 둔다. 실행기가 스트림에서 본 `function_call` 수와 감사 기록 수가 다르면 `complete=False`이고, 이때 규칙 7은 그 단계 전체를 건너뛰고 건너뛴 사실을 표시한다. 부분 감사 기록으로 추천을 제거하지 않는다.

AD-12의 "공통 `on_permission_request`"는 "`TOOL_ALLOWLIST[step]`로 만든 단계별 처리기"로 고친다.

---

## H2. `call_agent` ↔ 실행기 스트리밍 계약 — **High**

**충돌 단위:** `agents.call_agent(agent, prompt, run, step)`(L4) ↔ `workflow` 에이전트 실행기(L5) ↔ `service.ask`(L6).

**문제:** AD-8은 "에이전트 실행기는 `AgentResponseUpdate`를 그대로 `yield_output`한다", AD-10은 "모든 에이전트 호출은 `call_agent` 하나를 거친다"고 한다. 그런데 `call_agent`의 시그니처에는 `WorkflowContext`도 콜백도 없다. `yield_output`은 실행기의 `ctx`에서만 부를 수 있다.

**어긋나는 구현:**
- 팀원 A(agents): `call_agent`가 스트림을 끝까지 소비하고 `AgentResponse`를 돌려준다(45초·재시도를 내부에서 처리하기 가장 쉬운 형태). 시그니처 그대로다.
- 팀원 B(workflow): `async for u in call_agent(...)`로 갱신을 받아 `yield_output`하려 한다.
- 둘 다 AD를 지켰지만 결합되지 않는다. A의 구현을 따르면 토큰 스트리밍(SSE `token`, `tool_call`)이 사라진다. B의 구현을 따르면, 45초 초과 후 재시도할 때 **이미 내보낸 토큰 위에 같은 단계 토큰이 다시 쌓인다.** UI는 이를 구분할 신호가 없다.
- 재시도 예산도 갈린다. AD-6의 "제출 도구 미호출 시 1회 다시 요청"과 AD-10의 "1회 재시도"가 같은 예산인지 정해지지 않았다. 각각 1회씩이면 최악의 경우 4회 × 45초 = 180초로 90초 목표를 크게 넘는다. 누가 "제출 도구가 불렸는가"를 검사하는지(실행기 또는 `call_agent`)도 두 곳이 될 수 있다.
- `call_agent`의 중단 경로(TRD 7: `resume_session`→`abort()`)는 두 번째 `CopilotSession` 핸들을 같은 세션에 붙인다. 이 핸들에 훅을 다시 넘기면 이후 훅이 두 번 호출될 수 있다 `[미확인]`. 이 경우 감사 기록이 중복된다.

**닫는 AD (AD-10 강화):**

> - **Rule(추가):** `async def call_agent(agent, prompt, run, step, *, emit: Callable[[AgentResponseUpdate | UiEvent], Awaitable[None]], phase: Literal["workflow","ask"]="workflow") -> AgentCallResult`. 실행기는 `emit=ctx.yield_output`을 넘기고, `/ask`는 `service`가 만든 EventLog 기록 함수를 넘긴다. `call_agent`는 갱신마다 `emit`을 부른다. 두 번째 시도를 시작하기 전에 `UiEvent(type="step_retry", step, data={"attempt":2,"reason":code})`를 먼저 `emit`하고, UI는 이 이벤트를 받으면 그 단계의 토큰 표시를 비운다. 시도는 단계당 최대 2회이고, 시간 초과·오류 재시도와 제출 도구 미호출 재요청이 이 2회를 함께 쓴다. 제출 여부는 `call_agent`가 `run.has_submission(step)`으로만 판단한다. 실행기는 다시 검사하지 않는다. 중단용으로 얻은 세션 핸들은 `abort()` 직후 `disconnect()`한다. `AgentCallResult = {ok, error_code: rate_limit|timeout|tool_missing|other|None, attempts}`.

---

## H3. 매칭 결과 이중 경로, `verify()` 시그니처 누락, 규칙 6의 판정 ID — **High**

**충돌 단위:** `tools.submit_matches` ↔ `workflow.MatchExecutor` ↔ `workflow.VerifierExecutor` ↔ `verify.verify`.

**문제 1 — 결과가 두 곳에 있다.** AD-4는 `match_submissions`를 `submit_matches`가 RunState에 쓴다고 하고, TRD 3.2·5.5는 매칭 실행기가 `MatchResult`를 `send_message`로 fan-in에 보낸다고 한다. `verify(matches, …)`의 `matches`가 무엇인지 정하지 않았다.
- 팀원 A(workflow): Verifier 핸들러 인자 `list[MatchResult]`를 `matches`로 넘긴다. `MatchResult`에는 `status/error`만 있고 추천이 없다(추천은 RunState에 있다).
- 팀원 B(verify): `matches: list[MatchSubmission]`(추천 포함)을 기대한다.
- 결과: 형식 불일치. 또는 A가 실패 분야 정보를 잃는다.

**문제 2 — 분야 정체를 누가 정하나.** `submit_matches(MatchSubmission)`에서 분야를 모델 인자로 받으면, 모델이 다른 분야 이름을 넣어 **다른 분기의 제출을 덮어쓸 수 있다.** 같은 분기 재제출(검증 실패 뒤 재호출, H2의 재시도)이 추가인지 교체인지도 정하지 않았다. 추가라면 Verifier가 중복 추천을 받는다.

**문제 3 — `verify()`는 규칙 6을 수행할 수 없다.** 규칙 6(빠진 제도를 규칙 함수로 채움)에는 프로필이 필요한데 시그니처에 `profile`이 없다. 채운 판정은 `record_decision()`만 ID를 발급할 수 있는데(AD-3), L1 순수 함수는 RunState를 건드릴 수 없다(AD-1).
- 팀원 B(verify)는 `verify` 안에서 `rules.evaluate`를 직접 부르고(L1→L1 허용) ID를 `"verifier-1"`처럼 만든다 → AD-3 위반이 아닌 것처럼 보이지만 `lookup_decision`이 찾지 못하는 ID가 된다.
- 팀원 A(workflow)는 `verify`가 채울 목록을 돌려줄 것이라 기대한다.
- 실패한 분야(매칭 `status="failed"`)에도 규칙 6을 적용하는지 정해지지 않았다. 재현율 90% 목표에 직접 영향을 준다.

**닫는 AD (AD-1, AD-4, AD-6 강화):**

> ### AD-17 — 매칭 → 검증 데이터 계약 [PROPOSED]
> - **Binds:** tools, workflow, verify, schemas, F4, F5
> - **Prevents:** 매칭 결과가 메시지와 상태 두 곳에서 다른 형식으로 읽히는 것, 모델이 분야를 사칭해 제출을 덮는 것, 규칙 6 판정이 ID 계약 밖에서 생기는 것
> - **Rule:** `submit_matches`는 분야를 인자로 받지 않고 `ctx.kwargs["step"]`로 정한다. 같은 단계 재제출은 앞 제출을 교체한다(마지막 유효 제출). 매칭 실행기는 `call_agent`가 끝난 뒤 `MatchResult(domain, status: ok|failed, error_code, submission: MatchSubmission | None)`를 `run.match_submissions.get(step)`으로 만들어 **정확히 1회** `send_message`한다. Verifier 실행기 순서: (1) `gaps = verify.coverage_gaps(decisions, schemes)` (2) 각 `scheme_id`에 `run.record_decision(rules.evaluate(scheme, run.profile), source="verifier")` (3) `verify(matches: list[MatchResult], decisions, audit, schemes) -> VerifiedResult`. 규칙 6은 실패 분야에도 적용한다. `DecisionRecord.source: Literal["tool","verifier"]`를 두고, 규칙 7은 `source="tool"`에만 적용한다. `Recommendation`에는 `scheme_id`, `decision_id`, `result`, `condition_ids`를 필수로 둔다.

---

## H4. 실행 중 재생 전환 — **High**

**충돌 단위:** `service`의 재생 전환(AD-10 마지막 문장) ↔ 진행 중인 워크플로 백그라운드 태스크 ↔ `EventLog`(AD-8·AD-9) ↔ UI 타임라인.

**상황:** 데모 사례가 live로 시작해 `masked`, `step_started profiler`, `token`…(seq 1..N)까지 기록됐다. `match_health`에서 `rate_limit`이 났다. AD-10에 따라 실행기는 예외를 던지지 않고 `step_failed`를 내고 축소 결과를 보낸다. 워크플로는 **계속 진행한다.** 동시에 `RunService`는 재생으로 전환한다(AD-9: "같은 EventLog에 이벤트를 다시 쌓는다").

**어긋나는 구현:**
- 팀원 A(service 재생): 재생 파일 이벤트를 seq N+1부터 시간 간격대로 `append`한다.
- 팀원 B(workflow·소비 루프): 워크플로 스트림을 계속 매핑해 `append`한다.
- 결과: (1) 같은 로그에 `masked`가 두 번, `step_started profiler`가 두 번 나오고 live 토큰과 재생 토큰이 섞인다. (2) live 분기가 `request_info`에 도달하면 `approval_required`가 두 개(서로 다른 `request_id`) 나온다. AD-13의 "대기 중인 요청과 같아야 함"에서 어느 것이 대기 중인지 정해지지 않는다. (3) 계속 도는 live 매칭 도구가 `RunState.decisions`에 계속 추가한다. 재생 쪽 승인 템플릿이 그 판정을 섞어 쓸 수 있다. (4) 소비 태스크를 `cancel()`해도 Copilot 런타임 턴은 계속된다(agent-framework.md 4-4: 취소는 구독만 해제). 한도 초과 상황에서 호출을 더 쓴다.
- AD-9의 "재생 전용 경로 금지"를 지키면 UI에 "여기서부터 화면을 다시 그려라"라는 신호를 보낼 방법이 없다.

**닫는 AD (AD-9·AD-10 강화, 상태도 수정):**

> - **Rule(AD-10 추가):** 실행 중 재생 전환은 **새 실행으로** 한다. `RunService`는 (1) 기존 실행의 소비 태스크를 `cancel()`하고, (2) 그 실행의 Copilot 세션마다 `abort()`를 부르고, (3) 기존 실행 `EventLog`에 `UiEvent(type="replaced", data={"run_id": 새_id, "reason":"rate_limit"})`와 `done`을 쓰고 상태를 `failed(reason="replaced")`로 바꾼 뒤, (4) 새 `run_id`로 재생 실행을 시작한다. UI는 `replaced`를 받으면 새 실행의 SSE로 옮긴다. 한 `EventLog`에는 한 `mode`의 이벤트만 쌓인다. `EventLog.append`는 `run.mode`와 다른 출처의 이벤트를 거부한다.
> - **상태도:** `running --> replaying` 전이를 지우고 `running --> failed: replaced`를 둔다. 재생은 `queued --> replaying`으로만 시작한다.
> - **Rule(AD-7 보강):** 실행기의 예외 처리는 `except Exception`까지만 쓴다. `asyncio.CancelledError`는 잡지 않는다.

---

## H5. 승인 재개 경합과 상태 전이 호출 주체 — **High**

**충돌 단위:** `main`의 `POST /approval` → `service.respond` ↔ 서비스의 워크플로 소비 루프 ↔ `ReferralGate` ↔ `RunState` 전이 메서드.

**문제 1 — 이중 제출.** 담당자가 "승인"을 두 번 누르거나 심사 에이전트가 같은 요청을 재시도한다. 두 요청 모두 `request_id`가 대기 중 요청과 같으므로 AD-13 검사를 통과한다. 둘 다 `workflow.run(responses=...)`를 부르면 두 번째는 `WorkflowException("already running")`(agent-framework.md 2.4)이 나 500이 되거나, 첫 재개가 끝난 뒤라면 "대기 요청 없음" 오류가 난다. 상태도에는 "재개 중" 상태가 없어 `awaiting_approval` 동안 창이 열려 있다.

**문제 2 — 누가 상태를 바꾸나.** AD-4는 "전환은 RunState 메서드로만"이라고 했지만 **호출자**를 정하지 않았다.
- 팀원 A(workflow): Profiler 실패 시 실행기 안에서 `run.fail()`을 부르고 메시지를 보내지 않는다.
- 팀원 B(service): 스트림이 대기 요청 없이 끝나면 `run.fail()`을 부른다.
- 결과: `failed → failed` 전이가 상태도 위반 예외를 내거나, 서로 다른 실패 이유가 덮인다. `awaiting_approval` 전이를 매퍼(events.py)가 할지 소비 루프가 할지도 두 곳이 될 수 있다.

**문제 3 — `ApprovalDecision` 필드 미정.** AD-13은 "`scheme_ids`는 Verifier 통과 집합의 부분집합"이라 하지만 TRD의 POST 본문에는 `scheme_ids`가 없다. 누구의 `scheme_ids`를 검사하는지 정해지지 않았다.

**닫는 AD (AD-4·AD-13 강화):**

> ### AD-18 — 상태 전이는 RunService만 [PROPOSED]
> - **Binds:** service, runs, workflow, events, main
> - **Prevents:** 실행기·매퍼·서비스가 각자 상태를 바꿔 이중 전이·덮어쓰기가 생기는 것, 승인 이중 제출이 워크플로를 두 번 재개하는 것
> - **Rule:** 실행 상태 전이 메서드는 `RunService`만 부른다. 실행기·도구·매퍼·훅은 부르지 않는다. 전이 근거는 워크플로 이벤트다: `request_info` → `awaiting_approval`(+`run.pending_request_id` 설정), `output`의 `finalized` → `finalized`, `failed` 이벤트 또는 대기 요청·확정 없이 끝난 스트림 → `failed`(이유는 마지막 `step_failed`). `respond()`는 `await` 전에 동기 메서드 `run.claim_approval(request_id)`를 부른다. 이 메서드는 `pending_request_id`가 같으면 비우고 상태를 `resuming`으로 바꾸며, 다르거나 비어 있으면 409를 낸다. 상태도에 `awaiting_approval → resuming → finalized | awaiting_approval(거부) | failed`를 추가한다.
> - **Rule(AD-13 보강):** `ApprovalDecision = {request_id, approved, edited_sections: dict[SectionId, str], scheme_ids: list[str]}`. `scheme_ids`가 비어 있으면 `ApprovalRequest.scheme_ids`를 쓴다.

---

## H6. `/ask`가 승인 대기 초안을 바꿈, `/ask` 이벤트 경로 미정 — **High**

**충돌 단위:** `service.ask` ↔ `tools.submit_draft` ↔ `ReferralGate @response_handler` ↔ `main` SSE.

**문제 1 — 초안 변경.** `/ask`는 Documenter 에이전트를 같은 세션으로 다시 부른다(AD-7, TRD 3.2). AD-12 표에 따라 Documenter의 허용 도구에는 `submit_draft`가 있다. 질문이 "의뢰서에 기초연금도 넣어 줘"면 모델이 `submit_draft`를 부르고, AD-4상 `draft`의 유일한 쓰기 주체이므로 정당하게 **승인 대기 중인 RunState.draft를 교체**한다.
- 팀원 A(workflow): `ReferralGate`가 승인 시 `run.draft`를 읽어 템플릿을 채운다.
- 결과: 담당자가 화면에서 보고 고친 초안과 다른 초안에 `edited_sections`가 덮여 확정된다. 확정 내용이 모델 호출로 바뀌는 경로라서 AD-13의 목적(모델이 확정 내용을 바꿀 수 없음)을 우회한다.

**문제 2 — 아직 Documenter 세션이 없을 때.** 워크플로가 Documenter 단계 전에 `/ask`가 오면 `run.sessions["documenter"].service_session_id`가 비어 있다. MAF는 새 Copilot 세션을 만들고 그 ID를 공유 `AgentSession`에 쓴다. 곧이어 실행기도 같은 `AgentSession`으로 `run()`을 부르면, 잠금은 `service_session_id` 기준이라(agent-framework.md 2.2-4) ID가 없을 때는 직렬화되지 않는다 `[추론]`. 두 세션이 만들어지고 하나는 TTL 정리 대상에서 빠진다.

**문제 3 — 출력 경로.** TRD 표 4는 `/ask`가 **SSE 응답**이라 하고, AD-8은 SSE는 `EventLog`에서만 읽는다고 한다. `map_workflow_event`는 워크플로 이벤트용이라 `/ask`의 `AgentResponseUpdate`를 받을 입구가 없다.
- 팀원 A(main): `/ask` 응답 본문으로 직접 스트리밍한다(AD-8 위반처럼 보이지 않는다: "/ask는 워크플로 밖").
- 팀원 B(service): 실행 `EventLog`에 쓴다.
- 결과: 화면이 답변을 두 번 보이거나 한 번도 보이지 않는다.

**닫는 AD (AD-7·AD-8·AD-12 강화):**

> - **Rule(AD-7 추가):** `/ask`는 실행 상태가 `awaiting_approval`·`finalized`일 때만 받고, 그 밖에는 409다. 실행당 동시 `/ask`는 1건이다. `/ask` 호출은 `session_options(run, "documenter", phase="ask")`로 `available_tools=["custom:lookup_decision"]`만 넘긴다.
> - **Rule(AD-4 추가):** 제출 도구(`record_*`, `submit_*`)는 `run.status == "running"`이고 `ctx.kwargs["step"]`이 그 도구의 단계일 때만 기록하고, 아니면 거부 문자열을 돌려준다. `ReferralGate`는 `request_info`를 걸 때 `ApprovalRequest`에 초안 스냅샷을 담고, 확정은 그 스냅샷과 `edited_sections`로만 만든다.
> - **Rule(AD-8 추가):** `POST /ask`는 `202 {ask_id}`를 돌려주고, 답변 이벤트는 같은 실행의 `EventLog`에 `step="documenter"`, `data.ask_id`를 붙여 쓴다. 기록 함수는 `events.map_agent_update(update, step, ask_id) -> list[UiEvent]`다.

---

## H7. 재생 파일: 기록 ↔ 재생 불일치 — **High**

**충돌 단위:** 재생 파일 기록(누가, 언제?) ↔ `service` 재생 ↔ 승인 템플릿(AD-9: "ReferralGate와 같은 확정 템플릿 코드").

**어긋나는 구현:**
- AD-9는 재생 파일이 "실제 실행의 `EventLog`를 그대로 직렬화한 것"이라고 한다. 그대로 직렬화하면 봉투의 `run_id`, `seq`, `ts`, `trace_id`, `mode:"live"`가 **기록한 실행의 값**으로 남는다. 재생 담당자가 그대로 다시 `append`하면 UI는 다른 `run_id`의 이벤트를 받고, 화면의 trace ID 링크는 Application Insights에 없는 trace(로컬 기록)를 가리킨다.
- 기록 시점이 정해지지 않았다. 팀원이 "관리용 기록 엔드포인트"를 만들어 런타임에 `data/replays/`에 쓰면 AD-14(디스크 쓰기 금지)를 위반한다. 기록 범위도 없다. `finalized`까지 기록하면 재생이 승인 없이 확정 화면을 보여 AD-9("승인 단계까지")와 F8을 어긴다.
- **재생 승인이 동작하지 않는다.** 승인 템플릿은 `draft`와 Verifier 통과 집합(AD-13 부분집합 검사)이 필요하다. 재생 실행은 이벤트만 다시 쓰고 `RunState.profile/decisions/verified/draft`를 채우지 않는다. 팀원 A(템플릿)는 `run.draft`를 읽고, 팀원 B(재생)는 아무것도 채우지 않는다 → 재생 승인 시 `None` 오류. 재생 파일의 `approval_required` 이벤트에 든 `request_id`는 기록 실행의 것이라 `pending_request_id`와 맞지 않는다(H5).
- 재생 실행에서 `/ask`가 오면 Documenter 세션이 없다.

**닫는 AD (AD-9 대체 문구):**

> - **Rule:** `schemas.ReplayFile = {case_id, recorded_at, events: [{offset_ms, type, step, data}], snapshot: {masked_note, profile, decisions, verified, draft, approval_request}}`. 봉투 필드(`run_id`, `seq`, `ts`, `trace_id`, `mode`)는 저장하지 않고, 재생 때 `EventLog.append`가 새로 붙인다(`mode="replay"`, `trace_id`는 재생 실행의 것). 기록은 오프라인 스크립트 `scripts/record_replay.py`가 같은 `RunService`로 실행해 `approval_required`에서 자른 결과만 쓴다. 런타임 코드는 `data/replays/`에 쓰지 않는다. 재생 시작 시 `RunService`가 `snapshot`으로 `RunState`를 채우고, 재생의 `approval_required`는 새 `request_id`로 다시 만들어 `pending_request_id`에 넣는다. 재생 실행의 `/ask`는 409다.

---

## H8. 30분 TTL이 진행 중 실행·SSE를 지움 — Medium-High

**충돌 단위:** `RunRegistry` TTL 정리 ↔ 워크플로 백그라운드 태스크 ↔ SSE 핸들러 ↔ 도구(`ctx.kwargs["run_id"]` 조회).

**어긋나는 구현:**
- TTL은 "생성 30분 뒤"다(상태도 주석). 승인 대기 29분 59초에 승인하면 재개 도중 레지스트리가 실행과 Copilot 세션을 지운다. 백그라운드 태스크는 레지스트리가 모르는 객체라(AD-4는 태스크 소유를 정하지 않음) 계속 돈다. 이후 도구 호출은 `KeyError`, SSE 핸들러가 폴링마다 레지스트리를 조회하는 구현이면 스트림 중간에 404로 바뀐다. `EventLog` 참조를 쥔 구현이면 영원히 heartbeat만 보낸다.
- 세마포어 대기열(실시간 4건)에 오래 머문 실행도 생성 시점부터 TTL이 흐른다.
- TTL 정리에는 `delete_session`(비동기)이 필요한데, AD-4는 "상태 변경 메서드는 동기"라고 한다. 정리 루틴을 레지스트리(L2)에 넣으면 Copilot 클라이언트(L4)를 import해야 해 AD-1을 어긴다.

**닫는 AD (AD-4 강화):**

> - **Rule:** TTL은 마지막 활동(이벤트 기록·API 호출) 기준 30분이고, 상태가 `queued|running|resuming|replaying`이면 미룬다(생성 후 45분이 상한). 정리는 두 단계다: (1) `RunRegistry.evict(run_id)`(동기)가 색인에서 지우고 `EventLog.close("expired")`를 부른다. (2) 레지스트리 생성 때 `RunService`가 등록한 `on_evict(run)` 콜백이 백그라운드 태스크 `cancel()`, 세션 `abort()`·`delete_session()`을 비동기로 처리한다. SSE 핸들러는 연결 때 `EventLog` 참조를 한 번만 얻고, 로그가 닫히면 끝낸다. 재접속하면 404다. 도구는 실행을 찾지 못하면 예외 대신 `"실행이 만료되었습니다"`를 돌려준다.

---

## H9. 평가 ↔ 실시간 세마포어·재생 전환·완료 조건 — Medium-High

**충돌 단위:** `service.start_eval` ↔ `service.start` ↔ 세마포어(AD-10) ↔ 재생 전환(H4).

**어긋나는 구현:**
- AD-10은 "실시간 4, 평가 전역 1"만 정했다. TRD 7은 평가 사례를 2건씩 동시 실행한다. 평가 사례 실행이 실시간 세마포어를 쓰지 않는 구현이면 동시에 실시간 4 + 평가 2 = 6실행 × 매칭 3 = **18개 Copilot 세션**이 같은 토큰으로 돈다. 심사 중 평가 버튼 하나가 라이브 데모를 429로 떨어뜨린다. 쓰는 구현이면 평가 2건이 실시간 슬롯 절반을 차지한다. 어느 쪽도 AD를 어기지 않는다.
- 평가 사례는 데모 사례와 같은 `case_id`다(Capability map F1·F10). 평가 중 `rate_limit`이 나면 AD-10의 "데모 사례 rate_limit → 재생 전환"이 평가 실행에도 걸린다. 평가 담당은 재생 결과를 live 지표에 섞는다.
- **완료 조건이 없다.** 모든 실행은 `awaiting_approval`에서 멈춘다. `finalized`를 기다리는 평가 구현은 영원히 끝나지 않는다. 6분 상한에서 남은 사례를 취소하는 방법도 H4와 같은 문제를 가진다.
- 평가 SSE(`/api/eval/{id}/events`)의 이벤트 로그와 평가 상태(`EvalState`)의 소유자·TTL이 스파인에 없다. AD-4는 `RunState`만 다룬다.

**닫는 AD (AD-10 강화):**

> - **Rule:** 평가 사례 실행도 실시간 세마포어 1칸씩을 쓴다(프로세스 전체 동시 실행 ≤ 4). 평가 동시성은 2다. 평가 사례 실행은 `start(case_id, purpose="eval")`로 만들고, `purpose="eval"`이면 재생 전환을 하지 않는다. 대신 그 사례를 `replayed=true`로 표시하고 지표 평균에서 뺀다. 평가 사례 완료 조건은 `approval_required` 또는 `failed` 이벤트이고, 완료되면 바로 `evict`한다. 6분 상한을 넘기면 H4의 취소 절차(cancel → abort)를 쓴다. `EvalState`와 평가 `EventLog`도 `RunRegistry`가 같은 TTL 규칙으로 소유한다.

---

## H10. 레지스트리 접근 경로, `function_invocation_kwargs` 형식, 동기 함수 원자성 — Medium

**충돌 단위:** `tools.py` ↔ `runs.py` ↔ `context.StepTimingMiddleware` ↔ `service`.

**어긋나는 구현:**
- **레지스트리 인스턴스가 둘.** 팀원 A(service)는 FastAPI lifespan에서 `RunRegistry()`를 만들어 `app.state`에 둔다. 팀원 B(tools)는 `runs.py`의 모듈 수준 `registry`를 import한다. 도구가 실행을 찾지 못한다. 도구는 L3라 `app.state`에 접근할 수 없다.
- **kwargs 키가 부족하다.** 스파인은 `ctx.kwargs['run_id']`만 언급한다. `submit_matches`(H3)·`StepTimingMiddleware`의 `app.step` 속성·제출 도구의 단계 검사(H6)는 모두 `step`이 필요하다. 팀원마다 `"step"`, `"executor_id"`, `"domain"`(agent-framework.md 5.2 예시는 `"domain": self.id`)으로 다르게 넣는다.
- **"동기 함수라 원자적" 전제가 확인되지 않았다.** AD-4의 원자성은 모든 변경이 이벤트 루프 스레드에서 실행된다는 전제에 기대고 있다. SDK 처리기와 훅은 "동기·비동기 모두 가능"하다(copilot-sdk.md 3.3·3.8). 동기 도구 함수를 MAF/SDK가 스레드 풀에서 실행하는지는 참고 문서에 없다 `[미확인]`. 스레드에서 실행되면 `decision_id = f"d{len(self.decisions)+1}"` 같은 발급이 경합해 ID가 중복된다.

**닫는 AD (AD-4 강화):**

> - **Rule:** 레지스트리는 `runs.REGISTRY` 하나뿐이고 모듈이 로드될 때 만든다. 다른 곳에서 `RunRegistry()`를 만들지 않는다(테스트는 `REGISTRY.clear()`). `function_invocation_kwargs`는 정확히 `schemas.InvocationKwargs = {"run_id": str, "step": Step, "phase": "workflow"|"ask"}`이고 `call_agent`만 만든다. 도구·훅·권한 처리기는 모두 `async def`로 정의한다(스레드 실행 방지). `decision_id`는 실행별 `itertools.count()`로 `d{n}` 형식으로 발급한다.

---

## H11. 이벤트 매퍼 입력 타입·`W_OutT` 선언·게이트 출력 구분 — Medium

**충돌 단위:** `workflow` 실행기 ↔ `events.map_workflow_event`.

**어긋나는 구현:**
- 에이전트 실행기는 `AgentResponseUpdate`(토큰)와 `UiEvent`(`normalized`, `draft`, `step_failed`, `step_retry`)를 모두 `yield_output`한다. agent-framework.md 5.7 예시는 `WorkflowContext[MatchResult, AgentResponseUpdate]`로 선언한다. 그 예시를 따른 팀원은 `UiEvent`를 내보낼 때 타입 불일치를 만난다(MAF가 런타임에 경고·거부하는지는 `[미확인]`).
- `ReferralGate`는 `output_from=[gate]`에만 있다. TRD 3.5는 거부 결과를 `intermediate`로 내보낸다고 하지만, 출력 유형은 실행기 단위로 정해지므로(agent-framework.md 3.3 "출력") 게이트의 모든 `yield_output`은 `output`이다. 매퍼를 "`output` = `finalized`"로 짠 팀원은 거부 결과를 확정으로 표시한다.
- AD-8은 매퍼가 "하나"라고만 했다. `AgentResponseUpdate` 하나에 콘텐츠(text, function_call, function_result, usage)가 여러 개 들어올 수 있으므로 반환이 `Optional[UiEvent]`이면 이벤트를 잃는다.
- `executor_invoked`의 `.data`에는 입력 메시지(가리기 전 메모, 업로드 원본 바이트 포함 `RunInput`)가 들어 있다. 매퍼가 `.data`를 그대로 `step_started.data`에 넣으면 원본이 SSE·EventLog·재생 파일로 간다(AD-11 위반 경로).
- `step_failed` 뒤에 같은 실행기의 `executor_completed`가 오므로 `step_completed`도 나간다. UI가 마지막 이벤트로 상태를 정하면 실패 단계가 "완료"로 보인다.

**닫는 AD (AD-8 강화):**

> - **Rule:** 에이전트 실행기는 `WorkflowContext[Out, AgentResponseUpdate | UiEvent]`, 코드 실행기는 `WorkflowContext[Out, UiEvent]`로 선언한다. 매퍼는 `map_workflow_event(ev, run) -> list[UiEvent]`이고 MAF `event.type`(`output`/`intermediate`)이 아니라 `event.data`의 타입으로 판별한다: `UiEvent`면 그대로, `AgentResponseUpdate`면 콘텐츠마다 `token|tool_call|tool_result|usage` 하나씩. `executor_invoked/completed`는 `step_started/completed`이고 `data={}`다. MAF 이벤트의 `.data`를 SSE로 옮기지 않는다. 실행기가 `yield_output`하는 `UiEvent.type`은 `masked, transcribed, normalized, verified, draft, finalized, approval_kept, step_failed, step_retry` 중 하나다. UI는 `step_failed`를 받은 단계를 `step_completed`로 덮어쓰지 않는다.

---

## H12. `sessions` 필드 쓰기 주체 3곳, RunState의 MAF 객체 보관 — Medium

**충돌 단위:** `agents.call_agent`(재시도 때 세션 교체) ↔ 실행기(AD-4: `sessions`는 실행기가 씀) ↔ `StepTimingMiddleware`(AD-4: `sessions·timings`를 실행기와 미들웨어가 씀) ↔ `service`(워크플로·태스크 보관).

**어긋나는 구현:**
- AD-4의 "`sessions`·`timings`는 실행기와 `StepTimingMiddleware`가 쓴다"는 필드당 쓰기 주체 하나 원칙과 모순된다. TRD 7의 대체 경로(세션을 지우고 새 `AgentSession`으로 재시도)는 `call_agent`(L4)가 세 번째로 `sessions`를 쓰게 만든다. 실행기가 세션을 한 번 만들어 지역 변수로 쥐고 있으면 교체된 세션을 모르고, TTL 정리는 옛 ID만 지운다.
- TRD는 RunState가 워크플로 인스턴스를 가진다고 했지만 L2는 "MAF 이벤트 타입"만 의존 가능하다. `AgentSession`·`Workflow`·`asyncio.Task`를 RunState에 넣는 팀원과 `service` 사설 dict에 넣는 팀원이 갈린다. 후자는 TTL 정리에서 빠진다.

**닫는 AD (AD-4 강화):**

> - **Rule:** `run.sessions[step]`의 생성·교체는 `call_agent`만 `run.session_for(step)`/`run.replace_session(step)`으로 한다. `timings`는 `StepTimingMiddleware`만 쓴다. 실행기는 둘 다 쓰지 않는다. L2는 MAF의 `AgentSession` 타입을 import할 수 있다. 워크플로 인스턴스와 백그라운드 태스크는 `run.runtime: RunRuntime`(`service.py`에 정의, `runs.py`에서는 `Any`)에 두고 `service`만 읽고 쓴다.

---

## H13. 제출 도구의 "새 숫자" 검사 기준 — Medium

**충돌 단위:** `tools.submit_matches`/`submit_draft` 검사 ↔ 매칭·Documenter 프롬프트 ↔ `data/schemes.json`.

**어긋나는 구현:** AD-6은 모든 제출 도구에 "원문에 없는 숫자가 새로 생기지 않았는지"를 검사하게 했다. 원문을 "가린 메모"로 해석한 팀원 A(tools)와, 추천 설명에 "기준 820,556원 이하"처럼 제도 기준값을 쓰라고 지시한 팀원 B(prompts)가 만나면 **정상 추천이 모두 거부**되고, 2회 시도 뒤 `tool_missing` 실패가 된다. 가리기 자리표시자(`[전화1]`)의 숫자도 오탐 원인이다. 한글 수사 정규화 함수의 위치(TRD는 `record_clean_note` 안)도 정해지지 않아 도구마다 다시 구현된다.

**닫는 AD (AD-6 강화):**

> - **Rule:** 숫자 비교는 L1 `numbers.py`의 `new_numbers(candidate: str, allowed: set[int]) -> set[int]` 하나로 한다(한글 수사 정규화 포함, 자리표시자 제외). 허용 집합: `record_clean_note` = 가린 인식 텍스트의 숫자, `submit_matches`·`submit_draft` = 가린 메모 숫자 ∪ 같은 실행 판정 기록의 사용 값·기준값 ∪ `schemes.json` 기준값.

---

## H14. SSE 종료·heartbeat·`done` 위치 — Medium

**충돌 단위:** `main` SSE 핸들러 ↔ `service` 소비 루프 ↔ 브라우저 `EventSource`.

**어긋나는 구현:**
- `done`은 TRD 표 5에서 "API"가 만든다. `EventLog` 밖에서 만들면 재접속한 클라이언트는 `done`을 다시 받지 못하고, 서버가 연결을 닫을 때마다 `EventSource`가 자동 재접속을 반복한다.
- 워크플로가 `IDLE_WITH_PENDING_REQUESTS`로 끝나면(승인 대기) 소비 루프의 스트림이 끝난다. SSE 핸들러를 "워크플로 스트림이 끝나면 응답 종료"로 짠 팀원이 있으면, 승인 대기 동안 클라이언트가 3초마다 재접속한다. 승인 뒤 재개된 이벤트는 다음 재접속 때에야 보인다.
- heartbeat에 `id:`를 붙이면 `Last-Event-ID`가 seq 체계에서 벗어난다.

**닫는 AD (AD-8 강화):**

> - **Rule:** 종료 이벤트 `done`은 `RunService`가 `EventLog`에 쓴다(`finalized`·`failed`·`replaced`·`expired` 직후). `approval_required` 뒤에는 연결을 유지한다. SSE 핸들러는 `EventLog`의 조건 변수를 기다리며 `done`을 보낸 뒤에만 연결을 닫는다. heartbeat는 `: hb` 주석 줄로 보내고 `id`를 붙이지 않으며 로그에 넣지 않는다.

---

## H15. ID 어휘 공백 — Medium

**충돌 단위:** `data/schemes.json` 작성자 ↔ `tools.search_schemes(domain: Literal[...])` ↔ AD-3 단계 이름 ↔ 워크플로 실행기 ID.

- AD-3은 단계 이름 `match_living` 등을 고정했지만 **분야 ID**는 정하지 않았다. 데이터 담당이 `"domain": "생계·주거"`로 쓰고 도구 담당이 `Literal["living","health","care"]`로 쓰면 `search_schemes`가 빈 목록을 돌려준다. 모델은 "후보 없음"으로 끝나고 규칙 6이 모든 제도를 채우므로 오류가 드러나지도 않는다. 재현율은 맞지만 F4가 사실상 꺼진다.
- `InputRouter`의 실행기 ID가 목록에 없다. `executor_invoked` → `step_started`의 `step`이 AD-3 밖의 값이 된다.
- `/ask`의 단계 이름이 없다(span `app.step`, 타이밍 키).
- 매칭 에이전트가 `search_schemes("health")`처럼 다른 분야를 조회하고 판정할 수 있다. 판정 자체는 맞지만 분야별 커버리지 판단(규칙 6)과 UI 분류가 흔들린다.

**닫는 AD (AD-3 강화):**

> - **Rule(추가):** 분야 ID는 `living|health|care`이고 `schemes.json`의 `domain`, `search_schemes` 인자, 단계 이름 `match_{domain}`에 같은 값을 쓴다. 실행기 ID 목록에 `input_router`를 추가한다. `/ask`는 `step="documenter"`, `phase="ask"`로 기록한다. `search_schemes`와 `check_eligibility`는 `ctx.kwargs["step"]`의 분야 밖 제도를 거부한다.

---

## H16. `schemas.py` 최초 작성자 경합, 새 모듈 층 배정 — Medium

**충돌 단위:** 병렬로 시작한 모든 팀원.

- Deferred 표의 "`UiEvent.data` 세부 필드는 `schemas.py`를 처음 만드는 사람이 정한다"는 병렬 작업에서는 경합이다. 두 세션이 각자 `schemas.py`를 만들면 병합 충돌이 나고, 먼저 병합한 쪽이 이긴다. AD-2를 지키면서도 이 상황을 막을 수 없다.
- AD-1의 층 표는 모듈을 나열한다. H13의 `numbers.py`, 확정 템플릿(재생과 `ReferralGate`가 함께 씀), 기록 스크립트 같은 새 모듈의 층을 정하는 규칙이 없다. 확정 템플릿을 `workflow.py`에 두는 팀원과 `service.py`에 두는 팀원이 갈린다.

**닫는 AD (AD-2 강화):**

> - **Rule(추가):** 병렬 작업을 시작하기 전에 `schemas.py` 골격(모든 경계 타입, 이벤트 종류별 `UiEvent.data` 모델, `InvocationKwargs`, `ReplayFile`, `ApprovalDecision`)을 한 커밋으로 병합한다. 그 뒤 필드 추가는 이 파일만 고치는 별도 커밋으로 한다. 새 모듈은 층 표에 행을 추가하는 커밋으로만 만든다. 확정 문서 템플릿은 L1 `render.py`의 순수 함수 `render_final(draft_snapshot, edited_sections, verified) -> FinalDocuments`로 둔다.

---

## H17. Copilot CLI 세션 상태가 디스크에 남음 — Medium

**충돌 단위:** `agents.py`의 `CopilotClient` 구성 ↔ AD-14("디스크를 쓰지 않는다").

**라이브러리 사실:** Copilot 런타임은 세션 대화 이력을 `~/.copilot/session-state/{sessionId}/`(또는 `base_directory`)에 **파일로 저장**한다(copilot-sdk.md 2.2, 4-12). 가린 메모와 모델 답변이 컨테이너 디스크에 쓰인다. `delete_session`은 TTL 때만 호출되므로, 프로세스가 죽으면 파일이 남는다.

**어긋나는 구현:** AD-14를 문자 그대로 지키는 팀원은 앱 코드에서만 디스크 쓰기를 피하고, Copilot CLI가 쓰는 파일은 신경 쓰지 않는다. 보안 문서(TRD 8)와 RAI 설명에는 "저장 없음"이라고 쓰여 있다.

**닫는 AD (AD-14 강화):**

> - **Rule(추가):** Copilot CLI의 세션 저장 위치(`base_directory`)는 컨테이너의 임시 볼륨으로 고정한다. 앱 시작 시 `list_sessions()`로 남은 세션을 모두 `delete_session()`한다. "디스크를 쓰지 않는다"는 "앱이 쓰지 않고, CLI 세션 파일은 30분 안에 지우며 재시작 때 비운다"로 바꿔 적는다.

---

## H18. `/ask` 가리기와 `pii_map` 단일 쓰기 — Low-Medium

**충돌 단위:** `service.ask` ↔ `masking.mask` ↔ AD-4(`pii_map`은 `intake`만 씀).

`/ask` 질문에 메모와 같은 이름이 나오면 `mask()`를 새로 호출할 때 자리표시자 번호가 메모와 어긋날 수 있다(질문의 `[이름1]`이 메모의 `[이름2]`와 같은 사람). Documenter는 다른 사람으로 이해한다. 질문의 새 개인정보를 `pii_map`에 더하는 것은 AD-4가 금지한다.

> - **Rule(AD-11 추가):** `mask(text, known: PiiMap | None = None) -> MaskResult`는 `known`의 값과 같은 문자열에 같은 자리표시자를 쓴다. `/ask`는 `known=run.pii_map`으로 가리고, 질문에서 새로 찾은 항목은 그 요청 안에서만 쓰고 RunState에 저장하지 않는다.

---

## H19. 상태도 누락 전이와 TRD 충돌 — Low-Medium

- `replaying → failed`(재생 파일 없음·손상), `awaiting_approval/resuming → failed`(재개 중 예외)가 없다. 전이 검사를 엄격하게 구현한 팀원의 코드는 이 상황에서 예외를 내고 실행이 상태 없이 남는다.
- TRD 표 2는 "Profiler 실패 → 데모 사례는 저장된 실행 재생", 스파인 AD-10은 "Profiler 실패 → `failed`"와 "`rate_limit`일 때만 재생"이다. 두 문서를 각각 읽은 팀원의 동작이 다르다.

> - **Rule:** 상태도에 `replaying → failed`, `resuming → failed`를 추가한다. 데모 사례(`case_id` 있음, `purpose="live"`)에서 Profiler가 이유와 관계없이 실패하면 H4의 교체 절차로 재생 실행을 시작한다. 직접 입력은 `failed`다. TRD 표 2를 이 문장으로 맞춘다.

---

## 부록 A. 라이브러리 현실 점검 결과

| 질문 | 결론 | 근거 |
|---|---|---|
| 코드 실행기의 `yield_output(UiEvent)`가 `intermediate_output_from`으로 매퍼에 도달하는가 | 도달한다. 목록에 있는 실행기의 출력은 `type="intermediate"` 이벤트의 `.data`로 나온다. 단 (1) `input_router`는 목록에 없어 숨겨지고, (2) 게이트는 `output_from`이라 거부 결과도 `output`이며, (3) `W_OutT` 선언이 `AgentResponseUpdate`뿐이면 `UiEvent`가 타입 불일치가 된다 `[미확인: 런타임 거부 여부]` → H11 | agent-framework.md 3.3 "출력", 5.7 |
| 도구가 `ctx.kwargs['run_id']`만으로 RunState에 닿는가 | `function_invocation_kwargs`로 넘기면 `ctx.kwargs`에 들어온다(실행 확인). 실행 객체를 찾는 레지스트리 인스턴스가 하나여야 하고, `step`도 같이 넘겨야 한다 → H10. `ctx.session.state`도 대안 경로다 | agent-framework.md 5.2 |
| `on_post_tool_use`가 세션 ID를 알기 전에 실행을 찾을 수 있는가 | 찾을 수 없다. `service_session_id`는 `run()` 안에서 정해지고 실행기는 첫 갱신 뒤에야 본다. 훅 입력에는 `sessionId`만 있다 → H1 (실행별 `options`로 클로저 주입, 또는 스트림 기반 감사) | agent-framework.md 2.2, copilot-sdk.md 3.8 |
| 스트림 취소가 Copilot 턴을 멈추는가 | 멈추지 않는다. 구독만 해제한다 `[추론]`. 재생 전환·TTL·평가 상한의 취소 절차에 `abort()`가 필요하다 → H4, H8, H9 | agent-framework.md 4-4, copilot-sdk.md 4-3 |
| 같은 `Workflow`에 승인 응답을 두 번 넣으면 | 실행 중이면 `WorkflowException` → H5 | agent-framework.md 2.4 |
| Copilot 세션 데이터가 메모리에만 있는가 | 아니다. CLI가 디스크에 저장한다 → H17 | copilot-sdk.md 2.2 |
| 동기 도구 함수가 이벤트 루프 스레드에서 실행되는가 | 참고 문서에 없음 `[미확인]` → H10에서 `async def`로 강제 | — |

## 부록 B. 반영 순서 제안

1. 병렬 작업 전: H16(`schemas.py` 골격), H10(kwargs·레지스트리), H15(ID 어휘)를 반영한다. 30분 안에 끝나는 문서·골격 작업이다.
2. 최소 샘플(TRD 10 (1))에서 확인할 것을 추가한다: 실행별 `options`로 넘긴 `hooks`·`on_permission_request`가 `create_session`·`resume_session`에 전달되는가(H1), `UiEvent | AgentResponseUpdate` 합집합 `W_OutT`가 허용되는가(H11), `@response_handler` 안에서 `request_info`를 다시 걸 수 있는가(TRD 3.5).
3. 직렬 F1–F8 구현 전: H2(`call_agent` 시그니처), H3(매칭→검증 계약), H5(상태 전이 주체·승인 경합), H6(`/ask` 제한)을 AD로 확정한다.
4. 재생 파일 생성(TRD 10 (4)) 전: H7(재생 파일 형식)과 H4(교체 방식 전환)를 확정한다. 재생 파일을 먼저 만들고 형식을 나중에 바꾸면 파일을 다시 만들어야 한다.
5. 평가 구현 전: H9, H8.

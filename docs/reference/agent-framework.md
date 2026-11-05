# Microsoft Agent Framework(Python) API 명세 — 동행노트 기준

작성 기준일: 2026-11-05. 이 문서는 PyPI에 배포된 휠의 소스와 GitHub 저장소 태그 `python-1.24.0`(커밋 `43d767c55050480e470ebf0a89caa4141d325ebf`), Microsoft Learn 문서를 직접 읽고 정리했다. 줄 번호는 아래 버전 휠의 소스 기준이다. 일부 동작은 임시 가상환경(Python 3.12.15)에 패키지를 설치하고 실행해 확인했으며, 그 경우 "실행 확인"으로 표기한다. 확인하지 못한 항목은 `[미확인]`, 소스에서 추론한 항목은 `[추론]`으로 표기한다.

## 0. 출처 목록

본문은 아래 ID로 출처를 표기한다. 경로 앞부분 `R/`은 `https://github.com/microsoft/agent-framework/blob/43d767c55050480e470ebf0a89caa4141d325ebf/python/`을 뜻한다.

| ID | 출처 |
|---|---|
| S1 | PyPI JSON API: https://pypi.org/pypi/agent-framework-core/json, https://pypi.org/pypi/agent-framework/json, https://pypi.org/pypi/agent-framework-orchestrations/json, https://pypi.org/pypi/agent-framework-github-copilot/json, https://pypi.org/pypi/agent-framework-devui/json, https://pypi.org/pypi/agent-framework-ag-ui/json, https://pypi.org/pypi/github-copilot-sdk/json |
| S2 | `R/packages/github_copilot/agent_framework_github_copilot/_agent.py` (휠 2.1.1) |
| S3 | `R/packages/github_copilot/README.md` |
| S4 | `R/packages/core/agent_framework/_tools.py` (휠 1.24.0) |
| S5 | `R/packages/core/agent_framework/_middleware.py` |
| S6 | `R/packages/core/agent_framework/_sessions.py` |
| S7 | `R/packages/core/agent_framework/_agents.py` |
| S8 | `R/packages/core/agent_framework/_workflows/_workflow_builder.py` |
| S9 | `R/packages/core/agent_framework/_workflows/_edge_runner.py` |
| S10 | `R/packages/core/agent_framework/_workflows/_runner.py` |
| S11 | `R/packages/core/agent_framework/_workflows/_workflow.py` |
| S12 | `R/packages/core/agent_framework/_workflows/_workflow_context.py` |
| S13 | `R/packages/core/agent_framework/_workflows/_events.py` |
| S14 | `R/packages/core/agent_framework/_workflows/_agent_executor.py` |
| S15 | `R/packages/core/agent_framework/_workflows/_state.py`, `_checkpoint.py`, `_workflow_executor.py`, `_request_info_mixin.py`, `_executor.py`, `_functional.py` (같은 디렉터리) |
| S16 | `R/packages/orchestrations/agent_framework_orchestrations/` (`_sequential.py`, `_concurrent.py`, `_handoff.py`, `_group_chat.py`, `_magentic.py`) |
| S17 | `R/packages/core/agent_framework/observability.py` |
| S18 | Microsoft Learn, Observability: https://learn.microsoft.com/en-us/agent-framework/agents/observability?pivots=programming-language-python (git commit `94acee9d`) |
| S19 | Microsoft Learn, GitHub Copilot: https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/agent-services/github-copilot?pivots=programming-language-python (git commit `769f0e98`) |
| S20 | Microsoft Learn, Python 2026 Significant Changes Guide: https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes |
| S21 | 샘플: `R/samples/02-agents/providers/github_copilot/github_copilot_basic.py`, `github_copilot_with_function_approval.py`, `github_copilot_with_session.py` |
| S22 | 샘플: `R/samples/03-workflows/human-in-the-loop/guessing_game_with_human_input.py`, `R/samples/03-workflows/parallelism/fan_out_fan_in_edges.py` |
| S23 | `R/packages/devui/README.md`, `R/packages/ag-ui/README.md` |
| S24 | GitHub 이슈: https://github.com/microsoft/agent-framework/issues/9809 (open), /issues/8865 (closed), /issues/8753 (open), /issues/3572 (open), /issues/10087 (open) |
| S25 | Copilot SDK 휠 1.0.28: `copilot/client.py`(`create_session` 2442행, `start` 2048행), `copilot/session.py`(`_create_send_params` 2166행), `copilot/tools.py`(`Tool` 104행), `copilot/generated/session_events.py`(8340, 8491, 15160행) |

## 1. 패키지·버전·설치

출처: S1, S20.

### 1.1 현재 버전 (PyPI, 2026-11-05 조회)

| 패키지 | 최신 버전 | 업로드 시각(UTC) | Python | 핵심 의존성 |
|---|---|---|---|---|
| `agent-framework` | 1.24.0 | 2026-10-30 21:38 | >=3.10 | `agent-framework-core[all]==1.24.0` (메타 패키지) |
| `agent-framework-core` | 1.24.0 | 2026-10-30 21:39 | >=3.10 | `pydantic<3,>=2`, `opentelemetry-api<2,>=1.39.0`, `msgspec`, `python-dotenv`, `pyyaml` |
| `agent-framework-orchestrations` | 1.4.1 | 2026-10-30 21:39 | >=3.10 | `agent-framework-core<2,>=1.23.0` |
| `agent-framework-github-copilot` | 2.1.1 | 2026-10-30 21:39 | >=3.11 | `agent-framework-core>=1.22.0,<2`, `github-copilot-sdk>=1.0.16,<2.0` |
| `github-copilot-sdk` | 1.0.28 | 2026-10-28 00:55 | >=3.11 | — |
| `agent-framework-devui` | 1.0.0b261030 (beta) | 2026-10-30 21:39 | >=3.10 | `fastapi<0.142.0,>=0.115.0`, `uvicorn[standard]`, `openai`, `opentelemetry-sdk` |
| `agent-framework-ag-ui` | 1.7.1 | 2026-10-30 21:38 | >=3.10 | `ag-ui-protocol<0.2,>=0.1.19`, `fastapi<0.142.0,>=0.121.0`, `sse-starlette` |
| `agent-framework-azure-ai` | 1.0.0rc6 | 2026-03-30 | >=3.10 | 동행노트에는 불필요(모델은 Copilot SDK로 연결) |

GitHub 릴리스 태그 `python-1.24.0`은 2026-10-30 21:52(UTC)에 게시되었다.

### 1.2 설치

```text
# requirements.txt (동행노트 권장 고정)
agent-framework-core==1.24.0
agent-framework-orchestrations==1.4.1      # Sequential/Concurrent 등을 쓰지 않으면 생략 가능
agent-framework-github-copilot==2.1.1
github-copilot-sdk==1.0.28
opentelemetry-sdk                          # configure_otel_providers()에 필요(아래 주의)
azure-monitor-opentelemetry                # Application Insights
```

- `agent-framework-core` 1.24.0은 `opentelemetry-api`만 의존하고 `opentelemetry-sdk`를 설치하지 않는다. sdk 없이 `configure_otel_providers()`를 호출하면 `ModuleNotFoundError: opentelemetry-sdk is required to use configure_otel_providers()`가 발생한다(실행 확인). S18은 sdk가 기본 설치된다고 적고 있으나 1.24.0 휠 메타데이터와 다르다.
- `GitHubCopilotAgent`는 `agent_framework.github` 지연 임포트 네임스페이스와 `agent_framework_github_copilot` 두 경로로 임포트된다(`agent_framework/github/__init__.py`).
- Python 3.11 미만에서는 `agent-framework-github-copilot` 임포트가 `ImportError`로 실패한다(S2 118-122행).

### 1.3 이전 이름과 현재 이름

출처: S20(“ChatAgent renamed to Agent”, “Session/context provider pipeline finalized”, “Workflow events unified”, “workflow.send_responses* removed”, “SharedState renamed to State”, “Orchestration builders moved”, “Workflows now route runtime kwargs through explicit buckets”).

| 이전 | 현재(1.24.0) |
|---|---|
| `ChatAgent` | `Agent` (`RawAgent`는 미들웨어·텔레메트리 층 없는 버전) |
| `AgentThread`, `agent.get_new_thread()` | `AgentSession`, `agent.create_session()`, `agent.get_session(service_session_id=...)` |
| `agent.run_stream(...)` | `agent.run(..., stream=True)` → `ResponseStream[AgentResponseUpdate, AgentResponse]` |
| `@ai_function` | `@tool` (`ai_function`은 `_tools.py` 마지막 줄의 별칭으로만 남고 `agent_framework.__all__`에는 없다) |
| `WorkflowOutputEvent`, `RequestInfoEvent` 등 이벤트 클래스 | 단일 `WorkflowEvent`와 `event.type` 문자열 |
| `workflow.send_responses_streaming(...)` | `workflow.run(responses={...}, stream=True)` |
| `SharedState` | `State` (`ctx.get_state`/`ctx.set_state`, 동기 API) |
| `from agent_framework import SequentialBuilder` | `from agent_framework.orchestrations import SequentialBuilder` |
| `workflow.run(msg, **kwargs)` | `workflow.run(msg, function_invocation_kwargs=..., client_kwargs=...)` |

## 2. 핵심 개념과 객체 수명주기

### 2.1 에이전트 계층

출처: S7 428행(`BaseAgent`), 891행(`RawAgent`), 1999행(`Agent`); S2 618행(`RawGitHubCopilotAgent`), 1870행(`GitHubCopilotAgent`); S5 1913행(`AgentMiddlewareLayer`).

- `BaseAgent`: `id`, `name`, `description`, `context_providers`, `middleware`, `create_session()`, `get_session()`를 가진다. `create_session()`은 빈 `AgentSession`만 만든다.
- `Agent(client, instructions=None, *, tools, default_options, context_providers, middleware, ...)`: 채팅 클라이언트 기반 에이전트. 프레임워크가 함수 호출 루프, 승인 요청(`function_approval_request` 콘텐츠), 함수·채팅 미들웨어, 구조화 출력(`response_format`)을 직접 처리한다.
- `GitHubCopilotAgent`: `AgentMiddlewareLayer` + `AgentTelemetryLayer` + `RawGitHubCopilotAgent` 조합이다. 채팅 클라이언트가 없고, 도구 호출 루프와 권한 처리를 Copilot SDK 세션(Copilot CLI 런타임)이 맡는다. 따라서 `Agent`의 기능 중 일부(함수 미들웨어, 프레임워크 승인 왕복, `response_format`)는 이 경로에서 동작하지 않는다(4절, 5절).

### 2.2 GitHubCopilotAgent 수명주기

출처: S2 652-831행, 1497-1868행.

1. 생성: `GitHubCopilotAgent(instructions, *, client=None, id, name, description, context_providers, middleware, tools, default_options, env_file_path, env_file_encoding)`. `client`를 넘기면 `_owns_client=False`가 되어 `stop()`이 그 클라이언트를 멈추지 않는다.
2. 시작: `await agent.start()` 또는 `async with agent:`. 자체 클라이언트일 때만 `CopilotClient(connection=RuntimeConnection.for_stdio(path=cli_path), log_level, base_directory, telemetry)`를 만든다. 공유 클라이언트이면 `client.start()`만 호출하며, SDK의 `CopilotClient.start()`는 잠금 아래에서 `_state == "connected"`이면 바로 반환하므로 여러 에이전트가 호출해도 안전하다(S25 `client.py` 2048-2075행).
3. 실행: `run()`이 처음 호출되면 `AgentSession.service_session_id`가 비어 있어 `client.create_session(**kwargs)`로 Copilot 세션을 만들고 그 ID를 `service_session_id`에 저장한다. 이후 같은 `AgentSession`으로 실행하면 `client.resume_session(service_session_id, **kwargs)`를 호출한다(1646-1716행, 1836-1868행).
4. 실행마다 도구를 다시 변환해 등록한다. 도구 핸들러는 그 실행의 `function_invocation_kwargs`와 `AgentSession`을 클로저로 붙잡는다. 같은 `(CopilotClient, service_session_id)`에 대한 실행은 모듈 전역 `asyncio.Lock`으로 직렬화된다(206-208행, 1585-1645행). 한 세션에서 겹친 실행이 서로의 컨텍스트로 도구를 실행하지 않게 하려는 장치다.
5. 종료: `await agent.stop()`. 공유 클라이언트는 앱 종료 시 직접 `await client.stop()`한다.

### 2.3 프롬프트 구성 방식(Copilot 경로)

출처: S2 990-1030행(비스트리밍), 1127-1139행(스트리밍).

- 입력 메시지와 컨텍스트 공급자가 넣은 메시지를 `"\n".join(message.text ...)`로 한 문자열로 합쳐 `session.send(prompt, attachments=...)`/`send_and_wait(...)`에 보낸다. 역할(role) 구분은 전달되지 않는다.
- 컨텍스트 공급자의 `instructions`는 시스템 메시지가 아니라 프롬프트 앞에 텍스트로 붙는다.
- 생성자 `instructions`는 `system_message={"mode": "append", "content": instructions}`가 된다. `default_options["system_message"]`에 `"mode": "replace"`를 주면 Copilot 기본 시스템 프롬프트를 교체한다(1292-1313행).
- 대화 이력은 Copilot CLI 세션이 보관한다. `data:` base64 콘텐츠만 `blob` 첨부로 전달되고 원격 URI는 버려진다(1315-1362행).

### 2.4 Workflow 실행 모델

출처: S8, S10 120-185행, S11 801-899행, S15 `_state.py`.

- `WorkflowBuilder(...).add_*(...).build()`가 `Workflow`를 만든다. 실행은 Pregel식 superstep 단위다. 한 superstep에서 보낸 메시지는 다음 superstep에 배달되고, 서로 다른 대상의 메시지는 동시에 처리된다.
- `State`의 `set()`은 pending 버퍼에 깊은 복사로 쓰고, superstep 경계에서 `commit()`된다. 같은 superstep에서 여러 실행기가 같은 키를 쓰면 마지막 쓰기가 이긴다.
- 체크포인트 저장소가 있으면 superstep마다 체크포인트를 만든다.
- 하나의 `Workflow` 인스턴스는 동시에 한 실행만 허용한다. 실행 중에 다시 `run()`을 호출하면 `WorkflowException("Workflow is already running; concurrent runs are not allowed on the same instance.")`가 발생한다(S11 869-872행, 실행 확인). 순차 재실행은 가능하다(실행 확인).

## 3. 기능 카탈로그

### 3.1 에이전트·세션·응답

출처: S2, S5, S6 1844-1925행, S7, S20.

| 기능 | API(정확한 이름·시그니처) | 동작 | 최소 예시 코드 | 출처 |
|---|---|---|---|---|
| 비스트리밍 실행 | `agent.run(messages=None, *, stream=False, session=None, middleware=None, options=None, function_invocation_kwargs=None, client_kwargs=None) -> Awaitable[AgentResponse]` (`AgentMiddlewareLayer.run` 시그니처; `**kwargs`를 받지 않는다) | 최종 `AgentResponse` 반환. Copilot 경로는 `send_and_wait(timeout=...)`를 쓰며 기본 제한 60초 | `r = await agent.run("질문", session=s)` | S5 1992-2005행, S2 960-1076행 |
| 스트리밍 실행 | `agent.run(..., stream=True) -> ResponseStream[AgentResponseUpdate, AgentResponse]` | `async for u in stream`로 갱신을 받고 `await stream.get_final_response()`로 최종 응답을 얻는다 | `async for u in agent.run(q, stream=True): print(u.text, end="")` | S2 905-931행 |
| 응답 타입 | `AgentResponse(messages, response_id, finish_reason, usage_details, additional_properties)`, `.text`, `.value`; `AgentResponseUpdate(role, contents, response_id, message_id, finish_reason, ...)`, `.text` | `.value`는 `response_format`이 있을 때만 채워진다 | `print(r.text, r.usage_details)` | `R/packages/core/agent_framework/_types.py` 3608행, 3423행 |
| 세션 | `AgentSession(*, session_id=None, service_session_id=None)`, `.state: dict`, `.to_dict()`, `AgentSession.from_dict(d)` | 로컬 ID, 서비스 세션 ID, 공급자 상태만 담는 가벼운 컨테이너 | `d = s.to_dict(); s2 = AgentSession.from_dict(d)` | S6 1844-1925행 |
| 서비스 세션 재개 | `agent.get_session(service_session_id, *, session_id=None)` | Copilot 세션 ID로 `AgentSession`을 만들어 다음 실행에서 `resume_session` | `s = agent.get_session("copilot-session-id")` | S7 545-565행, S2 1646-1716행 |
| 컨텍스트 공급자 | `class ContextProvider(source_id)`: `async before_run(*, agent, session, context: SessionContext, state)`, `async after_run(...)`; `SessionContext.extend_messages(source_id, msgs)`, `.extend_instructions(source_id, text)`, `.extend_tools(source_id, tools)` | 실행 전 메시지·지시문·도구 주입, 실행 후 응답 처리. Copilot 경로에서도 실행된다(1.x에서 수정됨) | 아래 3.1.1 | S6 516-830행, S2 1251-1290행, S20 PR #5013 |
| 기록 공급자 | `HistoryProvider`, `InMemoryHistoryProvider`, `FileHistoryProvider` | `Agent`는 공급자가 없으면 `InMemoryHistoryProvider`를 자동 추가한다. `GitHubCopilotAgent`의 `create_session()`은 자동 추가하지 않는다 | — | S6 988행, 2219행, S7 522-543행 |
| 에이전트 미들웨어 | `class AgentMiddleware(ABC): async process(context: AgentContext, call_next)`; 데코레이터 `@agent_middleware` | `run` 전후 가로채기. `GitHubCopilotAgent`에서 동작 | 아래 3.1.2 | S5 848행, 1186행, 1992-2106행 |
| 함수 미들웨어 | `class FunctionMiddleware(ABC): async process(context: FunctionInvocationContext, call_next)`; `@function_middleware` | `Agent`의 함수 호출 루프에서 실행. `GitHubCopilotAgent`에서는 `client_kwargs["middleware"]`로 넘어가지만 `RawGitHubCopilotAgent.run`이 `**kwargs`로 받아 버린다(동작하지 않음) | — | S5 920행, 2016-2025행, S2 859-904행 |
| 채팅 미들웨어 | `class ChatMiddleware(ABC)`; `@chat_middleware` | 채팅 클라이언트 호출 가로채기. Copilot 경로에는 채팅 클라이언트가 없어 해당 없음 | — | S5 1011행 |
| 함수 도구 | `@tool(func=None, *, name=None, description=None, schema=None, approval_mode=None, kind=None, max_invocations=None, max_invocation_exceptions=None, additional_properties=None, result_parser=None) -> FunctionTool` | 시그니처·`Annotated`·Pydantic에서 JSON 스키마 생성 | 아래 3.1.3 | S4 1666-1800행 |
| 승인 모드 | `ApprovalMode = Literal["always_require", "never_require"]`, 기본 `"never_require"` | `Agent`: 함수 호출 루프가 승인 요청 콘텐츠를 내고 멈춘다. `GitHubCopilotAgent`: SDK `on_pre_tool_use`가 `"ask"`를 돌려 `on_permission_request`로 보낸다 | — | S4 301행, S2 1497-1583행 |
| 실행 컨텍스트 주입 | 도구 파라미터를 `ctx: FunctionInvocationContext`로 선언. 속성: `function`, `arguments`, `session`, `metadata`, `result`, `kwargs`, `tools`, `parent_service_session_state_keys` | 이 파라미터는 모델용 스키마에서 빠진다. `kwargs`는 실행의 `function_invocation_kwargs` | 아래 3.1.3 | S5 428-560행, S4 770-790행, 1160-1180행 |
| 구조화 출력 | `options={"response_format": PydanticModel}` 또는 `default_options` | `Agent`에서 `AgentResponse.value`에 파싱 결과. `GitHubCopilotAgent`에서는 미지원(5.4) | `r = await chat_agent.run(q, options={"response_format": Out}); r.value` | S22, S24 #9809 |
| Copilot 실행 옵션 | `GitHubCopilotOptions`(TypedDict): `system_message`, `cli_path`, `model`, `timeout`, `log_level`, `on_permission_request`, `mcp_servers`, `provider`, `instruction_directories`, `skill_directories`, `disabled_skills`, `base_directory`, `enable_file_hooks`, `telemetry`, `on_pre_tool_use`, `on_function_approval`(사용 중단) | 나열되지 않은 키(`available_tools`, `excluded_tools`, `reasoning_effort`, `hooks`, `working_directory` 등)도 `create_session`/`resume_session`에 그대로 전달된다. 잘못된 키는 SDK에서 `TypeError` | `default_options={"model": "...", "timeout": 45}` | S2 498-607행, 1717-1804행 |
| Copilot 설정 환경변수 | `GITHUB_COPILOT_CLI_PATH`, `GITHUB_COPILOT_MODEL`, `GITHUB_COPILOT_TIMEOUT`, `GITHUB_COPILOT_LOG_LEVEL`, `GITHUB_COPILOT_BASE_DIRECTORY`, `GITHUB_COPILOT_TELEMETRY`(JSON) | 명시 인자 > .env > 환경변수 순 | — | S2 463-496행, 734-745행 |

#### 3.1.1 컨텍스트 공급자 예시

```python
from agent_framework import ContextProvider

class CaseContext(ContextProvider):
    def __init__(self, store):
        super().__init__(source_id="case_context")
        self._store = store

    async def before_run(self, *, agent, session, context, state):
        profile = self._store.get(session.state.get("run_id"))
        if profile:
            context.extend_instructions(self.source_id, f"<case_profile>{profile.model_dump_json()}</case_profile>")
```

Copilot 경로에서는 위 지시문이 시스템 메시지가 아니라 프롬프트 앞 텍스트로 들어간다(2.3).

#### 3.1.2 에이전트 미들웨어 예시

```python
from agent_framework import AgentMiddleware, AgentContext

class TimingMiddleware(AgentMiddleware):
    async def process(self, context: AgentContext, call_next):
        # context.agent, context.messages, context.session, context.stream, context.function_invocation_kwargs
        await call_next()
```

S5 2069-2080행 기준 `AgentContext`에는 `agent`, `messages`, `session`, `tools`, `options`, `stream`, `client_kwargs`, `function_invocation_kwargs`가 있다.

#### 3.1.3 함수 도구와 실행 컨텍스트 예시

```python
from typing import Annotated, Literal
from agent_framework import tool, FunctionInvocationContext

@tool
def check_eligibility(
    scheme_id: Annotated[str, "제도 ID"],
    ctx: FunctionInvocationContext,
) -> str:
    run_id = ctx.kwargs["run_id"]           # run(..., function_invocation_kwargs={"run_id": ...})
    agent_session = ctx.session             # 실행에 쓴 AgentSession
    ...

@tool(approval_mode="always_require")
def finalize_referral(scheme_ids: list[str], note: str) -> str:
    ...
```

### 3.2 GitHubCopilotAgent 세부

출처: S2, S3, S19, S21, S25.

| 기능 | API | 동작 | 최소 예시 코드 | 출처 |
|---|---|---|---|---|
| 공유 클라이언트 | `GitHubCopilotAgent(..., client=copilot_client)` | 여러 에이전트가 CLI 프로세스 하나를 공유. 에이전트 `stop()`은 공유 클라이언트를 멈추지 않음 | 아래 3.2.1 | S2 698-699행, 806-817행 |
| 도구 변환 | `FunctionTool` → `copilot.tools.Tool(name, description, handler, parameters=ai_func.parameters())`. `CopilotTool` 인스턴스와 dict는 그대로 통과. `MCPTool`은 `TypeError` | 핸들러가 `FunctionInvocationContext(function, arguments, session=agent_session, kwargs=function_invocation_kwargs)`를 만들어 `ai_func.invoke(...)` 호출. 예외는 `ToolResult(result_type="failure", text_result_for_llm="Error: ...")`로 모델에 돌려준다. 텍스트 외 결과(`data`, `uri`)는 버려진다 | — | S2 1364-1495행 |
| `skip_permission` | 변환된 `Tool`은 `skip_permission=False`(SDK 기본값) | SDK는 `skip_permission=False` 사용자 도구 호출마다 `PermissionRequestCustomTool(kind="custom-tool")`를 `on_permission_request`에 보낸다(`copilot-sdk.md` 확인: SDK e2e `test_invokes_custom_tool_with_permission_handler`). 기본 처리기(`_deny_all_permissions`)는 이를 거부한다 | — | S2 227-232행, 1490-1495행, S25 `tools.py` 110행, `session_events.py` 8340행 |
| 승인 hook | 기본 `on_pre_tool_use`: `always_require` 도구에 `{"permissionDecision": "ask", ...}`, 나머지는 `None` | `"ask"`는 `on_permission_request`로 간다. 사용자 `on_pre_tool_use`나 `hooks={"on_pre_tool_use": ...}`가 있으면 기본 hook을 설치하지 않고 경고만 남긴다 | — | S2 1497-1583행, S3 |
| 권한 결정 정규화 | 처리기가 `PermissionDecisionApproveForSession()`을 범위 없이 돌려주면 요청 종류에 맞춰 범위를 채우거나 `PermissionDecisionApproveOnce()`로 좁힌다 | CLI 충돌(`commandIdentifiers`) 방지 | — | S2 309-401행 |
| 스트리밍 이벤트 매핑 | `ASSISTANT_MESSAGE_DELTA` → 텍스트 `AgentResponseUpdate`; `ASSISTANT_USAGE` → usage 콘텐츠; `TOOL_EXECUTION_START` → `Content.from_function_call(..., hosted=True)`; `TOOL_EXECUTION_COMPLETE` → `role="tool"`, `Content.from_function_result(...)`; `SESSION_IDLE` → 스트림 종료; `SESSION_ERROR` → `AgentException` | 비스트리밍 경로는 최종 `ASSISTANT_MESSAGE` 하나만 메시지로 만든다 | `for c in u.contents: if c.type == "function_call": ...` | S2 1141-1250행, 1047-1076행 |
| 파일 hook | `enable_file_hooks` 기본 `False` | 작업 디렉터리 `.github/hooks/`를 읽지 않는다 | — | S2 567-573행, S20 python-1.18.0 |
| 실행별 옵션 | `run(..., options={"system_message": {...}, "model": ...})` | `default_options` 위에 덮어쓴다. `on_function_approval`은 실행별 지정 금지(`ValueError`) | S21 `runtime_options_example` | S2 975-988행 |

#### 3.2.1 공유 클라이언트 예시

```python
from copilot import CopilotClient
from agent_framework.github import GitHubCopilotAgent, GitHubCopilotOptions

client = CopilotClient()          # 앱 시작 시 1회
await client.start()

profiler = GitHubCopilotAgent(
    instructions=PROFILER_PROMPT,
    client=client,
    name="profiler",
    tools=[record_case_profile],
    default_options=GitHubCopilotOptions(
        model="gpt-5",
        timeout=45,
        system_message={"mode": "replace", "content": PROFILER_PROMPT},
        on_permission_request=permission_handler,
    ),
)
```

`CopilotClient` 생성자의 토큰·연결 인자는 Copilot SDK 명세 문서를 따른다(이 문서 범위 밖).

### 3.3 Workflow

출처: S8-S15, S22, S20, 실행 확인.

| 기능 | API | 동작 | 최소 예시 코드 | 출처 |
|---|---|---|---|---|
| 빌더 | `WorkflowBuilder(max_iterations=100, name=None, description=None, *, start_executor, checkpoint_storage=None, output_from=..., intermediate_output_from=..., output_executors=...(사용 중단))` | `start_executor`는 키워드 전용 필수 인자 | `WorkflowBuilder(start_executor=intake)` | S8 91-170행 |
| 단일 간선 | `add_edge(source, target, condition=None)` | `condition(data) -> bool \| Awaitable[bool]` | `.add_edge(a, b)` | S8 230-280행 |
| fan-out | `add_fan_out_edges(source, targets: Sequence[...])` | 메시지를 모든 대상에 동시에 전달 | `.add_fan_out_edges(p, [m1, m2, m3])` | S8 282-336행 |
| fan-in | `add_fan_in_edges(sources: Sequence[...], target)` | 모든 원천이 메시지를 하나 이상 보낼 때까지 버퍼링 후 `list`로 한 번 전달. 순서는 `sources` 나열 순서 | `.add_fan_in_edges([m1, m2, m3], v)` | S8 511-564행, S9 390-500행 |
| switch-case | `add_switch_case_edge_group(source, cases: Sequence[Case \| Default])`, `Case(condition=..., target=...)`, `Default(target=...)` | 첫 번째로 참인 조건의 대상 하나로 전달 | S8 예시 | S8 338-423행 |
| 다중 선택 | `add_multi_selection_edge_group(source, targets, selection_func: (message, list[str]) -> list[str])` | 선택된 실행기 ID들로 전달 | — | S8 425-509행 |
| 체인 | `add_chain(executors)` | 순차 간선 일괄 추가 | — | S8 566-618행 |
| 에이전트 직접 노드 | 빌더 메서드에 `SupportsAgentRun`을 넘기면 `AgentExecutor(agent, id=resolve_agent_id(agent))`로 감싼다 | 이름/ID 중복이면 `ValueError` | `.add_edge(intake, profiler_agent)` | S8 191-228행 |
| 실행기 | `class X(Executor)`; `__init__(id)`; `@handler async def h(self, msg: T, ctx: WorkflowContext[OutT, W_OutT])`; 명시형 `@handler(input=..., output=..., workflow_output=...)`; 함수형 `@executor(id=...)` | `WorkflowContext[OutT]`의 `OutT`는 `send_message` 타입, `W_OutT`는 `yield_output` 타입 | S8 60-86행 예시 | S15 `_executor.py` 573-602행, S12 37-114행 |
| 메시지 전달 | `await ctx.send_message(message, target_id=None)` | 다음 superstep에 간선을 따라 전달 | — | S12 319-349행 |
| 출력 | `await ctx.yield_output(output)` | `output_from`/`intermediate_output_from` 설정에 따라 `type="output"` 또는 `"intermediate"` 이벤트. 목록에 없는 실행기의 출력은 숨겨진다 | — | S12 351-381행, S8 118-143행 |
| 사용자 이벤트 | `await ctx.add_event(WorkflowEvent(type, data=...))` | `output`/`intermediate`/`started`/`status`/`failed`는 실행기가 직접 낼 수 없어 경고 이벤트로 바뀐다. 그 외 문자열(예: `"progress"`)은 실행 시 그대로 전달된다(실행 확인). 단 `WorkflowEventType`이 `Literal`이라 타입 검사기는 경고한다 | `await ctx.add_event(WorkflowEvent("progress", data={...}))` | S12 383-402행, S13 129-155행 |
| 상태 | `ctx.get_state(key, default=None)`, `ctx.set_state(key, value)`, `ctx.state` | superstep 경계 커밋, 깊은 복사, `_` 접두 키는 예약 | — | S12 437-466행, S15 `_state.py` |
| 사람 개입 요청 | `await ctx.request_info(request_data, response_type, *, request_id=None)` + `@response_handler async def r(self, original_request: Req, response: Resp, ctx)` | `type="request_info"` 이벤트(`request_id`, `source_executor_id`, `data`, `response_type`). 실행은 `IDLE_WITH_PENDING_REQUESTS`로 끝난다 | 아래 3.3.1 | S12 404-435행, S15 `_request_info_mixin.py` 121-200행 |
| 응답 재개 | `workflow.run(responses={request_id: value}, stream=True)` | 대기 요청에 응답을 넣고 이어서 실행 | 아래 3.3.1 | S11 801-856행, 1077-1145행 |
| 실행 | `workflow.run(message=None, *, stream=False, responses=None, checkpoint_id=None, checkpoint_storage=None, include_status_events=False, tools=None, function_invocation_kwargs=None, client_kwargs=None)` | `stream=True`: `ResponseStream[WorkflowEvent, WorkflowRunResult]`. 비스트리밍: `WorkflowRunResult`(`.get_outputs()`) | `async for ev in wf.run(m, stream=True): ...` | S11 769-899행 |
| 실행 kwargs | `function_invocation_kwargs`: 평면 dict면 모든 `AgentExecutor`에, 최상위 키가 실행기 ID면 해당 실행기에만 | `AgentExecutor`만 읽는다. 사용자 `Executor` 안에서 직접 `agent.run`을 부를 때는 직접 넘겨야 한다 | — | S14 807-845행, S20 PR #5010 |
| 체크포인트 | `InMemoryCheckpointStorage()`, `FileCheckpointStorage(storage_path, *, allowed_checkpoint_types=None)`; `CheckpointStorage` 프로토콜(`save`, `load`, `list_checkpoints`, `delete`, `get_latest`, `list_checkpoint_ids`); 실행기 훅 `on_checkpoint_save()`, `on_checkpoint_restore(state)` | superstep마다 저장, fan-in 버퍼도 저장. `FileCheckpointStorage`는 pickle 사용 | `wf.run(checkpoint_id=cid, checkpoint_storage=st)` | S15 `_checkpoint.py` 134-600행, S9 402-441행, S20 PR #3744 |
| 하위 워크플로 | `WorkflowExecutor(workflow, id, allow_direct_output=False, propagate_request=False)`; 요청 가로채기 메시지 `SubWorkflowRequestMessage`, `SubWorkflowResponseMessage` | 워크플로를 실행기로 중첩. 같은 하위 워크플로 인스턴스를 공유하면 안 된다 | — | S15 `_workflow_executor.py` 152-310행 |
| 에이전트로 감싸기 | `workflow.as_agent(name=None, *, description=None, context_providers=None, **kwargs) -> WorkflowAgent` | 시작 실행기가 `list[Message]`를 받아야 한다. `output`, `intermediate`, `data`, `request_info` 이벤트만 에이전트 갱신으로 전달 | — | S11 1572-1600행, S13 158-168행 |
| 함수형 워크플로 | `@workflow`, `@step`, `RunContext`, `get_run_context()` | 실험 기능(`ExperimentalFeature.FUNCTIONAL_WORKFLOWS`) | — | S15 `_functional.py` 543행, 1692행, 2708행 |
| 시각화 | `WorkflowViz` | 그래프 출력 | — | `agent_framework.__all__` |

#### 3.3.1 사람 개입(HITL) 예시 (실행 확인)

```python
from dataclasses import dataclass
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler, response_handler

@dataclass
class ApprovalRequest:
    run_id: str
    scheme_ids: list[str]
    summary: str

class ApprovalGate(Executor):
    @handler
    async def on_draft(self, draft: "DraftResult", ctx: WorkflowContext) -> None:
        await ctx.request_info(ApprovalRequest(draft.run_id, draft.scheme_ids, draft.summary), bool)

    @response_handler
    async def on_decision(self, req: ApprovalRequest, approved: bool,
                          ctx: WorkflowContext[Never, "Finalized"]) -> None:
        await ctx.yield_output(finalize_referral_code(req) if approved else keep_draft(req))

# 1차 실행: request_info 이벤트 수집
pending = {ev.request_id: ev.data async for ev in wf.run(msg, stream=True) if ev.type == "request_info"}
# 승인 API 수신 후 재개
async for ev in wf.run(stream=True, responses={request_id: True}):
    ...
```

#### 3.3.2 워크플로 이벤트 종류

출처: S13 129-155행, 실행 확인.

| `event.type` | 주요 필드 | 발생 |
|---|---|---|
| `started` | — | 실행 시작 |
| `status` | `.state: WorkflowRunState` (`STARTED`, `IN_PROGRESS`, `IN_PROGRESS_PENDING_REQUESTS`, `IDLE`, `IDLE_WITH_PENDING_REQUESTS`, `FAILED`, `CANCELLED`) | 상태 전이 |
| `failed` | `.details: WorkflowErrorDetails` | 실행 실패(이후 예외가 호출자에게 다시 발생) |
| `output` / `intermediate` | `.executor_id`, `.data` | `yield_output` |
| `data` | — | 사용 중단된 별칭 |
| `request_info` | `.request_id`, `.source_executor_id`, `.data`, `.request_type`, `.response_type` | `ctx.request_info` |
| `warning` / `error` | `.data` | 사용자 코드 진단 |
| `superstep_started` / `superstep_completed` | `.iteration` | superstep 경계 |
| `executor_invoked` / `executor_completed` / `executor_failed` / `executor_bypassed` | `.executor_id`, `.data` 또는 `.details` | 실행기 수명주기 |
| `group_chat`, `handoff_sent`, `magentic_orchestrator` | `.data` | 오케스트레이션 내부 |

이벤트는 superstep이 끝나기를 기다리지 않고 발생 즉시 스트림으로 나온다. 러너가 반복 작업과 `next_event()`를 함께 기다리는 구조다(S10 128-146행). 실행 확인 결과, fan-out 분기의 `intermediate` 이벤트가 각 분기 `executor_completed` 전에 나왔다.

### 3.4 Orchestrations 패키지

출처: S16, S24 #3572, S20.

| 빌더 | 생성자(핵심 인자) | GitHubCopilotAgent 사용 | 비고 |
|---|---|---|---|
| `SequentialBuilder` | `(*, name=None, participants: Sequence[SupportsAgentRun \| Executor], checkpoint_storage=None, chain_only_agent_responses=False, output_from=..., intermediate_output_from=None, ensure_trailing_user_turn=False)`; `.with_request_info(agents=None)` | 가능(타입이 `SupportsAgentRun`) | 이전 대화 전체가 다음 참가자에 전달된다. Copilot 경로에서는 텍스트로 합쳐진다(2.3) |
| `ConcurrentBuilder` | `(*, name=None, participants, checkpoint_storage=None, output_from=..., intermediate_output_from=None)`; `.with_aggregator(executor \| callback(list[AgentExecutorResponse]) )`; `.with_request_info()` | 가능 | 내부 구성: dispatcher → fan-out → participants → fan-in → aggregator. 기본 집계는 참가자별 assistant 메시지를 담은 `AgentResponse` 하나 |
| `HandoffBuilder` | `(*, name=None, participants: Sequence[Agent] \| None, ...)` | 불가. `Agent` 인스턴스가 아니면 `TypeError("Participants must be Agent instances ... rely on cloning, tool injection, and middleware capabilities.")` | S16 `_handoff.py` 770-780행, 지원 요청 이슈 #3572 open |
| `GroupChatBuilder` | `(*, participants, participant_factories, orchestrator_agent: Agent \| Callable[[], Agent] \| None, orchestrator, selection_func, termination_condition, max_rounds, ...)` | 참가자로는 가능. `orchestrator_agent`는 타입이 `Agent`이고 `options={"response_format": AgentOrchestrationOutput}`를 사용하므로 Copilot 에이전트에는 부적합 `[추론]` | `selection_func`로 결정적 화자 선택 가능 |
| `MagenticBuilder` | `(*, participants, manager=None, manager_factory=None, manager_agent: SupportsAgentRun \| None, manager_agent_factory=None, ...)`; `.with_plan_review()`, `.with_checkpointing()` | 참가자·`manager_agent` 타입상 가능. 표준 관리자는 응답 텍스트에서 JSON을 파싱한다(`json.loads`) | 계획 검토 HITL 내장 |

### 3.5 관측성(OpenTelemetry)

출처: S17 1501-1720행, S18, 실행 확인.

| 기능 | API | 동작 | 출처 |
|---|---|---|---|
| 공급자 구성 | `configure_otel_providers(*, service_name=None, service_version=None, resource_attributes=None, otlp_endpoint=None, otlp_protocol=None, otlp_headers=None, otlp_timeout=None, otlp_compression=None, enable_sensitive_data=None, enable_console_exporters=None, enable_message_events=None, otel_semconv_stability_opt_in=None, exporters=None, views=None, vs_code_extension_port=None, env_file_path=None, env_file_encoding=None)` | 추적·로그·지표 공급자 생성 후 계측 활성화. 한 번만 호출. `opentelemetry-sdk` 필요 | S17 1605행 |
| 서드파티 구성 후 활성화 | `enable_instrumentation(*, enable_sensitive_data=None, enable_message_events=None, force=False)` | `configure_azure_monitor(...)` 다음에 호출하는 패턴을 Learn이 제시 | S17 1558행, S18 |
| 민감 데이터 | `enable_sensitive_data` 인자 또는 `ENABLE_SENSITIVE_DATA`(기본 false); `enable_sensitive_telemetry(*, force=False)`는 켜는 함수 | 켜면 프롬프트·응답·도구 인자·결과·예외 메시지 기록 | S17 1501행, S18 425-426행 |
| 계측 끄기 | `ENABLE_INSTRUMENTATION=false`, `disable_instrumentation()` | 1.6.0부터 계측이 기본 활성 | S20 python-1.6.0, S18 |
| 스팬 | `invoke_agent <agent_name>`, `chat <model>`, `execute_tool <function_name>`, 워크플로 `workflow.build`, `workflow.run`, `executor.process`, `edge_group.process`, `message.send` | Copilot 경로: `invoke_agent`(`AgentTelemetryLayer`)와 `execute_tool`(`FunctionTool.invoke` 내부)은 생성된다. 모델 호출은 CLI가 하므로 프레임워크 `chat` 스팬은 없다 `[추론]`. CLI 자체 추적은 `GitHubCopilotOptions.telemetry`/`TelemetryConfig`로 따로 설정 | S17 224-345행, S4 1180-1260행, S2 575-576행 |

Application Insights 연결 예시(Learn 패턴 3):

```python
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import create_resource, enable_instrumentation

configure_azure_monitor(connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
                        resource=create_resource())
enable_instrumentation(enable_sensitive_data=False)
```

`configure_otel_providers(exporters=[AzureMonitorTraceExporter(...), ...])`처럼 내보내기 객체를 직접 넘기는 패턴 2도 가능하다(S18 306-322행).

### 3.6 DevUI와 AG-UI/FastAPI 호스팅

출처: S23, S20 python-1.23.0, S24 #8753.

| 기능 | API | 동작 | 동행노트 적합성 |
|---|---|---|---|
| DevUI | `from agent_framework.devui import serve; serve(entities=[agent_or_workflow], auto_open=True)`; CLI `devui ./agents --port 8080` | 에이전트·워크플로 실행과 추적을 보는 개발용 UI(beta). `GET /v1/entities` 등 API 제공 | 개발·시연 녹화용. 운영 UI는 아님 |
| AG-UI 엔드포인트 | `from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint; add_agent_framework_fastapi_endpoint(app, agent_or_workflow, "/", single_user=True)` | FastAPI 앱에 AG-UI 프로토콜(SSE) 엔드포인트 추가. 1.23.0부터 권한 소유 모드 지정 필수 | 자체 SSE 프로토콜과 중복. 승인 인터럽트는 `function_approval_request` 기반인데 Copilot 에이전트는 이를 내지 않는다(#8753 open) |
| 스레드별 워크플로 | `AgentFrameworkWorkflow(workflow_factory=lambda thread_id: build(), name=...)` | 요청 대기 상태를 스레드별로 분리 | 실행별 워크플로 생성 원칙과 같다 |

## 4. 주의점·제약

출처: 각 항목에 표기.

1. `GitHubCopilotAgent`는 `response_format`을 지원하지 않는다. 옵션이 `create_session` kwargs에 그대로 섞이고(실행 확인: 세션 kwargs 키에 `response_format` 포함), SDK `create_session`에는 그런 인자가 없어 `TypeError`가 난다(실행 확인: `"response_format" in signature(CopilotClient.create_session).parameters == False`). SDK 자체는 `send(..., response_schema=...)`로 strict JSON schema를 지원하지만(S25 `session.py` 2166-2203행) MAF가 전달하지 않는다. 지원 요청 이슈 #9809가 open이다(S24).
2. 함수·채팅 미들웨어는 Copilot 경로에서 실행되지 않는다. 실행별 `middleware=`에 넣은 함수 미들웨어도 무시된다(S2 899-904행, S5 2016-2025행).
3. `FunctionInvocationContext.tools`는 Copilot 경로에서 `None`이다. `ctx.add_tools()`(점진적 도구 노출)를 쓸 수 없다(S2 1456-1462행에서 `tools=`를 넘기지 않음).
4. 스트리밍 실행에는 제한 시간이 없다. `timeout`(기본 60초)은 비스트리밍 `send_and_wait`에만 적용된다. `_stream_updates`는 `SESSION_IDLE`까지 큐를 기다린다(S2 1236-1250행). 스트리밍에서 제한 시간이 필요하면 호출자가 `asyncio.timeout(...)`으로 감싸야 한다. 취소 시 프레임워크는 이벤트 구독만 해제하며, CLI 쪽 진행 중인 턴을 중단하는 코드는 없다 `[추론]`. 중단 API는 Copilot SDK 명세를 따른다.
5. 스트리밍 usage 집계 버그: 여러 모델 호출이 있는 스트리밍 실행은 마지막 호출 usage만 남는다(이슈 #10087 open). 비스트리밍은 합산이 맞다(S2 1003-1022행).
6. 사용자 도구도 Copilot 권한 요청 대상이다. MAF가 만든 `Tool`은 `skip_permission=False`이므로 기본 거부 처리기에서는 앱의 도구가 모두 거부된다. 처리기는 `kind == "custom-tool"`이고 `tool_name`이 허용 목록에 있을 때 승인해야 한다(S2 227-232행, S25; `copilot-sdk.md`의 SDK e2e 테스트 확인).
7. 사용자 `on_pre_tool_use`를 넣으면 `always_require` 자동 보호가 꺼진다(S2 1549-1557행, S3).
8. 핸드오프 오케스트레이션은 `Agent` 전용이다(S16 `_handoff.py` 775행).
9. 한 `Workflow` 인스턴스는 동시 실행을 막는다. 실행기 인스턴스도 상태를 가지므로(`AgentExecutor`는 메시지 캐시와 세션을 보유, S14 309-352행) 동시 상담마다 워크플로와 실행기를 새로 만들어야 한다.
10. 한 분기의 예외는 워크플로 전체를 실패시킨다(5.5).
11. 같은 `AgentSession`으로 동시에 실행하면 잠금 때문에 직렬화된다(S2 1585-1645행). 병렬 매칭 세 분기는 에이전트별·실행별로 다른 `AgentSession`을 써야 병렬로 돈다.
12. `AgentExecutor`에 `GitHubCopilotAgent`를 직접 넣으면 기본 `context_mode="full"`로 누적 메시지 전체를 다시 보낸다. Copilot 세션도 이력을 보관하므로 이전 턴이 중복 전달될 수 있다 `[추론]`(S14 309-340행, S2 1024-1027행).
13. `GitHubCopilotAgent`에 `HistoryProvider`를 붙이면 공급자가 이력을 프롬프트 텍스트로 다시 넣고 CLI 세션도 이력을 가지므로 중복된다 `[추론]`(S2 1251-1290행).
14. 세션 직렬화: `AgentSession.to_dict()`에는 Copilot 세션 ID만 들어간다. 대화 내용은 CLI가 `base_directory`(기본 `~/.copilot`)에 보관한다(S2 479-482행). 컨테이너 재시작 후 재개 가능 여부는 CLI 저장 위치의 영속성에 달려 있다 `[추론]`.
15. Learn의 GitHub Copilot 페이지(Python) 도구 표는 Tool Approval을 “framework's function-invoking chat client가 제공”한다고 적지만, 1.24.0/2.1.1 소스는 SDK `on_pre_tool_use` hook으로 처리한다(S19 680행 vs S2 1497-1583행). 소스를 기준으로 한다.
16. Learn 관측성 페이지는 `opentelemetry-sdk`가 기본 설치된다고 적지만 1.24.0 휠은 설치하지 않는다(1.2).

## 5. 동행노트 설계(TRD) 검증

TRD: [`TRD.md`](../../TRD.md).

### 5.1 TRD 가정별 판정

| # | TRD 가정(위치) | 판정 | 올바른 API·근거 |
|---|---|---|---|
| A1 | 패키지 `agent-framework-core` 1.24.x, `orchestrations` 1.4.x, `github-copilot` 2.1.x, `github-copilot-sdk` 1.0.x (1절) | 맞음 | 1.24.0 / 1.4.1 / 2.1.1 / 1.0.28 (S1). `opentelemetry-sdk`, `azure-monitor-opentelemetry`를 추가해야 한다 |
| A2 | 공유 `CopilotClient`를 `client=`로 모든 에이전트에 넘긴다 (2절) | 맞음 | `GitHubCopilotAgent(..., client=client)`; `_owns_client=False`; `CopilotClient.start()` 멱등(S2 698-817행, S25) |
| A3 | `WorkflowBuilder(start_executor=intake).add_edge(...).add_fan_out_edges(profiler, [...]).add_fan_in_edges([...], verifier).add_edge(...).build()` (3.2절) | 맞음 | 시그니처 일치(S8 282, 511행). 실행 확인 |
| A4 | Verifier가 `MatchResult ×3`을 받는다 (표 2) | 부분적으로 맞음 | fan-in 대상 핸들러는 `list[MatchResult]`를 받아야 한다. 순서는 `add_fan_in_edges` 원천 나열 순서, 원천이 여러 메시지를 보내면 모두 포함(S9 485-490행, 실행 확인: `['a:hi','b:hi','c:hi']`) |
| A5 | “한 분야 실패가 다른 분야를 막지 않는다” (표 2, 7절) | 틀림(기본 동작 기준) | 한 분기가 예외를 던지면 같은 superstep의 다른 분기는 취소되고 `executor_failed` → `failed` → `status(FAILED)` 이벤트 후 예외가 호출자에게 다시 발생한다. fan-in은 실행되지 않는다(5.5). 실행기 안에서 예외를 잡아 실패 표시 `MatchResult`를 `send_message`해야 한다 |
| A6 | 실행기 안에서 `GitHubCopilotAgent.run(..., session=..., stream=True)` 호출 (3.2절) | 맞음 | S2 846-931행 |
| A7 | 진행 이벤트를 `ctx.add_event(...)`로 내보낸다 (3.2절) | 부분적으로 맞음 | `ctx.add_event(WorkflowEvent("progress", data=...))`는 실행 시 동작하지만(실행 확인) `WorkflowEventType` Literal 밖이라 타입 검사 경고가 난다. `output`/`intermediate`/`started`/`status`/`failed`는 실행기가 낼 수 없다(S12 383-402행). 공식 경로는 `yield_output` + `intermediate_output_from`(5.7) |
| A8 | API가 `workflow.run(message, stream=True)` 이벤트를 SSE로 바꾼다 (3.2절) | 맞음 | S11 769-899행. 단 상담마다 워크플로를 새로 만들어야 한다(A9) |
| A9 | 프로세스당 동시 실시간 실행 4건 (7절) — 워크플로 인스턴스 공유 여부 미기재 | 부분적으로 맞음 | 같은 `Workflow`에서 동시 `run`은 `WorkflowException`(실행 확인). `build_workflow(run_ctx)` 팩토리로 실행마다 생성해야 한다. 에이전트 객체는 공유 가능, `AgentSession`은 실행·에이전트별 분리 |
| A10 | 에이전트별 `AgentSession`을 보관해 후속 질문(F9)에 재사용 (3.2절) | 맞음 | 같은 `AgentSession`이면 `resume_session(service_session_id)`(S2 1646-1716행). 메모리 보관 30분 정책과 일치 |
| A11 | `check_eligibility`가 `FunctionInvocationContext`의 `ctx.kwargs["run_id"]`로 상태를 읽는다 (3.3절) | 부분적으로 맞음 | 동작한다. 단 `agent.run(..., function_invocation_kwargs={"run_id": run_id})`로 넘겨야 한다. `agent.run(..., run_id=...)`는 `TypeError`(실행 확인). `workflow.run(function_invocation_kwargs=...)`는 `AgentExecutor`에만 전달되므로 TRD의 사용자 실행기 설계에서는 실행기가 직접 넘긴다(5.2) |
| A12 | `finalize_referral`에 `@tool(approval_mode="always_require")` (표 3) | 부분적으로 맞음 | Copilot 경로에서 기본 `on_pre_tool_use`가 `"ask"`를 돌려 `on_permission_request`로 보낸다(5.3). 프레임워크 승인 콘텐츠(`function_approval_request`)는 나오지 않는다 |
| A13 | “실행 전 hook이 `ask`를 돌려주고 `on_permission_request` 처리기가 호출된다” (3.5절 2) | 맞음 | S2 1568-1582행, S3. 이때 들어오는 요청 종류는 `PermissionRequestHook(kind="hook")`일 가능성이 높으나 `[미확인]`(5.3) |
| A14 | 처리기가 Copilot 내장 권한 요청을 모두 거부하고 “앱이 등록한 함수 도구만 실행된다” (3.5절 5) | 부분적으로 맞음 | 사용자 도구도 `custom-tool` 권한 요청을 거친다(4절 6). 처리기는 `custom-tool` + 허용 목록 도구를 승인하고 나머지 종류를 거부해야 한다. 모두 거부하면 `search_schemes` 등도 실행되지 않는다 |
| A15 | Copilot SDK 세션에서 응답 형식 강제를 기대하지 않고 도구 인자로 구조화 결과를 받는다 (3.6절) | 맞음 | `GitHubCopilotAgent`는 `response_format` 미지원(4절 1). 도구 인자 방식은 `FunctionTool.invoke`가 Pydantic 검증을 하므로 타당하다(S2 1463-1471행) |
| A16 | 모델 호출 제한 시간 45초 (7절) | 부분적으로 맞음 | `default_options={"timeout": 45}`는 비스트리밍에만 적용된다. 스트리밍 실행은 `asyncio.timeout(45)`로 감싸야 한다(4절 4) |
| A17 | `configure_otel_providers` + Azure Monitor exporter (표 5) | 맞음 | `configure_otel_providers(exporters=[...])` 또는 `configure_azure_monitor(...)` + `enable_instrumentation()`(S18). `opentelemetry-sdk` 설치 필요 |
| A18 | OpenTelemetry 민감 데이터 기록 `enable_sensitive_telemetry`를 끈다 (8절) | 부분적으로 맞음 | `enable_sensitive_telemetry()`는 켜는 함수다. 끄는 설정은 `ENABLE_SENSITIVE_DATA=false`(기본값) 또는 `enable_sensitive_data=False` 인자(S17 1501행, S18 426행) |
| A19 | `available_tools` 제한 | 부분적으로 맞음 | `default_options`의 미기재 키는 `create_session`에 그대로 전달되므로 `available_tools`/`excluded_tools` 지정은 가능하다(S2 498-508행, S25 2458-2459행). 사용자 도구를 목록에 포함해야 하는지 등 SDK 의미는 `[미확인]`(Copilot SDK 명세 참조) |
| A20 | 도구 호출을 SSE `tool_call`로 보낸다 (5절 API) | 맞음 | 스트리밍 갱신에 `function_call`(hosted=True)과 `function_result`(role="tool") 콘텐츠가 온다(S2 1182-1220행) |

### 5.2 GitHubCopilotAgent를 통한 함수 도구의 실행별 컨텍스트

- 결론: 동작한다. 조건은 `function_invocation_kwargs`로 넘기는 것이다.
- 근거: `RawGitHubCopilotAgent.run`은 `function_invocation_kwargs`를 받아 `_session_run_scope` → `_build_session_kwargs` → `_prepare_tools` → `_tool_to_copilot_tool`로 전달한다. 핸들러는 호출마다 `FunctionInvocationContext(function=ai_func, arguments=args, session=agent_session, kwargs=runtime_kwargs, ...)`를 만든다(S2 1405-1495행). 1.x 초기의 누락 버그는 #8865로 수정·종료되었다(S24).
- 실행 확인: `_build_session_kwargs(..., agent_session=AgentSession(session_id="S1"), function_invocation_kwargs={"run_id": "R1"})`로 만든 도구 핸들러를 `ToolInvocation(arguments={"scheme_id": "S9"})`로 호출하자 결과가 `S9|run=R1|sess=S1`이었다. `ctx` 파라미터는 모델용 스키마에서 빠졌다(`required: ["scheme_id"]`).
- 주의: `agent.run(..., run_id=...)`처럼 임의 키워드를 넘기면 `AgentMiddlewareLayer.run()`이 `TypeError`를 낸다(실행 확인). 실행기 구현은 다음과 같다.

```python
class MatchExecutor(Executor):
    def __init__(self, id: str, agent: GitHubCopilotAgent):
        super().__init__(id=id)
        self._agent = agent

    @handler
    async def run(self, profile: ProfileMessage, ctx: WorkflowContext[MatchResult, AgentResponseUpdate]) -> None:
        session = profile.sessions[self.id]          # 실행별 AgentSession
        stream = self._agent.run(
            build_prompt(profile),
            stream=True,
            session=session,
            function_invocation_kwargs={"run_id": profile.run_id, "domain": self.id},
        )
        ...
```

- 대안: `ctx.session.state`(실행별 `AgentSession.state`)에 `run_id`를 넣어도 도구에서 읽을 수 있다(S2 1456-1462행).

### 5.3 `approval_mode="always_require"`와 GitHubCopilotAgent

- 결론: 동작하지만 메커니즘이 `Agent`와 다르다.
- `Agent`(채팅 클라이언트 경로): 함수 호출 루프가 `function_approval_request` 콘텐츠를 응답에 넣고 멈춘다. 호출자가 승인 응답을 다음 `run`에 넣어 재개한다(S4 1766-1769행 “this only applies to the auto-invocation flow”).
- `GitHubCopilotAgent`: `on_pre_tool_use`를 직접 주지 않으면 기본 hook이 `always_require` 도구에 `{"permissionDecision": "ask"}`를 돌려주고 결정이 `on_permission_request`로 간다(S2 1497-1583행, 실행 확인: `finalize`에는 `ask`, `check`에는 `None`). 처리기가 없으면 기본 거부(`PermissionDecisionUserNotAvailable`)다. 승인 대기는 처리기 콜백 안에서 일어나므로, 도구 호출 중인 SDK 턴이 끝나지 않은 채 기다린다. 실행 상태가 프로세스 메모리에만 있고 체크포인트할 수 없다.
- 사용 중단된 `on_function_approval` 콜백도 있으나 `DeprecationWarning`을 내고 `on_pre_tool_use`와 함께 쓸 수 없다(S2 594-607행, 717-732행).
- `[미확인]`: `"ask"` 경로에서 `on_permission_request`가 받는 객체가 `PermissionRequestHook(kind="hook", tool_name, hook_message, tool_args, tool_call_id)`인지 `PermissionRequestCustomTool`인지 문서·테스트로 확인하지 못했다(`copilot-sdk.md`에서도 미확인). 처리기는 두 종류 모두에서 `tool_name == "finalize_referral"`을 검사하도록 작성한다.
- AG-UI/DevUI에서 Copilot 도구 승인을 대화형으로 띄우는 기능은 없다(이슈 #8753 open).

### 5.4 GitHubCopilotAgent의 `response_format`/구조화 출력

- 결론: 지원하지 않는다.
- 근거: `_agent.py`에 `response_format`/`response_schema` 처리 코드가 없다(소스 검색 결과 0건). `options`/`default_options`의 키는 `create_session`에 그대로 전달되며(S2 1717-1804행), 실행 확인 결과 세션 kwargs에 `response_format`이 남았고 SDK `create_session` 시그니처에는 해당 인자가 없다. `AgentResponse.value`는 채워지지 않는다. 이슈 #9809(open)가 같은 내용을 보고한다.
- 대안 1(TRD 현행): 구조화 결과를 도구 인자(Pydantic 스키마)로 받는다. `FunctionTool.invoke`가 인자를 검증한다.
- 대안 2: SDK 세션 직접 호출(`CopilotSession.send(prompt, response_schema=Model)`, S25 `session.py` 2192-2201행)은 MAF 에이전트 추상화를 우회하므로 이 문서는 권하지 않는다.
- 대안 3: 도구 계약 쪽에 `copilot.tools.Tool(is_terminal=True)`를 쓰면 성공한 도구 호출로 턴을 끝낼 수 있다(S25 `tools.py` 113-117행). 다만 MAF가 변환하는 `FunctionTool`에는 이 속성을 지정할 방법이 없고, `CopilotTool`을 직접 넘기면 `FunctionInvocationContext` 주입을 잃는다(S2 1388-1389행) `[추론]`.

### 5.5 `add_fan_out_edges`/`add_fan_in_edges` 시그니처와 fan-in 메시지 형태, 분기 실패

- 시그니처: `add_fan_out_edges(self, source: Executor | SupportsAgentRun, targets: Sequence[Executor | SupportsAgentRun]) -> Self`, `add_fan_in_edges(self, sources: Sequence[Executor | SupportsAgentRun], target: Executor | SupportsAgentRun) -> Self` (S8 282-286행, 511-515행).
- 형태: fan-in 대상은 `list[T]` 하나를 받는다. `FanInEdgeRunner`는 대상이 `list`를 처리할 수 있는지 검사한 뒤 원천별 버퍼에 쌓고, 모든 원천이 하나 이상 보냈을 때 `[msg.data for edge in edges for msg in buffer[edge.source_id]]`를 전달한다(S9 467-490행). 대상 핸들러가 `list[MatchResult]`를 받지 않으면 메시지가 `DROPPED_TYPE_MISMATCH`로 버려진다(S9 477-483행).
- 분기 실패: `Executor.execute`가 `executor_failed` 이벤트를 넣고 예외를 다시 던진다(S15 `_executor.py` 309-324행). 배달 경로의 `gather_cancelling_siblings_on_error`가 같은 superstep의 다른 분기를 취소한다(S9 30-53행, S10 221-238행). 워크플로는 `failed`와 `status(FAILED)` 이벤트를 낸 뒤 예외를 호출자에게 다시 던진다(S11 679-708행).
- 실행 확인(분기 b가 `RuntimeError`, 분기 a는 0.05초 지연): 이벤트 순서는 `executor_invoked a/b/c` → `intermediate b` → `executor_failed b` → `intermediate c` → `executor_completed c` → `failed` → `status`였고, a는 완료 이벤트 없이 취소되었으며, 소비 루프에서 `RuntimeError: boom b`가 발생했다. fan-in 대상은 호출되지 않았다.
- 동행노트 처리: 각 매칭 실행기는 `try/except`와 `asyncio.timeout`으로 감싸고, 실패 시 `MatchResult(domain=..., status="failed", error=...)`를 `send_message`한다. 이렇게 해야 fan-in이 세 결과를 모두 받아 Verifier가 실패 분야를 표시한다.

### 5.6 Copilot 권한 hook 대신 워크플로 HITL(`request_info`)

- 가능하며, 승인 흐름을 워크플로 단계로 올릴 수 있다.
- API: 실행기에서 `await ctx.request_info(ApprovalRequest(...), bool)`; `@response_handler`에서 승인 결과를 받는다; API는 `type == "request_info"` 이벤트를 SSE `approval_required`로 보내고, `POST /approval`에서 `workflow.run(responses={request_id: approved}, stream=True)`로 재개한다(S12 404-435행, S11 801-856행, S22). 실행 확인(3.3.1).
- 차이:

| 항목 | Copilot 권한 hook(TRD 3.5) | 워크플로 `request_info` |
|---|---|---|
| 대기 위치 | SDK 도구 호출 안의 콜백(`asyncio.Future`) | 워크플로 실행 종료(`IDLE_WITH_PENDING_REQUESTS`) 후 외부 응답 |
| 모델 턴 | 도구 호출 중 열린 채 대기 | 모델 턴이 끝난 뒤 대기 |
| 체크포인트 | 불가 | superstep 체크포인트로 저장·재개 가능 |
| 확정 실행 주체 | 모델이 `finalize_referral`을 호출해야 함 | 승인 뒤 결정적 코드가 확정(모델 비의존) |
| 평가 축 노출 | Copilot SDK 권한 모델 활용 | MAF 워크플로 HITL 활용 |

- 두 방식을 함께 쓸 수 있다. 문서 확정은 `request_info`로 받고, Copilot 권한 처리기는 허용 목록 외 도구 거부 정책만 맡는 구성이 가장 단순하다.

### 5.7 실행기 안 에이전트 토큰을 워크플로 이벤트 스트림으로 보내기

- 공식 경로: 실행기 컨텍스트를 `WorkflowContext[MatchResult, AgentResponseUpdate]`로 선언하고, 에이전트 스트림의 각 `AgentResponseUpdate`를 `await ctx.yield_output(update)`로 낸다. 빌더에서 `WorkflowBuilder(..., output_from=[documenter], intermediate_output_from=[profiler, match_living, ...])`처럼 지정하면 토큰은 `type="intermediate"`, 최종 결과는 `type="output"`으로 구분된다(S12 351-381행, S8 118-143행). 내장 `AgentExecutor`도 스트리밍 모드에서 같은 방식(`ctx.yield_output(update)`)을 쓴다(S14 871-937행).
- 이벤트는 superstep 종료를 기다리지 않고 바로 스트림에 나온다(S10 128-146행, 실행 확인). 병렬 분기의 토큰이 섞여 나오므로 SSE에는 `event.executor_id`를 붙인다.
- 보조 경로: `ctx.add_event(WorkflowEvent("token", data=...))`도 실행 시 전달되지만(실행 확인) 타입 검사 경고가 나고 `as_agent()` 경계에서는 전달되지 않는다(S13 158-168행). 실행별 `asyncio.Queue`로 따로 보내는 방식은 워크플로 추적과 분리된다.
- 예시:

```python
@handler
async def run(self, msg: ProfileMessage, ctx: WorkflowContext[MatchResult, AgentResponseUpdate]) -> None:
    try:
        async with asyncio.timeout(45):
            stream = self._agent.run(prompt(msg), stream=True, session=msg.sessions[self.id],
                                     function_invocation_kwargs={"run_id": msg.run_id})
            async for update in stream:
                await ctx.yield_output(update)        # SSE token / tool_call
            response = await stream.get_final_response()
        await ctx.send_message(collect_match(msg.run_id, self.id))
    except Exception as exc:
        await ctx.send_message(MatchResult.failed(self.id, str(exc)))
```

## 6. “깊이 있게” 쓸 만한 기능 후보

평가 기준: 모델 연결 / 에이전트 설계 / 오케스트레이션 / 도구 호출 / 컨텍스트 처리 / 스트리밍. 비용 S(반나절 이하) / M(하루) / L(이틀 이상).

| 기능 | 평가 축 | 동행노트 적용 | 비용 | 위험 | 근거 |
|---|---|---|---|---|---|
| 공유 `CopilotClient` + 에이전트별 `GitHubCopilotOptions`(`model`, `system_message` replace, `timeout`) | 모델 연결 | 5개 에이전트가 CLI 하나를 공유하고 역할별 시스템 메시지를 교체 | S | 낮음 | S2 698-817행 |
| `function_invocation_kwargs` + `FunctionInvocationContext` | 도구 호출, 컨텍스트 처리 | `check_eligibility`가 모델 인자 없이 실행 상태 프로필로 판정(인젝션 방어 근거) | S | 낮음(실행 확인) | 5.2 |
| 권한 처리기 허용 목록(`custom-tool` 승인, 그 외 거부) | 도구 호출 | 내장 셸·파일·URL·MCP 차단을 실제 코드로 증명, 거부 로그를 trace에 남김 | S | 중간: `ask` 요청 종류 `[미확인]` | 4절 6, 5.3 |
| `@tool(approval_mode="always_require")` + 기본 `on_pre_tool_use` | 도구 호출 | `finalize_referral` 승인 게이트 | S | 중간: 콜백 대기 중 SDK 턴이 열린 채 유지 | 5.3 |
| 워크플로 `request_info` + `@response_handler` | 오케스트레이션 | 의뢰서 확정 승인을 워크플로 단계로 표현, 승인 후 결정적 코드로 확정 | M | 낮음(실행 확인) | 5.6 |
| fan-out/fan-in + 분기별 실패 결과 메시지 | 오케스트레이션 | 매칭 3분야 병렬, 실패 분야도 Verifier에 도달 | S | 낮음 | 5.5 |
| `yield_output` + `intermediate_output_from`/`output_from` | 스트리밍 | 토큰·도구 호출·최종 결과를 이벤트 유형으로 구분해 SSE로 변환 | S | 낮음 | 5.7 |
| 스트리밍 `function_call`/`function_result` 콘텐츠 | 스트리밍, 도구 호출 | 타임라인에 도구 이름·인자·결과 실시간 표시 | S | 낮음 | S2 1182-1220행 |
| `AgentSession` 재사용 + `to_dict()` | 컨텍스트 처리 | 후속 질문이 Documenter 세션을 이어 받음(F9), 세션 ID를 상태에 보관 | S | 중간: 컨테이너 재시작 시 CLI 세션 보존 `[추론]` | S6 1884-1925행 |
| `ContextProvider` | 컨텍스트 처리 | 검증된 판정 기록을 Documenter 프롬프트에 주입하는 공급자 | M | 중간: Copilot 경로에서 텍스트 결합(2.3) | S6 752-830행 |
| 에이전트 미들웨어 | 에이전트 설계 | 실행 ID·단계명 span 속성, 입력 길이 검사, 실행 시간 측정 | S | 낮음 | S5 1992-2106행 |
| 체크포인트(`InMemoryCheckpointStorage`) | 오케스트레이션 | 승인 대기 상태 저장·재개, “저장된 실행 재생” 근거 | M | 중간: Copilot 세션은 체크포인트 대상 아님 | S15 `_checkpoint.py` |
| `configure_azure_monitor` + `enable_instrumentation` | 관측(오케스트레이션·도구 호출 증빙) | `workflow.run` → `executor.process` → `invoke_agent` → `execute_tool` trace를 UI에 trace ID로 연결 | S | 낮음: `opentelemetry-sdk`·`azure-monitor-opentelemetry` 설치 필요 | S17, S18 |
| `switch-case` 간선 | 오케스트레이션 | Profiler 결과 `missing_fields`가 많으면 추가 질문 단계로 분기 | S | 낮음 | S8 338-423행 |
| `ConcurrentBuilder`/`SequentialBuilder` | 오케스트레이션 | 매칭 단계를 내장 패턴으로 대체 | M | 중간: 메시지가 `AgentResponse` 형태로 바뀌어 타입 고정 메시지 설계와 충돌 | S16 |
| `HandoffBuilder` | 에이전트 설계 | — | — | 사용 불가(`Agent` 전용) | S16 `_handoff.py` 775행 |
| `response_format` | 에이전트 설계 | — | — | 사용 불가(#9809) | 5.4 |
| DevUI | 시연 | 개발 중 워크플로 그래프·실행 확인, 발표 녹화 | S | 낮음(beta) | S23 |

# GitHub Copilot SDK(Python) API 명세 — 동행노트 구현 기준

이 문서는 동행노트 구현과 TRD 검증에 쓰는 GitHub Copilot SDK Python API 명세다. 모든 내용은 아래 1차 출처를 직접 읽고 정리했다. 확인하지 못한 내용은 `[미확인]`으로 표시하고 확인한 범위를 적었다. 추론은 `[추론]`으로 표시한다.

출처 표기 규칙

- `SDK@v1.0.28`: https://github.com/github/copilot-sdk/tree/v1.0.28 (커밋 `fa108e71ee3025663e0dac20f2a071055d3a6b14`, 2026-10-28). PyPI 1.0.28 wheel을 임시 venv에 설치해 `python/copilot/` 소스와 비교했고, 차이는 `_cli_version.py`의 `CLI_VERSION = "1.0.105"` 한 줄뿐이었다(태그 소스는 `None`, wheel에 런타임 버전이 주입됨).
- `SDK@main`: https://github.com/github/copilot-sdk/tree/main (커밋 `c072001600018fe166910cfcb6eb42e769b9209d`, 태그 `v1.0.29-preview.8`, 2026-11-04). 1.0.28과 다른 점만 따로 적는다.
- 파일 경로 뒤 `:N`은 해당 태그 기준 줄 번호다. 예: `python/copilot/tools.py:62` → https://github.com/github/copilot-sdk/blob/v1.0.28/python/copilot/tools.py#L62
- `MAF-GHCP@2.1.1`: PyPI `agent-framework-github-copilot` 2.1.1 wheel의 `agent_framework_github_copilot/_agent.py`. Copilot SDK와 맞물리는 부분만 인용한다. MAF 전체 명세는 별도 문서 범위다.

---

## 1. 패키지·버전·설치

### 1.1 버전(2026-11-05 기준, PyPI JSON API 확인)

| 패키지 | 최신 안정판 | 업로드 시각(UTC) | 비고 |
|---|---|---|---|
| `github-copilot-sdk` | 1.0.28 | 2026-10-28 00:55 | `requires_python >=3.11`, 의존성 `python-dateutil>=2.9.0.post0`, `pydantic>=2.11`, `httpx>=0.24.0`, extra `telemetry` → `opentelemetry-api>=1.0.0`. 사전판 1.0.29rc8(2026-11-04)까지 있음 |
| (wheel 내장 런타임) | Copilot CLI runtime 1.0.105 | — | `copilot/_cli_version.py`의 `CLI_VERSION` |
| `agent-framework-github-copilot` | 2.1.1 | — | 의존성 `github-copilot-sdk<2.0,>=1.0.16`, `agent-framework-core<2,>=1.22.0` |

출처: https://pypi.org/pypi/github-copilot-sdk/json , https://pypi.org/pypi/agent-framework-github-copilot/json , wheel 내부 `copilot/_cli_version.py:18`.

TRD 1절의 "`github-copilot-sdk` 1.0.x"는 맞다. `requirements.txt`에는 `github-copilot-sdk==1.0.28`처럼 정확히 고정한다. 1.0.x 안에서도 생성 코드(`generated/rpc.py`, `generated/session_events.py`)가 크게 바뀐다(v1.0.28→main 사이 62개 파일, 11,351줄 추가).

### 1.2 설치와 런타임 내려받기

```bash
pip install "github-copilot-sdk[telemetry]==1.0.28"
python -m copilot download-runtime          # 런타임(copilot-runtime + runtime.node) 사전 배치
python -m copilot download-runtime --in-process   # FFI 전송용 네이티브 라이브러리까지
```

- `python -m copilot`은 하위 명령이 필수다. 하위 명령 없이 실행하면 도움말을 출력하고 종료 코드 1로 끝난다. 하위 명령은 `download-runtime` 하나이고 옵션은 `--force`, `--version`, `--in-process`다. 출처: `python/copilot/__main__.py`, `python/copilot/_cli_download.py:496-565`.
- 내려받기는 GitHub Releases의 플랫폼 패키지를 받아 `SHA256SUMS.txt`로 검증한 뒤 캐시에 푼다. 출처: `python/README.md:23-36`(v1.0.28), `_cli_download.py:130-172`.
- 캐시 위치: Linux `$XDG_CACHE_HOME/github-copilot-sdk/cli/<version>/prebuilds/<platform>/`, 없으면 `~/.cache/...`. `COPILOT_CLI_EXTRACT_DIR`를 주면 버전별 디렉터리 전체를 대체한다. 출처: `_cli_download.py:60-88`.
- 플랫폼 식별: glibc Linux는 `linux-x64`/`linux-arm64`, musl(Alpine)은 `linuxmusl-x64`/`linuxmusl-arm64`. 출처: `_cli_version.py:27-52`.

| 환경 변수 | 동작 | 출처 |
|---|---|---|
| `COPILOT_CLI_PATH` | 내려받은 런타임 대신 이 실행 파일을 쓴다 | `client.py` `_resolve_runtime_entrypoint`, README "Environment variables" |
| `COPILOT_CLI_EXTRACT_DIR` | 런타임 캐시 디렉터리 대체 | `_cli_download.py:66-69` |
| `COPILOT_SKIP_CLI_DOWNLOAD` | `1`/`true`/`yes`면 자동 내려받기 금지. 캐시가 없으면 `RuntimeError("Copilot runtime bundle is not cached in ... and automatic downloads are disabled.")` | `_cli_download.py:125-127`, `:343-347` |
| `COPILOT_CLI_DOWNLOAD_BASE_URL` | Releases 기본 URL 대체 | README |
| `COPILOT_SDK_DEFAULT_CONNECTION=inprocess` | 기본 전송을 FFI로 | README "In-process (FFI) transport" |

주의: 런타임 경로 해석(`ensure_runtime_wrapper()` 호출)은 `start()`가 아니라 `CopilotClient.__init__`에서 일어난다. 따라서 `COPILOT_SKIP_CLI_DOWNLOAD=1`이고 캐시가 없으면 생성자에서 예외가 난다. 출처: `client.py:1664-1905`(생성자), 특히 `connection.path = self._resolve_runtime_entrypoint(...)`.

### 1.3 인증과 라이선스

| 방법 | 내용 | 출처 |
|---|---|---|
| 환경 변수 | 우선순위 `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` | `docs/auth/authenticate.md:390-400` |
| 전체 우선순위 | 명시 `github_token` → `GITHUB_COPILOT_API_TOKEN`+`COPILOT_API_URL` → 환경 변수 → 저장된 OAuth → `gh auth` | `docs/auth/authenticate.md:519-527` |
| 명시 토큰 | `CopilotClient(github_token=...)`. SDK가 자식 프로세스 환경에 `COPILOT_SDK_AUTH_TOKEN`으로 넣는다. `use_logged_in_user` 기본값은 `github_token`이 있으면 `False` | `client.py:1694-1730`, `:4873-4874` |
| `use_logged_in_user=False` | 런타임에 `--no-auto-login` 전달. 문서상 이 경우 `COPILOT_GITHUB_TOKEN` 같은 환경 변수 토큰도 무시되므로 명시 토큰이 필요 | `client.py:4840-4841`, `docs/auth/authenticate.md:531-533` |
| 세션별 토큰 | `create_session(github_token=...)` 또는 `github_token_provider=`(회전 토큰, `{"kind":"token","accessToken":..., "expiresIn":초}` 반환). 둘은 상호 배타 | `client.py:2442-2860`, README v1.0.28 `:525-544` |
| 지원 토큰 | `gho_`, `ghu_`, `github_pat_`(fine-grained). `ghp_`(classic) 미지원 | `docs/auth/authenticate.md:250-256` |
| Fine-grained PAT 권한 | 리소스 소유자를 **개인 계정**으로 두고 Account 권한 **Copilot Requests**를 추가해야 한다. 조직 소유 PAT에는 이 권한이 없다 | https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli ("Supported token types", "Authenticating with environment variables") |
| 구독 | 사용자 토큰 방식은 Copilot 구독 필요(Individual/Business/Enterprise). BYOK는 구독 불필요 | `docs/auth/authenticate.md:7-13`, `docs/integrations/microsoft-agent-framework.md:19-25` |
| 조직 GitHub App | 설치 토큰 + 조직 권한 **Copilot Requests**(Read-only). 토큰 수명 1시간 | `docs/auth/server-to-server-tokens.md:30-44` |

BYOK(`provider=`)는 2.4절 표에 정리했다.

---

## 2. 핵심 개념과 객체 수명주기

### 2.1 구조

- SDK는 Copilot CLI 런타임과 JSON-RPC로 통신하는 얇은 클라이언트다. 에이전트 루프(모델 호출, 도구 선택, 재시도, 압축)는 런타임이 수행하고 SDK는 이벤트 수신, 도구 처리기 실행, 권한·훅 콜백 응답을 맡는다. 출처: `python/README.md:3`, `docs/features/agent-loop.md`.
- 전송 방식: `RuntimeConnection.for_stdio(path=None, args=())`(기본, 자식 프로세스), `for_tcp(port=0, connection_token=None, ...)`, `for_uri(url, connection_token=None)`(외부 headless 서버), `for_inprocess()`(실험적 FFI). 출처: `client.py:614-723`.
- `CopilotClient` 1개 = 런타임 프로세스 1개. 세션 여러 개를 동시에 띄울 수 있다. 문서는 "A single CLI server can handle many concurrent sessions"라고만 적고 수치 한도는 제시하지 않는다. 출처: `docs/setup/scaling.md:363-367`.

### 2.2 수명주기

```text
CopilotClient(...)            # 런타임 경로 해석(필요 시 내려받기)
  └ await client.start()      # 런타임 spawn + server.connect. create_session이 미시작이면 자동 start
      └ session = await client.create_session(...)     # session.create
          ├ session.on(handler)                         # 이벤트 구독(동기 콜백)
          ├ await session.send(prompt)                  # messageId 반환, 비동기 처리
          ├ await session.send_and_wait(prompt, timeout=60.0)
          ├ await session.abort()                       # 진행 중 턴 중단, 세션 유지
          └ await session.disconnect()                  # 메모리 자원 해제, 디스크 상태 유지
      └ await client.resume_session(session_id, ...)   # 디스크 상태에서 재개
      └ await client.delete_session(session_id)        # 디스크까지 영구 삭제
  └ await client.stop()        # 세션 정리 후 런타임 종료(최대 10초 대기 후 terminate/kill)
  └ await client.force_stop()  # 정리 없이 종료
```

- 두 객체 모두 `async with`를 지원한다. 출처: `python/README.md:96-191`, `session.py:3982-4032`.
- `disconnect()`는 `session.detach`를 호출하고 디스크의 대화 이력은 남긴다. 기본 저장 위치는 `~/.copilot/session-state/{sessionId}/`이고 `base_directory=`로 `COPILOT_HOME`을 바꿀 수 있다. 출처: `session.py:3982-4016`, README "Infinite Sessions", `docs/setup/multi-tenancy.md:304-318`.
- `session_idle_timeout_seconds`(클라이언트 옵션)는 런타임에 `--session-idle-timeout`으로 전달된다. 기본은 비활성. 출처: `client.py:4843-4844`, `docs/setup/backend-services.md:536-543`.

### 2.3 클라이언트 모드: `"copilot-cli"`(기본) 대 `"empty"`

| 항목 | `mode="copilot-cli"` | `mode="empty"` |
|---|---|---|
| 내장 도구 | 런타임 기본 도구 전부 노출(셸, 파일 편집, 검색, 웹 가져오기 등) | `create_session`에 `available_tools` 필수. 없으면 `ValueError` |
| 저장소 | `~/.copilot` 기본 | `base_directory`, `session_fs`, `for_uri` 중 하나 필수 |
| system message | 그대로 | `environment_context` 섹션 자동 제거(cwd, OS 정보 비노출) |
| 기본값 | 런타임 기본 | 세션 텔레메트리, 메모리, 스킬, 파일 훅, 호스트 git 작업, 세션 스토어, 실험 모드 끔. 커스텀 지시문 건너뜀, 플러그인 없음, 내장 스킬 없음, 키체인 비활성(`COPILOT_DISABLE_KEYTAR=1`) |
| 문서 권고 | CLI 같은 코딩 에이전트용 | 공유 서버·다중 사용자 서버의 안전 기준선 |

출처: `python/copilot/_mode.py:1-371`, `client.py:4876-4881`, `docs/setup/multi-tenancy.md:31-35`, `:409-426`.

`BUILTIN_TOOLS_ISOLATED`(세션 경계 밖에 접근하지 않는 내장 도구): `ask_user`, `task_complete`, `exit_plan_mode`, `task`, `read_agent`, `write_agent`, `list_agents`, `send_inbox`, `context_board`, `skill`. 출처: `_mode.py:88-107`.

### 2.4 `create_session` 주요 매개변수(키워드 전용, v1.0.28)

전체 시그니처는 `client.py:2442-2550`이다. 동행노트와 관련 있는 것만 정리한다.

| 매개변수 | 타입 | 의미 |
|---|---|---|
| `on_permission_request` | `(PermissionRequest, PermissionInvocation) -> PermissionRequestResult`(동기·비동기) | 도구 실행 전 권한 판단. 생략하면 요청이 이벤트로만 나가고 보류된다 |
| `model` | `str` | 모델 ID. BYOK에서는 필수 |
| `session_id` | `str` | 지정 ID. 생략 시 UUID |
| `reasoning_effort` | `Literal["low","medium","high","xhigh","max"]` | 지원 모델만. `list_models()`로 확인 |
| `reasoning_summary` | `Literal["none","concise","detailed"]` | 추론 요약 |
| `tools` | `list[Tool]` | 커스텀 도구 |
| `system_message` | `{"mode":"append"|"replace"|"customize", "content":..., "sections":{...}}` | 3.6절 |
| `available_tools` / `excluded_tools` | `list[str] | ToolSet` | 도구 허용·차단 목록. 3.4절 |
| `streaming` | `bool` | `assistant.message_delta` 등 delta 이벤트 활성화 |
| `hooks` | `SessionHooks` | 3.8절 |
| `on_user_input_request` | `(UserInputRequest, dict) -> UserInputResponse` | `ask_user` 도구 활성화 |
| `on_elicitation_request` | `(ElicitationContext) -> ElicitationResult` | 구조화 폼 입력 |
| `on_auto_mode_switch_request` | `(AutoModeSwitchRequest, dict) -> "yes"|"yes_always"|"no"` | 속도 제한 뒤 auto 모델 전환 승인 |
| `mcp_servers` | `dict[str, MCPStdioServerConfig | MCPHTTPServerConfig]` | MCP 서버 |
| `custom_agents`, `agent`, `default_agent` | `list[CustomAgentConfig]`, `str`, `{"excluded_tools": [...]}` | 하위 에이전트 |
| `infinite_sessions` | `{"enabled": bool, "background_compaction_threshold": 0.80, "buffer_exhaustion_threshold": 0.95}` | 자동 압축. 기본 켜짐 |
| `working_directory` | `str` | 세션 작업 디렉터리 |
| `provider` | `ProviderConfig` | BYOK. `type`(`openai`/`azure`/`anthropic`), `base_url`, `api_key`, `bearer_token`, `bearer_token_provider`(콜백, Azure Managed Identity용), `wire_api`, `azure.api_version`, `wire_model`, `max_prompt_tokens`, `max_output_tokens` 등 |
| `github_token`, `github_token_provider` | | 세션별 인증 |
| `enable_session_telemetry` | `bool` | 런타임 내부 세션 텔레메트리. OpenTelemetry 설정과 별개 |
| `on_event` | `Callable[[SessionEvent], None]` | 생성 직후부터 이벤트 수신 |
| `commands` | `list[CommandDefinition]` | TUI 슬래시 명령(웹앱에는 무관) |

출처: `client.py:2442-2860`, `session.py:1389-1512`(훅·MCP·에이전트·무한 세션 타입), `session.py:1700-1750`(`ProviderConfig`), `python/README.md:509-546`, `:992-1061`.

---

## 3. 기능 카탈로그

### 3.1 클라이언트·세션·모델

| 기능 | API | 동작 | 최소 예시 | 출처 |
|---|---|---|---|---|
| 클라이언트 생성 | `CopilotClient(*, connection=None, working_directory=None, log_level="info", env=None, github_token=None, base_directory=None, use_logged_in_user=None, telemetry=None, session_idle_timeout_seconds=None, client_info=None, on_list_models=None, mode="copilot-cli", ...)` | 런타임 연결 설정. `env`를 주면 `os.environ`을 상속하지 않는다 | `client = CopilotClient(mode="empty", base_directory="/tmp/copilot")` | `client.py:1664-1690`, `:4863-4871` |
| 시작·중지 | `await client.start()`, `await client.stop()`, `await client.force_stop()` | stop은 graceful(최대 10초) | `async with CopilotClient() as client: ...` | `client.py:2048`, `:2179`, `:2341`, README `:183-191` |
| 상태 확인 | `await client.ping(msg)`, `await client.get_status()`, `await client.get_auth_status()` | readiness 확인에 사용 | `await client.get_auth_status()` → `isAuthenticated` | `client.py:4181-4244` |
| 모델 목록 | `await client.list_models() -> list[ModelInfo]` | 첫 성공 결과를 캐시. `ModelInfo.id/name/capabilities.supports.vision/reasoning_effort/limits/policy/billing.multiplier/supported_reasoning_efforts/default_reasoning_effort` | `[m.id for m in await client.list_models()]` | `client.py:1227-1240`, `:4245-4293` |
| 세션 생성 | `await client.create_session(**kw) -> CopilotSession` | 2.4절 | 아래 3.2 예시 | `client.py:2442` |
| 세션 재개 | `await client.resume_session(session_id, *, on_permission_request=..., tools=..., ...)` | 디스크 상태 재개. 도구·훅·skill_provider 등 콜백은 다시 넘긴다 | `s = await client.resume_session(sid, tools=[...])` | `client.py:3384`, README `:1268-1287` |
| 세션 목록·삭제 | `list_sessions(filter=None)`, `get_session_metadata(id)`, `delete_session(id)`, `get_last_session_id()` | 삭제는 디스크까지 제거 | `await client.delete_session(sid)` | `client.py:4295-4419` |
| 수명 이벤트 | `client.on_lifecycle(handler)` / `on_lifecycle("session.created", handler)` | `session.created/deleted/updated/foreground/background` | | README `:548-580` |
| 모델 전환 | `await session.set_model(model, *, reasoning_effort=None, reasoning_summary=None, context_tier=None, ...)` | 다음 메시지부터 적용, 이력 유지 | `await session.set_model("claude-sonnet-4.6", reasoning_effort="high")` | `session.py:4056-4123` |
| 이력 | `await session.get_events() -> list[SessionEvent]` | 세션 전체 이벤트 | | `session.py:3956` |

### 3.2 메시지 전송·스트리밍·중단·제한 시간

| 기능 | API | 동작 | 최소 예시 | 출처 |
|---|---|---|---|---|
| 비동기 전송 | `await session.send(prompt, *, attachments=None, source=None, mode=None, agent_mode=None, request_headers=None, display_prompt=None, response_schema=None) -> str` | messageId를 바로 반환. 결과는 이벤트로 받는다 | `mid = await session.send("요약해 줘")` | `session.py:2105-2164` |
| 대기 전송 | `await session.send_and_wait(prompt, ..., response_schema=None, timeout=60.0) -> SessionEvent | None` | 해당 메시지 완료(비-autopilot idle)까지 대기. 시간 초과 시 `TimeoutError`. **시간 초과는 대기만 멈추고 에이전트 작업은 계속된다** | `ev = await session.send_and_wait(p, timeout=45)` | `session.py:2277-2353` |
| 구조화 출력(실험) | `await session.send_and_wait_typed(prompt, ResponseModel, *, timeout=60.0) -> ResponseModel` / `send(..., response_schema=Model 또는 dict)` | `responseFormat={"type":"json_schema","jsonSchema":{"name":"response","strict":True,"schema":...}}`를 해당 실행 1회에 적용. 도구 호출 포함. 스트리밍은 텍스트 그대로. 지원하지 않는 모델·스키마는 오류 | 3.7절 | `session.py:2166-2203`, `:2603-2646`, README `:797-845`, `python/e2e/test_structured_output_e2e.py` |
| 중단 | `await session.abort()` | 진행 중 메시지 중단. 세션은 계속 사용 가능. `abort` 이벤트와 `session.idle(aborted=True)` 발생 | `await session.abort()` | `session.py:4034-4054`, `docs/features/streaming-events.md:606-612`, `:869-875` |
| 조향·대기열 | `send(..., mode="immediate")`(진행 중 턴에 주입) / `mode="enqueue"`(기본, 순차) | 즉시 조향에는 스키마 불가 | | `docs/features/steering-and-queueing.md` |
| 이벤트 구독 | `session.on(handler) -> unsubscribe` | `handler: Callable[[SessionEvent], None]`(동기). `event.type`, `event.data`(타입별 dataclass), `event.agent_id`(하위 에이전트면 값 있음), `event.ephemeral` | `unsub = session.on(lambda e: q.put_nowait(e))` | `session.py:2747-2784`, `docs/features/streaming-events.md:50-62` |
| 첨부·이미지 | `attachments=[{"type":"file","path":...}]`, `{"type":"blob","data":base64,"mimeType":"image/png"}`, `directory`, `selection` | 이미지 입력. 모델 vision 지원 여부는 `ModelInfo.capabilities.supports.vision` | README 예시 | `session.py:312-368`, README `:762-795` |

스트리밍 이벤트 표(키는 wire 이름, Python dataclass 필드는 snake_case. 예: `deltaContent` → `data.delta_content`)

| 이벤트 | 임시 | 주요 필드 | 동행노트 용도 |
|---|---|---|---|
| `assistant.turn_start` / `assistant.turn_end` | | `turnId` | 단계 진행 |
| `assistant.intent` | 예 | `intent` | "제도 조회 중" 같은 진행 문구 |
| `assistant.reasoning_delta` / `assistant.reasoning` | 예/아니오 | `reasoningId`, `deltaContent` / `content` | 추론 노출 여부 결정 필요 |
| `assistant.message_delta` | 예 | `messageId`, `deltaContent` | SSE `token` |
| `assistant.message` | | `messageId`, `content`, `toolRequests[]`(`toolCallId`,`name`,`arguments`), `outputTokens`, `phase` | 최종 텍스트 |
| `assistant.usage` | 예 | `model`, `inputTokens`, `outputTokens`, `reasoningTokens`, `cacheReadTokens`, `finishReason`, `cost`, `duration`, `timeToFirstTokenMs`, `apiEndpoint`, `quotaSnapshots` | 비용·지연 지표 |
| `assistant.turn_retry` | | `turnId`, `model`, `reason` | 재시도 표시 |
| `tool.execution_start` | | `toolCallId`, `toolName`, `arguments`, `mcpServerName` | SSE `tool_call` |
| `tool.execution_progress` / `tool.execution_partial_result` | 예 | `progressMessage` / `partialOutput` | |
| `tool.execution_complete` | | `toolCallId`, `success`, `result.content`, `error.message` | 도구 결과 표시 |
| `permission.requested` / `permission.completed` | | `requestId`, `permissionRequest`(kind별) / `result.kind` | 승인 UI |
| `user_input.requested` / `elicitation.requested` | 예 | `question`, `choices` / `message`, `requestedSchema` | |
| `subagent.started/completed/failed/selected` | | `agentName`, `durationMs`, `totalTokens`, `totalToolCalls` | 하위 에이전트 타임라인 |
| `session.idle` | 예 | `aborted`, `mode` | 턴 완료 |
| `session.error` | | `errorType`(`authentication`/`quota`/`rate_limit` 등), `message`, `statusCode`, `eligibleForAutoSwitch`, `providerCallId` | 429 처리 |
| `session.compaction_start/complete` | | `preCompactionTokens`, `postCompactionTokens`, `summaryContent` | |
| `session.usage_info` | 예 | `tokenLimit`, `currentTokens`, `messagesLength` | 맥락 사용률 |
| `session.shutdown` | | `totalPremiumRequests`, `totalApiDurationMs`, `modelMetrics` | 실행 요약 |
| `external_tool.requested/completed` | | `requestId`, `sessionId`, `toolCallId`, `toolName`, `arguments` | SDK가 내부적으로 도구 처리기 호출에 사용 |
| `auto_mode_switch.requested` | | `errorCode`, `retryAfterSeconds` | 속도 제한 뒤 전환 |
| `abort` | | `reason` | |

출처: `docs/features/streaming-events.md:396-1066`, 전체 이벤트 타입 열거는 `python/copilot/generated/session_events.py`의 `SessionEventType`, `SessionErrorData`(`:10282`), `AssistantTurnRetryData`(`:3689`), `AutoModeSwitchRequestedData`(`:4963`).

전형적 이벤트 순서: `assistant.turn_start → assistant.intent → assistant.message_delta* → assistant.message(toolRequests) → assistant.usage → permission.requested → permission.completed → tool.execution_start → tool.execution_complete → (반복) → assistant.turn_end → session.idle`. 출처: `docs/features/streaming-events.md:979-1004`.

### 3.3 커스텀 도구

| 기능 | API | 동작 | 최소 예시 | 출처 |
|---|---|---|---|---|
| Pydantic 데코레이터 | `@define_tool(name=None, *, description=None, overrides_built_in_tool=False, skip_permission=False, defer=None, metadata=None, is_terminal=False, namespace=None)` | 첫 매개변수 Pydantic 모델에서 JSON Schema 생성(`model_json_schema()`). 처리기 시그니처 4종: `()`, `(invocation: ToolInvocation)`, `(params)`, `(params, invocation)`. 동기·비동기 모두 가능 | 아래 | `tools.py:127-370` |
| 함수형 | `define_tool("name", description=..., handler=fn, params_type=Model)` | `name` 필수 | | `tools.py:176-188`, `:349-353` |
| 선언 전용 | `define_tool("name", description=..., params_type=Model)` 또는 `Tool(handler=None)` | 처리기 없이 노출. `external_tool.requested`를 관찰하고 보류 RPC로 응답 | | `tools.py:355-368`, README `:652-662` |
| 저수준 | `Tool(name, description, handler=None, parameters=None, overrides_built_in_tool=False, skip_permission=False, defer=None, metadata=None, is_terminal=False, namespace=None)` | `handler(invocation: ToolInvocation) -> ToolResult` | README `:611-650` | `tools.py:103-120` |
| 처리기 문맥 | `ToolInvocation(session_id, tool_call_id, tool_name, arguments, available_tools, agent_id, request_id)` | **앱 정의 kwargs는 없다.** `session_id`로 앱 상태를 찾아야 한다 | | `tools.py:61-88`, `session.py:3046-3054` |
| 반환값 | `None`→빈 성공, `str`→그대로, `ToolResult`→그대로, 그 밖(Pydantic, dict, date, Decimal, UUID, Enum, set)→JSON 직렬화 | | | `tools.py:381-429` |
| `ToolResult` | `text_result_for_llm`, `result_type`(`"success"|"failure"|"rejected"|"denied"|"timeout"`), `error`, `binary_results_for_llm`, `session_log`, `tool_telemetry`, `tool_references` | | `ToolResult(text_result_for_llm="...", result_type="failure", error="...")` | `tools.py:34-58` |
| 인자 검증 실패 | Pydantic `ValidationError` → `result_type="failure"`, 모델에 `"Invalid tool arguments:\n<loc>: <msg>"` 전달 | 모델이 스스로 고쳐 다시 호출할 수 있다 | | `tools.py:292-307` |
| 처리기 예외 | 모델에는 `"Invoking this tool produced an error. Detailed information is not available."`만 보내고 상세는 `error` 필드로 런타임에 전달 | 보안상 상세 비노출 | | `tools.py:319-332`, `session.py:3082-3101` |
| 권한 생략 | `skip_permission=True` | 해당 도구 호출 시 `on_permission_request`를 거치지 않는다 | `@define_tool(description="...", skip_permission=True)` | README `:723-731`, `python/e2e/test_tools_e2e.py` `test_skips_permission...`(`:219-243`) |
| 턴 종료 도구 | `is_terminal=True` | 성공 시 결과를 모델에 다시 넣지 않고 턴 종료. 실패·거부·시간 초과는 모델에 보여 재시도 가능 | | `tools.py:113-117`, `docs/features/context-management.md:42-57` |
| 지연 로드 | `defer="auto"|"never"` | tool search로 지연 노출할지 | | README `:733-741` |
| 내장 도구 대체 | `overrides_built_in_tool=True` | 같은 이름 내장 도구를 대체. 없으면 이름 충돌 오류 | | README `:685-697` |
| 실행 중 교체(실험) | `await session.set_tools(tools)` | 이 클라이언트의 커스텀 도구 전체 교체. 내장·MCP 불변 | | `session.py:2221-2275` |
| 취소 | 런타임 요청이 끝나거나 세션이 종료되면 Python 처리기 task가 취소된다 | | | `CHANGELOG.md:77`(v1.0.14) |
| 추적 문맥 | 처리기 호출을 `trace_context(traceparent, tracestate)`로 감싼다 | 처리기 안에서 만든 OTel span이 CLI span의 자식이 된다 | | `session.py:3056-3060`, `_telemetry.py:26-48` |

```python
from pydantic import BaseModel, Field
from copilot import define_tool
from copilot.tools import ToolInvocation

class EligibilityParams(BaseModel):
    scheme_id: str = Field(description="제도 ID")

@define_tool(description="실행 상태의 CaseProfile로 자격 규칙을 판정한다", skip_permission=True)
async def check_eligibility(params: EligibilityParams, invocation: ToolInvocation) -> dict:
    run = RUNS_BY_COPILOT_SESSION[invocation.session_id]   # 앱이 session_id → run 매핑을 관리
    return evaluate(run.profile, params.scheme_id).model_dump()
```

### 3.4 도구 허용·차단(`available_tools`, `excluded_tools`, `ToolSet`)

- `available_tools`: 허용 목록. 지정하면 **내장 도구, MCP 도구, `tools=`로 등록한 커스텀 도구를 합친 전체 카탈로그**에 적용된다. 커스텀 도구도 이름을 넣지 않으면 모델에게 숨겨진다. `excluded_tools`보다 우선한다. 출처: `client.py:2572-2577`.
- `excluded_tools`: 차단 목록. 커스텀 도구 포함 전체에 적용. docstring은 "`available_tools`가 있으면 무시"라고 적지만, empty 모드 e2e는 `available_tools=builtin:*` + `excluded_tools=["builtin:bash"]`로 차감이 동작함을 검증한다. 두 설명이 어긋나므로 차단 목록에 의존하지 말고 허용 목록을 정확히 쓴다. 출처: `client.py:2578-2580`, `python/e2e/test_mode_empty_e2e.py` `test_empty_mode_excluded_tools_subtracts_from_available_tools`.
- 항목 형식: 맨 이름(`"view"`) 또는 출처 한정(`"builtin:bash"`, `"custom:check_eligibility"`, `"mcp:<server>-<tool>"`, 와일드카드 `builtin:*`/`custom:*`/`mcp:*`). 맨 `"*"`는 `ValueError`. 이름 규칙 `^[a-zA-Z0-9_-]+$`. 문자열 하나를 그대로 넘기면 `TypeError`. 출처: `_mode.py:21-140`.
- copilot-cli 모드에서 `available_tools=["view"]`를 주면 모델 요청의 도구 목록이 `["view"]` 하나뿐임을 e2e가 확인한다. 출처: `python/e2e/test_session_config_e2e.py:670-688`.
- 셸 도구 이름은 Linux/macOS `bash`, Windows `powershell`. 그 밖에 e2e에 나오는 내장 도구 이름: `edit`, `grep`, `web_fetch`, `view`. 전체 내장 도구 목록은 SDK 저장소에 열거되어 있지 않다 `[미확인]`(런타임 소스 범위). 출처: `python/e2e/test_mode_empty_e2e.py:66-94`.
- `default_agent={"excluded_tools":[...]}`: 주 에이전트에게서만 숨기고 하위 에이전트에게는 허용. 출처: `docs/features/custom-agents.md:778-926`.

### 3.5 권한 처리(`on_permission_request`)

- 호출 시점: 도구 실행 전(파일 쓰기, 셸, URL, MCP, 커스텀 도구 등). 처리기 시그니처 `(request: PermissionRequest, invocation: PermissionInvocation)`, 동기·비동기 모두 가능. `invocation`은 `{"session_id": str, "managed_settings_enabled": bool, "prompt_request"?: ...}`. 출처: `session.py:553-567`, `:3152-3217`, README `:1177-1266`.
- 생략 시: 요청이 `permission.requested` 이벤트로만 나가고 보류된다(SDK 자체는 거부하지 않는다). 출처: `client.py` docstring `on_permission_request`, README `:1179`.
- 처리기 예외 또는 응답 전송 실패: SDK가 `PermissionDecisionUserNotAvailable()`(거부)로 응답한다. 출처: `session.py:3204-3217`.
- `resolved_by_hook=True`인 요청은 처리기를 부르지 않는다. 출처: `session.py:2889-2891`.

요청 종류(`PermissionRequest` 판별 합집합, `request.kind`)

| kind | 클래스 | 주요 필드 |
|---|---|---|
| `shell` | `PermissionRequestShell` | `full_command_text`, `intention`, `commands`, `possible_paths`, `possible_urls`, `has_write_file_redirection`, `tool_call_id` |
| `write` | `PermissionRequestWrite` | `file_name`, `diff`, `intention`, `new_file_contents`, `file_edits` |
| `read` | `PermissionRequestRead` | `path`, `intention` |
| `mcp` | `PermissionRequestMcp` | `server_name`, `tool_name`, `tool_title`, `args`, `read_only` |
| `url` | `PermissionRequestUrl` | `url`, `intention`, `redirected_from` |
| `memory` | `PermissionRequestMemory` | `subject`, `fact`, `citations` |
| `custom-tool` | `PermissionRequestCustomTool` | `tool_name`, `tool_description`, `args`, `tool_call_id`, `skip_permission` |
| `hook` | `PermissionRequestHook` | `tool_name`, `hook_message`, `tool_args`, `tool_call_id` ("Hook confirmation permission request") |
| `workflow`, `extension-management`, `extension-permission-access`, `extension-env-access` | | 확장·워크플로용 |

출처: `python/copilot/generated/session_events.py:8340`(custom-tool), `:8491`(hook), `:8532`(mcp), `:8663`(read), `:8720`(shell), `:8883`(url), `:9024`(write), `:15160`(합집합), `docs/features/streaming-events.md:723-757`.

응답 값(`PermissionRequestResult = PermissionDecision | PermissionNoResult`, `copilot.rpc`에서 import)

| 값 | 의미 |
|---|---|
| `PermissionDecisionApproveOnce()` | 이번 한 번 허용 |
| `PermissionDecisionReject(feedback="...")` | 거부. `feedback`은 모델에 전달 |
| `PermissionDecisionUserNotAvailable()` | 확인할 사람이 없어 거부 |
| `PermissionDecisionApproveForSession(...)`, `PermissionDecisionApproveForLocation(...)`, `PermissionDecisionApprovePermanently(...)` | 장기 승인 |
| `PermissionNoResult()` | 이 클라이언트는 응답하지 않음(다른 클라이언트에 위임) |

출처: README `:1246-1266`, `session.py:493-512`, `generated/rpc.py:12451-12571`.

`PermissionHandler.approve_all`은 `managed_approval_required=True`면 `PermissionNoResult`, 그 밖은 `ApproveOnce`를 돌려준다. `enable_managed_settings`와 함께 쓰면 오류. 출처: `session.py:569-578`.

```python
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
from copilot.session_events import PermissionRequestCustomTool, PermissionRequestHook

async def on_permission(request, invocation):
    match request:
        case PermissionRequestCustomTool(tool_name="finalize_referral") | PermissionRequestHook(tool_name="finalize_referral"):
            ok = await approvals.wait(invocation["session_id"], request, timeout=120)
            return PermissionDecisionApproveOnce() if ok else PermissionDecisionReject(feedback="담당자가 거부함")
        case PermissionRequestCustomTool(tool_name=name) if name in APP_TOOLS:
            return PermissionDecisionApproveOnce()
        case _:
            return PermissionDecisionReject(feedback="이 앱에서는 허용하지 않는 동작")
```

### 3.6 시스템 메시지·맥락 처리

| 기능 | API | 동작 | 출처 |
|---|---|---|---|
| 덧붙이기 | `system_message={"mode":"append","content":"..."}` | 런타임 기본 프롬프트 뒤에 추가 | README `:1063-1082` |
| 섹션 편집 | `{"mode":"customize","sections":{"tone":{"action":"replace","content":...},"code_change_rules":{"action":"remove"}},"content":...}` | 섹션 ID: `preamble`, `identity`, `tone`, `tool_efficiency`, `environment_context`, `code_change_rules`, `guidelines`, `safety`, `tool_instructions`, `custom_instructions`, `runtime_instructions`, `last_instructions`. 동작 `replace/remove/append/prepend/preserve` 또는 변환 콜백 `(str)->str` | README `:1084-1132` |
| 전체 교체 | `{"mode":"replace","content":...}` | SDK 안전 지침까지 제거 | README `:1134-1148` |
| 무한 세션 | `infinite_sessions={...}` | 기본 켜짐. 80%에서 백그라운드 압축, 95%에서 압축 완료까지 차단. `session.workspace_path` | README `:936-974`, `session.py:1493-1512` |
| 맥락 비우기 | `await session.rpc.history.clear_context(...)` | 도구 처리기 안에서만 호출 가능. `is_terminal=True` 도구와 함께 사용 | `docs/features/context-management.md` |
| 메시지 출처 | `send(..., source="system")` 또는 `AgentMessageSource("reviewer")` | 앱 내부 맥락을 사용자 메시지와 구분 | README `:154-181` |
| 메모리 | `memory={"enabled": True}` | 세션 간 기억. empty 모드 기본 끔 | README `:976-990` |

### 3.7 구조화 출력(실험)

```python
from pydantic import BaseModel, ConfigDict

class CaseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: int | None
    household_size: int | None

profile = await session.send_and_wait_typed("<case_note>...</case_note>를 구조화하라", CaseProfile, timeout=45)
```

- 실행 1회 단위로 적용되고, 도구 호출·조향 포함 그 실행의 최종 메시지에 적용된다. 다음 독립 send나 하위 에이전트에는 상속되지 않는다.
- 공급자 스키마 제한이 그대로 적용된다(OpenAI strict는 닫힌 객체와 required 필드 필요). 스키마를 고쳐 쓰지 않으며, 지원하지 않는 모델·스키마는 오류를 낸다.
- 검증은 `model_validate_json(by_alias=True, by_name=False)`.

출처: README `:797-845`, `session.py:2186-2194`, `:2603-2646`, `python/e2e/test_structured_output_e2e.py`.

### 3.8 훅(`hooks=SessionHooks`)

모든 훅 처리기는 `(input: TypedDict, invocation: dict[str, str])`를 받고 동기·비동기 모두 가능하며 `None`을 돌려주면 기본 동작이다. 입력에는 공통으로 `sessionId`, `timestamp`(datetime), `workingDirectory`, 선택 `agentId`/`agentType`/`parentAgentId`가 있다.

| 키 | 입력 주요 필드 | 출력 | 출처 |
|---|---|---|---|
| `on_pre_tool_use` | `toolName`, `toolArgs` | `permissionDecision: "allow"|"deny"|"ask"`, `permissionDecisionReason`, `modifiedArgs`, `additionalContext`, `suppressOutput` | `session.py:1018-1045`, `docs/hooks/pre-tool-use.md:127-155` |
| `on_pre_mcp_tool_call` | MCP 도구 호출 정보 | `metaToUse` 등 | `session.py:1048-1080` |
| `on_post_tool_use` | `toolName`, `toolArgs`, 결과 | `modifiedResult`, `additionalContext`, `suppressOutput` | `session.py:1083-1109` |
| `on_post_tool_use_failure` | `toolName`, `error` | `additionalContext`(재시도 안내) | `session.py:1112-1145` |
| `on_user_prompt_submitted` | `prompt` | `modifiedPrompt`, `additionalContext`, 또는 `{"decision":"block","reason":...}`(모델 턴 없음, `session.warning` 발생) | `session.py:1148-1179`, README `:1426` |
| `on_user_prompt_transformed` | 변환된 프롬프트 | `modifiedTransformedPrompt` | `session.py:1182-1205` |
| `on_session_start` | `source`(`startup`/`resume`/`new`) | `additionalContext` | `session.py:1208-1232` |
| `on_session_end` | `reason` | `suppressOutput` 등 | `session.py:1235-1261` |
| `on_error_occurred` | `error`, `errorContext`(`model_call`/`tool_execution`/`system`/`user_input`), `recoverable` | `errorHandling: "retry"|"skip"|"abort"`, `retryCount`, `userNotification`, `suppressOutput` | `session.py:1264-1291` |
| `on_agent_stop` | 턴 종료 정보 | `{"decision":"block","reason":...}`로 계속 진행 요구 | `session.py:1294-1319` |
| `on_subagent_start` / `on_subagent_stop` | `agentName`, `stopReason`, `response` | `additionalContext` / `modifiedResponse` 또는 block | `session.py:1322-1386`, README `:1429-1442` |

- `"ask"`의 동작은 문서상 "User is prompted to approve (interactive mode)"까지만 적혀 있다. SDK 환경에서 `"ask"`가 어떤 kind의 권한 요청(`hook` 또는 `custom-tool`)으로 `on_permission_request`에 도달하는지 명시한 문서·e2e는 찾지 못했다 `[미확인]`. `PermissionRequestHook`(kind `hook`, "Hook confirmation permission request")이 존재하므로 `hook`일 가능성이 높다 `[추론]`. 처리기는 두 kind를 모두 도구 이름으로 처리하는 편이 안전하다.
- `"allow"`가 이후 `custom-tool` 권한 요청까지 생략시키는지도 문서에 명시가 없다 `[미확인]`. 문서 예시는 항상 `on_pre_tool_use`와 승인하는 `on_permission_request`를 함께 둔다(`docs/features/hooks.md:318-366`).

### 3.9 사용자 입력·elicitation

| 기능 | API | 동작 | 출처 |
|---|---|---|---|
| `ask_user` | `on_user_input_request=async (request, invocation) -> {"answer": str, "wasFreeform": bool}` | 처리기를 주면 `ask_user` 도구가 활성화된다. `request["question"]`, `request.get("choices")`, `request.get("allowFreeform", True)` | README `:1293-1320`, `session.py:657-675` |
| elicitation | `on_elicitation_request=async (context) -> {"action":"accept"|"decline"|"cancel","content":{...}}` | MCP·서버의 구조화 폼 요청. 처리기 예외 시 자동 cancel | README `:1555-1592` |
| `ask_user_variant` | `"legacy"|"elicitation"` | `ask_user` 도구 형태 선택 | `client.py` docstring |

### 3.10 MCP·커스텀 에이전트·스킬

| 기능 | API | 동작 | 출처 |
|---|---|---|---|
| MCP 서버 | `mcp_servers={"name": {"type":"stdio","command":...,"args":[...],"tools":["*"]}}` 또는 `{"type":"http","url":...,"headers":{...},"tools":[...]}` | 도구 이름은 `<server>-<tool>`. 권한 kind `mcp` | `session.py:1411-1433`, README `:546` |
| 커스텀 에이전트 | `custom_agents=[{"name","prompt","description","tools","mcp_servers","infer","skills","model","reasoning_effort"}]`, `agent="name"` | 런타임이 의도에 맞춰 하위 에이전트로 위임. 격리된 맥락에서 실행, `subagent.*` 이벤트 | `session.py:1456-1478`, `docs/features/custom-agents.md:5-25`, `:246-270`, `:415-437` |
| 스킬 | `skill_directories=[...]`, `enable_skills=True`, `skill_provider=SkillProvider`(실험) | SKILL.md 또는 SDK 제공 스킬 | README `:269-338` |

### 3.11 텔레메트리(OpenTelemetry)

| 기능 | API | 동작 | 출처 |
|---|---|---|---|
| CLI 추적 내보내기 | `CopilotClient(telemetry={"otlp_endpoint":..., "otlp_protocol":"http/protobuf", "exporter_type":"otlp-http"|"file", "file_path":..., "source_name":..., "capture_content": False})` | SDK가 런타임 환경에 `COPILOT_OTEL_ENABLED=true`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` 등을 설정. 내보내기는 OTLP HTTP 또는 파일 | `client.py:553-571`, `:4888-4905`, `docs/observability/opentelemetry.md:102-113` |
| 추적 문맥 전파 | 자동(`opentelemetry-api` 설치 시) | `create_session`, `resume_session`, `send`에 현재 span의 `traceparent`를 실어 보내고, 도구 처리기 호출 시 CLI span 문맥을 복원 | `_telemetry.py:9-48`, `session.py:2202`, `docs/observability/opentelemetry.md:162-197` |
| 토큰·비용 | `assistant.usage` 이벤트, `session.rpc.usage.get_metrics()`(실험), `models.list`의 `billing.multiplier` | | `docs/features/usage-and-billing.md:8-25` |
| GitHub 측 텔레메트리 차단 | 런타임 환경 `COPILOT_GITHUB_TELEMETRY_DISABLED="true"` | 사용자 설정 OTel 내보내기와 별개 | README `:385-396` |

### 3.12 headless 서버·Docker

- 기본 구성(자식 프로세스 stdio)은 앱 컨테이너 안에서 SDK가 런타임을 직접 띄운다. 별도 서버는 필요 없다. 출처: `docs/setup/bundled-cli.md`.
- 분리 구성: `copilot --headless --host 0.0.0.0 --port 4321`로 CLI 서버를 띄우고 `RuntimeConnection.for_uri("host:4321", connection_token=...)`로 연결. SDK-CLI 사이에는 내장 인증이 없으므로 네트워크 경로를 보호해야 한다. 공식 Docker 이미지는 없고 GitHub Releases에서 받아 직접 만든다. 출처: `docs/setup/backend-services.md:59-120`, `:536-543`.
- 세션 상태는 로컬 디스크 파일이다. 재시작 후 유지가 필요하면 `~/.copilot/session-state/`(또는 `COPILOT_HOME`)에 영구 볼륨을 붙인다. Azure Container Instances 예시는 Azure Files를 마운트한다. 출처: `docs/setup/scaling.md:576-592`, `:612-630`.
- Azure Container Apps 전용 안내는 저장소에 없다 `[미확인]`(docs 전체에서 "Container Apps" 검색 결과 0건).

---

## 4. 주의점·제약

1. **문서 버전 차이**: main(1.0.29 사전판) README와 1.0.28 README가 다르다. 예: 텔레메트리 차단 변수가 1.0.28은 `COPILOT_GITHUB_TELEMETRY_DISABLED`, main은 `COPILOT_TELEMETRY_DISABLED`. `entra=` 관련 `copilot/entra.py`는 main에만 있다. 구현 시 1.0.28 태그 기준 문서를 본다.
2. **MAF 통합 문서 오기**: `docs/integrations/microsoft-agent-framework.md:44-46`은 `pip install copilot-sdk agent-framework-github-copilot`라고 적었지만 PyPI 패키지 이름은 `github-copilot-sdk`다.
3. **`send_and_wait` 시간 초과는 작업을 멈추지 않는다.** 45초 제한을 지키려면 `TimeoutError`를 잡은 뒤 `await session.abort()`를 호출해야 한다. 출처: `session.py:2316-2317`.
4. **`session.on` 처리기는 동기 함수다.** 비동기 큐에 넣을 때는 `queue.put_nowait`나 `loop.call_soon_threadsafe`를 쓴다. 출처: `session.py:2747`, `:1817`.
5. **`env=`를 주면 환경을 상속하지 않는다.** `COPILOT_GITHUB_TOKEN`을 함께 넣지 않으면 인증이 빠진다. 출처: `client.py:4863-4871`.
6. **커스텀 도구도 기본적으로 권한 요청을 거친다.** `skip_permission=False`(기본)인 도구는 호출마다 `custom-tool` 권한 요청을 만든다. 모두 거부하는 처리기를 두면 앱 도구까지 막힌다. 출처: `python/e2e/test_tools_e2e.py:266-321`.
7. **copilot-cli 모드의 기본 노출 도구**: `available_tools`를 주지 않으면 셸·파일 편집·웹 가져오기 같은 내장 도구가 모델에게 보인다. 권한 거부로 실행은 막아도 모델이 호출을 시도하며 턴과 토큰을 소모한다 `[추론]`.
8. **속도 제한(429)**: 런타임이 재시도와 오류 분류를 맡는다. SDK에 노출되는 신호는 `session.error`(`errorType` 예 `"rate_limit"`, `"quota"`, `statusCode`, `eligibleForAutoSwitch`), `assistant.turn_retry`(`reason`), `auto_mode_switch.requested`(`retryAfterSeconds`, 처리기 `on_auto_mode_switch_request`), `on_error_occurred` 훅(`errorContext="model_call"`, `errorHandling="retry"|"skip"|"abort"`)이다. 런타임의 재시도 횟수·백오프 값은 SDK 저장소에 없다 `[미확인]`. 출처: `docs/features/streaming-events.md:614-624`, `generated/session_events.py:3689`, `:4963`, `:10282`, `session.py:701-714`, `:1264-1291`.
9. **RPC 기본 제한 시간**: 생성 RPC 메서드는 기본 30초이고 `timeout=`으로 바꿀 수 있다. 출처: `CHANGELOG.md:869`.
10. **구조화 출력은 실험 기능**이다. 모델별 지원 차이가 있고 스트리밍 delta는 JSON 텍스트 조각으로 나온다.
11. **OTel 내보내기 대상**: CLI 런타임은 OTLP HTTP 또는 파일로만 내보낸다. Application Insights로 보내려면 OTLP 수신 경로(예: OpenTelemetry Collector + Azure Monitor exporter)가 필요하다 `[추론]`. CLI span을 내보내지 않으면 앱 도구 span의 부모(CLI span)가 수집되지 않아 trace가 끊겨 보일 수 있다 `[추론]`.
12. **세션 저장은 파일 기반**이고 내장 세션 잠금이 없다. 같은 세션에 동시 send가 들어가면 기본 `enqueue`로 순차 처리된다. 출처: `docs/setup/scaling.md:622-630`, `docs/features/steering-and-queueing.md`.

---

## 5. 동행노트 설계(TRD) 검증

| # | TRD 가정(위치) | 판정 | 근거와 올바른 API |
|---|---|---|---|
| 1 | 앱 시작 시 `CopilotClient`를 한 번 만들어 모든 에이전트가 공유(2절) | 맞음 | 클라이언트 1개가 런타임 1개를 띄우고 여러 세션을 동시에 연다(2.1절). MAF에서는 `GitHubCopilotAgent(client=...)`로 공유하는지 MAF 문서로 확인한다 |
| 2 | Docker 빌드에서 `python -m copilot`으로 런타임을 받는다(2절) | 부분적으로 맞음 | 명령은 `python -m copilot download-runtime`이다. 하위 명령 없이 실행하면 종료 코드 1(`_cli_download.py:496-565`). 빌드 사용자와 실행 사용자의 HOME이 다르면 캐시를 못 찾으므로 빌드·실행 모두 `COPILOT_CLI_EXTRACT_DIR=/opt/copilot-runtime`처럼 고정 경로를 지정한다 |
| 3 | `COPILOT_SKIP_CLI_DOWNLOAD=1`로 실행 중 내려받기 방지(2절) | 맞음(주의 있음) | 값 `1`/`true`/`yes` 인정. 캐시가 없으면 `CopilotClient()` 생성자에서 `RuntimeError`(`_cli_download.py:343-347`). `/readyz`에서 이 예외를 오류로 노출한다 |
| 4 | 인증은 Key Vault의 `COPILOT_GITHUB_TOKEN`(6절) | 맞음(조건) | 환경 변수 최우선순위 토큰이다. Fine-grained PAT이면 개인 계정 소유 + Account 권한 **Copilot Requests** 필요. classic `ghp_` 불가. 토큰 주인에게 Copilot 구독 필요(1.3절). `github_token=`을 직접 넘기면 `use_logged_in_user`가 False가 되어 `--no-auto-login`이 붙는다 |
| 5 | 커스텀 도구 처리기가 `FunctionInvocationContext`의 `ctx.kwargs["run_id"]`로 실행 상태를 읽는다(3.3절) | SDK 수준에서는 틀림, MAF 수준에서는 맞음 | **Copilot SDK 처리기 문맥은 `ToolInvocation(session_id, tool_call_id, tool_name, arguments, available_tools, agent_id, request_id)`뿐이고 앱 정의 kwargs는 없다**(`tools.py:61-88`, `session.py:3046-3054`). 반면 MAF 2.1.1 `_tool_to_copilot_tool`은 SDK 처리기를 감싸 `FunctionInvocationContext(kwargs=function_invocation_kwargs, session=agent_session, ...)`를 만들어 넘긴다(`MAF-GHCP@2.1.1 _agent.py:1405-1471`). 따라서 `agent.run(..., function_invocation_kwargs={"run_id": ...})`로 넘기면 `ctx.kwargs["run_id"]`가 동작한다 `[추론: run 인자 이름은 MAF 명세로 확인]`. SDK를 직접 쓰는 경우에는 `invocation.session_id → run_id` 매핑을 앱이 관리한다 |
| 6 | `finalize_referral`은 `@tool(approval_mode="always_require")`이고 실행 전 hook이 `ask`를 돌려 `on_permission_request`가 호출된다(3.5절) | 부분적으로 맞음 | MAF 2.1.1은 사용자가 `on_pre_tool_use`를 주지 않으면 `always_require` 도구에 `{"permissionDecision":"ask"}`를 돌려주는 기본 훅을 설치한다(`_agent.py:1497-1583`). 그러나 (a) `"ask"`가 `on_permission_request`에 어떤 kind(`hook`/`custom-tool`)로 오는지 SDK 문서·e2e에 명시가 없다 `[미확인]`. 처리기는 두 kind를 모두 `tool_name=="finalize_referral"`로 판정해야 한다. (b) 앱이 `on_pre_tool_use`를 직접 주면 MAF 기본 훅이 꺼지고 승인 강제 책임이 앱으로 넘어간다(`_agent.py:587-592`) |
| 7 | 커스텀 도구가 사용자 승인을 요구하게 하는 방법 | 확인됨 | SDK 자체 경로: `skip_permission=False`(기본)인 커스텀 도구는 호출마다 **kind `"custom-tool"`**(`PermissionRequestCustomTool`: `tool_name`, `tool_description`, `args`, `tool_call_id`) 권한 요청을 만든다. 처리기가 `PermissionDecisionReject`를 돌려주면 도구 처리기는 호출되지 않는다(`python/e2e/test_tools_e2e.py:266-321`). 즉 hook 없이도 `on_permission_request` 하나로 승인 게이트를 만들 수 있다 |
| 8 | 권한 처리기는 내장 권한 요청을 모두 거부하고 앱 함수 도구만 실행된다(3.5절 5항, 8절) | 틀림(그대로 구현하면 앱 도구도 막힘) | MAF 2.1.1은 `FunctionTool`을 `CopilotTool(name, description, handler, parameters)`로 바꾸며 `skip_permission`을 설정하지 않는다(`_agent.py:1490-1495`). 그래서 **모든 앱 도구 호출이 `custom-tool` 권한 요청을 만든다.** 또 `on_permission_request`를 주지 않으면 MAF 기본 처리기 `_deny_all_permissions`가 `PermissionDecisionUserNotAvailable()`로 전부 거부한다(`_agent.py:227-232`, `:527-532`). 처리기는 "kind가 `custom-tool`이고 이름이 앱 도구 목록에 있으면 승인, `finalize_referral`은 사람 승인 대기, 나머지 kind는 거부"로 작성해야 한다(3.5절 예시) |
| 9 | `available_tools`가 내장 도구를 제한하는가 | 맞음 | 허용 목록은 내장·MCP·커스텀을 합친 전체 카탈로그에 적용된다(`client.py:2572-2580`). copilot-cli 모드에서 `available_tools=["view"]`이면 모델에게 `view`만 보인다(`test_session_config_e2e.py:670-688`). **커스텀 도구 이름도 반드시 포함해야 한다.** 예: `available_tools=["custom:record_case_profile","custom:search_schemes","custom:check_eligibility","custom:finalize_referral"]` 또는 `ToolSet().add_custom("*")`. MAF는 이 키를 `create_session`으로 그대로 전달한다(`_agent.py:498-507`) |
| 10 | headless 서버 컨테이너에서 내장 도구(셸·파일)가 기본으로 켜지는가, 끄는 방법 | 확인됨: 켜짐 | 기본 `mode="copilot-cli"`는 내장 도구를 모두 노출하고 호스트 파일시스템에 닿을 수 있다(`docs/setup/multi-tenancy.md:31-35`, `:418-422`). 끄는 방법 세 가지: (1) `available_tools`로 앱 도구만 허용(권장, 최소 변경), (2) `CopilotClient(mode="empty", base_directory=...)` + 세션마다 `available_tools` 필수(`_mode.py:343-371`), (3) `excluded_tools=["builtin:*"]` 또는 `ToolSet().add_builtin("*")`를 차단 목록에 넣기. 권한 처리기 거부는 실행만 막을 뿐 도구 노출은 막지 못한다. MAF가 `mode=`를 클라이언트에 넘기는지는 MAF 명세로 확인 `[미확인]`. 클라이언트를 직접 만들어 `client=`로 넘기면 앱이 `mode`를 정할 수 있다 |
| 11 | 구조화 출력·응답 형식 강제가 없다고 보고 도구 인자로만 받는다(3.6절) | 틀림(SDK에는 있음) | v1.0.28에 실험 기능으로 `session.send_and_wait_typed(prompt, PydanticModel)`과 `send(..., response_schema=...)`가 있다(`session.py:2603-2646`, README `:797-845`). 다만 MAF 2.1.1 `_run_impl`은 `copilot_session.send_and_wait(prompt, attachments=..., timeout=...)`만 호출하고 `response_schema`를 넘기지 않는다(`_agent.py:1041`). MAF 경유로는 쓸 수 없으므로 TRD의 "도구 인자로 구조화" 방식은 MAF 경로에서 유효한 선택이다. 문장은 "SDK는 실험적 응답 스키마를 지원하지만 MAF GitHubCopilotAgent 2.1.1이 전달하지 않으므로 도구 인자로 받는다"로 고친다 |
| 12 | 모델 호출 제한 시간 45초, 실패 시 1회 재시도(7절) | 부분적으로 맞음 | `send_and_wait(timeout=45)`는 대기만 끊고 런타임 작업은 계속된다. 반드시 `session.abort()`를 함께 호출한다(`session.py:2316-2317`, `:4034`). MAF는 `timeout` 옵션(기본 60초, `GITHUB_COPILOT_TIMEOUT`)을 `send_and_wait`에 전달한다(`_agent.py:521-522`, `:1041`). 모델 호출 수준 재시도는 런타임이 이미 수행하며 `assistant.turn_retry`로 관찰된다 |
| 13 | 429·시간 초과가 이어지면 저장된 실행 재생(7절) | 맞음(감지 방법 보완) | 429 감지는 `session.error.errorType`(예 `"rate_limit"`, `"quota"`)과 `statusCode`로 한다. MAF 경로에서는 `AgentException("GitHub Copilot request failed: ...")`로 감싸져 올라온다(`_agent.py:1042-1043`). 원인 분류가 필요하면 세션 이벤트를 직접 구독한다 |
| 14 | 실행별 `AgentSession`으로 후속 질문 재사용(3.2절, F9) | 맞음 | SDK 세션은 `disconnect` 전까지 맥락을 유지하고, 끊은 뒤에도 `resume_session(session_id)`로 재개된다(2.2절). 30분 뒤 삭제 정책은 `client.delete_session(session_id)`로 구현하고, 자동 정리는 `session_idle_timeout_seconds`로 보조한다 |
| 15 | SSE로 에이전트 토큰 전송(1절) | 맞음 | `streaming=True`일 때 `assistant.message_delta.delta_content`. 최종 `assistant.message`는 항상 온다(README `:927-934`) |
| 16 | `/readyz`에서 `CopilotClient` 시작 여부와 모델 연결 확인(5절) | 맞음 | `await client.get_auth_status()`(`isAuthenticated`), `await client.list_models()`(캐시됨), `await client.ping()`로 확인한다. 워밍업 호출은 premium request를 소모할 수 있다 `[추론]` |
| 17 | Application Insights로 OpenTelemetry(6절, 8절) | 부분적으로 맞음 | 앱 프로세스 span은 MAF/Azure Monitor exporter로 보낸다. Copilot 런타임 span은 `CopilotClient(telemetry=...)`의 OTLP HTTP로만 나가므로 Application Insights에 바로 들어가지 않는다 `[추론]`. 런타임 span까지 보려면 Collector를 사이드카로 두거나, 범위를 앱 span으로 한정한다고 TRD에 적는다. `capture_content=False`로 메모 내용 기록을 끈다 |
| 18 | 개인정보 가린 메모만 모델에 전달(8절) | 맞음(보완) | copilot-cli 모드 기본 system message에는 `environment_context`(cwd, OS 등)가 들어간다. `system_message={"mode":"customize","sections":{"environment_context":{"action":"remove"}},"content":...}`로 제거하거나 `mode="empty"`를 쓴다(`_mode.py:142-176`) |

질문별 요약 답

- 커스텀 도구 처리기가 받는 호출 문맥: `ToolInvocation.session_id`, `tool_call_id`, `tool_name`, `arguments`, `agent_id`, `request_id`(+ tool search 전용 `available_tools`). 앱 kwargs는 없다. MAF 래퍼를 거치면 MAF가 `FunctionInvocationContext.kwargs`를 채운다.
- 커스텀 도구 승인 요구: 기본값(`skip_permission=False`)에서 kind `"custom-tool"` 권한 요청이 생긴다. 승인 불필요 도구는 `skip_permission=True`로 둔다(MAF 2.1.1 변환은 이 값을 설정하지 않음). 훅 `"ask"` 경로의 kind는 `[미확인]`.
- `available_tools`의 내장 도구 제한: 제한한다. 커스텀 도구 이름도 넣어야 한다.
- headless 컨테이너의 내장 도구 기본 상태: copilot-cli 모드에서 켜져 있다. `available_tools`, `mode="empty"`, `excluded_tools`로 끈다.
- 구조화 출력: SDK 1.0.28에 실험 기능으로 있다(`send_and_wait_typed`, `response_schema`). MAF 2.1.1 경유로는 전달되지 않는다.

---

## 6. "깊이 있게" 쓸 만한 기능 후보

평가 축: 모델 연결 / 에이전트 설계 / 오케스트레이션 / 도구 호출 / 컨텍스트 처리 / 스트리밍. 비용 S(반나절 이하), M(하루), L(이틀 이상).

| 기능 | 평가 축 | 동행노트에서의 구체 용도 | 비용 | 위험 | 근거 |
|---|---|---|---|---|---|
| 권한 kind별 정책 처리기(`custom-tool` 승인 목록 + `finalize_referral` 사람 승인 + 그 밖 거부) | 도구 호출, 에이전트 설계 | 3.5절 승인 흐름을 SDK 권한 모델 위에 정확히 구현. 승인 요청 SSE에 `tool_name`, `args`, `tool_call_id`를 그대로 실음 | S | `ask` 경로 kind 미확인 → 두 kind 모두 처리 | 3.5절, 5절 #6~8 |
| `available_tools` 허용 목록(또는 `mode="empty"`) | 에이전트 설계, 도구 호출 | 에이전트별로 필요한 도구만 노출(Profiler는 `record_case_profile`, 매칭은 `search_schemes`·`check_eligibility`, Documenter는 `finalize_referral`). 공개 앱에서 셸·파일·웹 도구 원천 차단 | S | 커스텀 도구 이름 누락 시 도구가 사라짐. empty 모드는 MAF가 지원하는지 확인 필요 | 3.4절, 5절 #9~10 |
| 스트리밍 이벤트 전체 매핑 | 스트리밍 | `assistant.intent`→단계 문구, `message_delta`→토큰, `tool.execution_start/complete`→도구 타임라인, `permission.requested`→승인 카드, `assistant.usage`→단계별 토큰·지연 표시 | M | 이벤트 필드 이름은 생성 코드 기준으로 버전마다 늘어남 → 1.0.28 고정 | 3.2절 |
| `on_post_tool_use` / `on_post_tool_use_failure` 훅으로 판정 기록 감사 | 도구 호출, 컨텍스트 처리 | `check_eligibility` 결과를 훅에서 판정 기록과 대조해 Verifier 입력을 이중 확보. 실패 시 `additionalContext`로 "누락 필드를 질문하라" 재시도 안내 | M | 사용자 훅을 주면 MAF 기본 `ask` 훅이 꺼질 수 있음(MAF는 `on_pre_tool_use`만 해당) → `on_pre_tool_use`는 건드리지 않음 | 3.8절, `_agent.py:1534-1561` |
| `on_user_prompt_submitted` 훅의 인젝션 방어 | 컨텍스트 처리 | 메모가 `<case_note>` 구분자 없이 들어오면 `{"decision":"block"}`. 사례 5 평가에서 방어 계층을 보여 줌 | S | 과차단 | 3.8절 |
| system message `customize` | 컨텍스트 처리, 에이전트 설계 | `environment_context` 제거, `tone`을 상담 보고서체로 교체, `code_change_rules` 제거. 에이전트별 지시문을 섹션 단위로 관리 | S | MAF가 `instructions`를 `system_message` append로 바꾸는 규칙과 충돌 가능(`_agent.py:1292-1310`) → MAF `default_options["system_message"]`로 넘김 | 3.6절 |
| 구조화 출력 `send_and_wait_typed` | 모델 연결, 도구 호출 | Profiler의 `CaseProfile` 추출을 도구 인자 대신 응답 스키마로 강제(MAF 바깥 SDK 직접 호출 경로가 필요) | M | 실험 기능, MAF 경로 미지원, 모델별 strict 지원 차이 | 3.7절, 5절 #11 |
| `reasoning_effort` + `list_models()` 기반 모델 선택 | 모델 연결 | 시작 시 `list_models()`로 사용 가능 모델·`supported_reasoning_efforts` 확인 후 Profiler·매칭은 낮게, Documenter는 높게 설정. `/readyz`에 모델 ID 표시 | S | 계정 정책에 따라 모델 목록이 다름 | 3.1절 |
| `session.abort()` + 시간 초과 처리 | 오케스트레이션 | 분야별 매칭 하나가 45초를 넘으면 중단하고 나머지로 진행(TRD 7절) | S | abort 후 같은 세션 재사용 시 상태 확인 필요 | 4절 3항 |
| `assistant.usage` 집계 | 모델 연결, 스트리밍 | 실행별 입력·출력 토큰, `timeToFirstTokenMs`, `cost`를 UI와 평가 결과에 기록 | S | 임시 이벤트라 이력(`get_events`)에 남지 않을 수 있음 `[추론]` | 3.2절 |
| 커스텀 에이전트(`custom_agents`) | 에이전트 설계, 오케스트레이션 | 후속 질문(F9)에서 "제도 설명" 하위 에이전트를 런타임 위임으로 사용 | M | MAF Workflow 오케스트레이션과 역할 중복. 평가에서 두 프레임워크 중 어느 쪽이 오케스트레이션을 맡는지 흐려짐 → 후순위 | 3.10절 |
| `resume_session` + `delete_session` 수명 관리 | 컨텍스트 처리 | 후속 질문 시 같은 세션 재개, 30분 뒤 영구 삭제로 "저장 없음" 보장 | S | 컨테이너 재시작 시 디스크 세션 유실(설계상 허용) | 2.2절 |
| `on_error_occurred` 훅 | 오케스트레이션 | `errorContext="model_call"`이면 `retry`(1회) 후 `abort`, 사용자 알림 문구 생성 | S | 런타임 자체 재시도와 중복 | 3.8절 |
| OTel 문맥 전파 | 오케스트레이션(관측) | 앱 요청 span → `send` → 도구 처리기 span이 같은 trace로 묶임. 도구 span에 `decision_id` 속성 기록 | S(앱 span) / M(Collector 포함) | CLI span 미수집 시 trace 단절 | 3.11절 |

우선순위 제안(심사 1번 항목 "활용의 깊이" 기준): 권한 kind별 정책 처리기, `available_tools` 허용 목록, 스트리밍 이벤트 전체 매핑, post-tool 훅 감사를 먼저 구현한다. 네 가지 모두 SDK 고유 기능이고 MAF Workflow와 역할이 겹치지 않으며 비용이 S~M이다.

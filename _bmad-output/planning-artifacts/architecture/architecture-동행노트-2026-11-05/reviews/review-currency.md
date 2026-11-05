# Review — Currency / Reality-Check Lens

- **Target:** `ARCHITECTURE-SPINE.md` (동행노트, 2026-11-05)
- **Reviewer lens:** checks whether each committed decision (versions, named technologies, API claims) was confirmed against live sources or just asserted from memory.
- **Date of checks:** 2026-11-05
- **Method:**
  - Read the PyPI JSON API for every Stack pin and compared `requires_dist` across pins.
  - Resolved all 11 pins in a throwaway uv venv (py3.12) and ran `uv pip check`. Also ran `uv pip compile` for linux/x86_64 py3.12.
  - Read the installed source of `agent_framework`, `agent_framework_github_copilot`, `copilot` and `azure.identity`.
  - Ran a runtime smoke test of the MAF workflow shape the spine depends on: switch-case → fan-out → fan-in → `request_info` → resume.
  - Checked the Azure claims against Microsoft Learn.

## Verdict

**Mostly current and reality-checked, with three precision gaps.**

- **What holds up:**
  - Every pinned Python package is the PyPI latest as of 2026-11-05, and the pins are mutually compatible.
  - The core MAF and Copilot SDK API claims exist with the claimed signatures.
  - The Azure claims are confirmed by current docs.
- **The three gaps:**
  - AD-10's "`abort`" has no public call site on the MAF path.
  - AD-15's user-assigned identity with `DefaultAzureCredential` needs `AZURE_CLIENT_ID`, and the spine doesn't say so.
  - The spine itself doesn't pin, or cite a verification for, the Copilot CLI runtime version or the Azure REST api-versions it relies on.

---

## 1. Stack pins vs PyPI (checked 2026-11-05)

| Package | Spine pin | PyPI latest | Latest upload | Match | Notes |
| --- | --- | --- | --- | --- | --- |
| fastapi | 0.162.0 | 0.162.0 | 2026-10-23 | ✅ | Needs `starlette>=0.46` (resolved 1.10.0) and `opentelemetry-api>=1.44.0`. Ships a native `fastapi.sse.EventSourceResponse`/`ServerSentEvent` with `id`, `retry` and keep-alive `: ping`, so no `sse-starlette` is needed. |
| uvicorn | 0.54.0 | 0.54.0 | — | ✅ | |
| agent-framework-core | 1.24.0 | 1.24.0 | 2026-10-30 | ✅ | Needs `opentelemetry-api>=1.39.0,<2`. |
| agent-framework-github-copilot | 2.1.1 | 2.1.1 | — | ✅ | Needs `agent-framework-core>=1.22.0,<2` and `github-copilot-sdk>=1.0.16,<2.0`, with `requires_python>=3.11`. |
| github-copilot-sdk | 1.0.28 | 1.0.28 | 2026-10-28 | ✅ | Bundles `CLI_VERSION = "1.0.105"` (`copilot/_cli_version.py:18`), which is **not in the Stack table** (see F3). |
| opentelemetry-sdk | 1.45.2 | 1.45.2 | — | ✅ | Must stay `~=1.45.0`, because azure-monitor-opentelemetry requires it. |
| azure-monitor-opentelemetry | 1.8.11 | 1.8.11 | — | ✅ | Needs `opentelemetry-sdk~=1.45.0` and `opentelemetry-instrumentation-fastapi==0.66b*`. That instrumentation's `_instruments = fastapi ~= 0.92`, so 0.162 is allowed. |
| azure-ai-documentintelligence | 1.0.2 | 1.0.2 | 2025-03-27 | ✅ | Still the latest. Default `api_version="2024-11-30"` (verified in the package source). |
| azure-identity | 1.27.0 | 1.27.0 | — | ✅ | |
| httpx | 0.28.1 | 0.28.1 | — | ✅ | |
| python-multipart | 0.0.33 | 0.0.33 | — | ✅ | `requires_python>=3.11` |
| Python | 3.12 | 3.15.2 (newest cycle) | — | ⚠️ acceptable | 3.12 has been security-only since 2025-04-02, with EOL 2028-10-31. 3.13 has also moved to security-only (2026-10-01). Source: https://endoflife.date/api/python.json |

**Resolution check:**
- `uv pip install` of all 11 pins on py3.12 gave 67 packages, and `uv pip check` reported them all compatible.
- `uv pip compile --python-platform x86_64-manylinux_2_28` resolved `opentelemetry-api/sdk==1.45.2`, `opentelemetry-instrumentation-fastapi==0.66b2`, `starlette==1.10.0`, `pydantic==2.14.2` and `azure-core==1.41.0`.
- There were no conflicts.

## 2. MAF / Copilot SDK API claims

| Claim in spine | Status | Evidence |
| --- | --- | --- |
| `WorkflowBuilder.add_switch_case_edge_group(source, cases)` with `Case`/`Default` | ✅ exists | `agent_framework/_workflows/_workflow_builder.py`. Smoke test routed correctly. |
| `add_fan_out_edges(source, targets)` / `add_fan_in_edges(sources, target)` (target receives `list[T]`) | ✅ | The smoke test's fan-in got `list[Msg]` from 3 matchers. |
| `WorkflowBuilder(start_executor=…, output_from=[…], intermediate_output_from=[…] \| "all" \| "all_other")` | ✅ | `_workflow_builder.py:148, 639-649`. If omitted, every `yield_output` still surfaces as an `output` event (verified), so the AD-8 single event path works either way. |
| `ctx.yield_output(...)` | ✅ | Smoke test |
| `ctx.request_info(request_data, response_type, *, request_id=None)` + `@response_handler` | ✅ | Smoke test: `request_info` event, then `wf.run(responses={rid: True}, stream=True)` resumed and the handler ran. |
| `FunctionInvocationContext` → `ctx.kwargs` filled from `run(..., function_invocation_kwargs=…)` | ✅ | `GitHubCopilotAgent.run` accepts `function_invocation_kwargs`. A tool read `ctx.kwargs["run_id"]`, and the ctx parameter is excluded from the tool schema. |
| `default_options["system_message"] = {"mode":"replace", …}` | ✅ | `GitHubCopilotOptions.system_message`. `_agent.py` `_prepare_system_message` keeps the `mode` even when `instructions=` is also passed. |
| `default_options["on_permission_request"]` | ✅ typed | `GitHubCopilotOptions.on_permission_request`. `PermissionRequestCustomTool.kind == "custom-tool"` with `tool_name`. |
| `default_options["available_tools"]` (`custom:` prefix) | ⚠️ works but **untyped** | Not a key of `GitHubCopilotOptions`. It passes through `**opts` to `CopilotClient.create_session`/`resume_session`, which accept it (`_agent.py:1740-1805`). |
| `default_options["hooks"]` with only `on_post_tool_use`/`on_error_occurred` | ⚠️ works but **untyped** | Merge logic at `_agent.py:1534-1594` returns the caller's hooks unchanged when there is no `on_pre_tool_use` and no approval-required tools. `PostToolUseHookInput`/`ErrorOccurredHookInput` carry `sessionId`. |
| `CopilotClient.resume_session(...)` | ✅ | `copilot/client.py`. Accepts the same session config as `create_session` (incl. `on_event`). |
| `CopilotClient.delete_session(session_id)` | ✅ | `copilot/client.py:4360` |
| **`abort`** (AD-10: `call_agent` does "45초 제한·`abort`") | ❌ **not reachable publicly** | No `CopilotClient.abort`. Only `CopilotSession.abort()` exists (`copilot/session.py:4034-4054`). MAF creates and resumes the `CopilotSession` inside `_session_run_scope` (`_agent.py:1595-1645`) and never exposes it. Cancelling the streaming path only unsubscribes (≈`_agent.py:1228-1250`). The non-streaming path uses `send_and_wait(timeout)` (≈`_agent.py:1041`), which stops waiting but not the work (`docs/reference/copilot-sdk.md` §4.3). See F1. |

## 3. Azure claims

| Claim | Status | Evidence |
| --- | --- | --- |
| Container App secret as a Key Vault reference using a **user-assigned** identity, consumed via `secretRef` | ✅ | `secrets: [{name, keyVaultUrl, identity: <UAMI resourceId> \| "system"}]`. The identity needs *Key Vault Secrets User*. https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets (updated 2026-09-11) |
| AI Services `kind: AIServices` with `disableLocalAuth: true` | ✅ | https://learn.microsoft.com/en-us/azure/ai-services/disable-local-auth (2026-05-31). The ARM `Microsoft.CognitiveServices/accounts` reference lists API 2026-09-01. Entra auth needs a **custom subdomain** (in TRD.md:251, not in the spine). |
| Speech fast transcription `api-version=2025-10-15`, ko-KR, diarization | ✅ | https://learn.microsoft.com/en-us/azure/ai-services/speech-service/fast-transcription-create (2026-10-02). Curl samples use `2025-10-15`. `diarization: {"maxSpeakers":2,"enabled":true}` is supported. ko-KR is in the specified-locale list. The page now also offers *Azure LLM Speech* and *MAI-Transcribe-2* modes. **Region not verified**: fast transcription is region-limited. |
| Document Intelligence `prebuilt-read` 2024-11-30, Korean handwriting | ✅ | https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr?view=doc-intel-4.0.0 (2026-04-18). Korean `ko` is in the read-model **handwritten** table. SDK 1.0.2 defaults to `2024-11-30`. |

---

## 4. Findings

### F1 — MEDIUM — AD-10 commits to `abort`, but there is no public abort on the MAF Copilot path
- **Item:** AD-10 (spine line 117): "`agents.call_agent` … 45초 제한·`abort`·1회 재시도".
- **Evidence:**
  - `copilot/client.py` has no `abort`. `copilot/session.py:4034-4054` has `CopilotSession.abort()`, but `agent_framework_github_copilot/_agent.py:1595-1645` creates the session internally and never exposes it.
  - Cancelling the stream only unsubscribes (`_agent.py` ≈1228-1250).
  - The non-streaming timeout (`send_and_wait`, ≈1041) does not stop server-side work (`docs/reference/copilot-sdk.md` §4.3).
  - So a retry after a timeout would run concurrently with the still-running first turn on the same session.
- **Fix:** Name the mechanism in AD-10. Recommended:
  1. Wrap each call in `asyncio.timeout(45)`, which covers both streaming and non-streaming.
  2. On timeout, call `await client.delete_session(agent_session.service_session_id)` (public, `client.py:4360`).
  3. Retry once on a **new** `AgentSession`.

  If you keep a true abort instead, use the private `client._get_session(sid).abort()`. In that case, record that it is a private API, keep `github-copilot-sdk==1.0.28` exactly pinned, and cover it with a test.

### F2 — MEDIUM — AD-15 user-assigned identity with `DefaultAzureCredential` needs `AZURE_CLIENT_ID`
- **Item:** AD-15 (line 154): "사용자 할당 관리 ID(`DefaultAzureCredential`)".
- **Evidence:**
  - `azure/identity/_credentials/default.py:111-117,160-161`: `ManagedIdentityCredential` inside DAC uses `managed_identity_client_id` or the env var `AZURE_CLIENT_ID`. Without either, it requests a **system-assigned** token, which fails if only a UAMI is attached.
  - The spine and TRD.md never mention `AZURE_CLIENT_ID`.
- **Fix:**
  - Add to AD-15 and the Bicep: the Container App env `AZURE_CLIENT_ID = <uami>.properties.clientId`.
  - Alternatively, construct `DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id)` or use `ManagedIdentityCredential(client_id=…)` directly.
  - Optionally set `AZURE_TOKEN_CREDENTIALS=prod` (default.py:179) so DAC doesn't probe developer credentials in the container.
  - Note that ACR pull uses `registries[].identity = <UAMI id>` and Key Vault references use `identity = <UAMI id>`. Both are configured separately from DAC.

### F3 — LOW-MEDIUM — The Copilot CLI runtime (the real model-calling component) is not pinned or provisioned in the spine
- **Item:** Stack table (lines 170-186).
- **Evidence:**
  - `github-copilot-sdk 1.0.28` bundles `CLI_VERSION = "1.0.105"` (`copilot/_cli_version.py:18`).
  - The runtime binary is resolved or downloaded on the `CopilotClient.__init__` path (`copilot/client.py:1865, 1901-1926`), which means a network download at container start unless it is prefetched (`docs/reference/copilot-sdk.md` §1.2, §5 #2-3).
- **Fix:**
  - Add a Stack row: `Copilot CLI runtime | 1.0.105 (bundled by github-copilot-sdk 1.0.28)`.
  - Add a Dockerfile/Structural Seed note: run `python -m copilot download-runtime` at build time with `COPILOT_CLI_EXTRACT_DIR` set, and set `COPILOT_SKIP_CLI_DOWNLOAD=1` at runtime.
  - Use a glibc base (`python:3.12-slim`), not Alpine.

### F4 — LOW — `available_tools` and `hooks` rely on untyped pass-through options
- **Item:** AD-12 (line 129).
- **Evidence:** `GitHubCopilotOptions` TypedDict keys are `system_message, cli_path, model, timeout, log_level, on_permission_request, mcp_servers, provider, instruction_directories, skill_directories, disabled_skills, base_directory, enable_file_hooks, telemetry, on_pre_tool_use, on_function_approval`. `available_tools` and `hooks` are absent and reach `create_session` only via `**opts` (`_agent.py:1740-1805`).
- **Risk:** A type checker won't catch a misspelt key, and a future MAF minor version could drop or rename the pass-through. If `available_tools` is silently dropped, built-in CLI tools (shell, file) become visible again. AD-12's deny-by-default `on_permission_request` still blocks them, but the model wastes turns.
- **Fix:**
  - Add a startup assertion or unit test that each agent's created session config contains `available_tools == ["custom:…"]` and the two hooks.
  - Keep `agent-framework-github-copilot` exactly pinned.

### F5 — LOW — Versions in the spine have no verification stamp or lock, and there is a known trap for DevUI/AG-UI
- **Item:** Stack table.
- **Evidence:**
  - The verification date exists only in `TRD.md:20` ("2026-11-05 PyPI 확인"). The spine has no date or source.
  - `agent-framework-devui 1.0.0b261030` requires `fastapi<0.142.0`, and `agent-framework-ag-ui 1.7.1` requires `fastapi<0.142.0` (PyPI JSON). Both are incompatible with the fastapi 0.162.0 pin (`docs/reference/agent-framework.md` §1.1).
  - `opentelemetry-sdk` cannot move past 1.45.x while azure-monitor-opentelemetry 1.8.11 is pinned.
- **Fix:**
  - Add "PyPI 확인 2026-11-05" under the Stack heading.
  - Commit a lock file (`uv.lock` or `uv pip compile` output for linux/py3.12).
  - Add notes to the Stack table: "opentelemetry-sdk is constrained by azure-monitor-opentelemetry (`~=1.45.0`)" and "Do not add agent-framework-devui/ag-ui (fastapi<0.142)".

### F6 — LOW — The Azure REST api-versions and model choices the code depends on are not in the spine
- **Item:** Stack table and AD-15. OCR and STT calls are core capabilities.
- **Evidence:**
  - TRD.md:181-182 implies Speech `2025-10-15` and DI `2024-11-30`. Both are confirmed current (see §3).
  - The fast transcription page (2026-10-02) now offers alternative LLM Speech and MAI-Transcribe-2 modes, and region support varies.
  - Entra auth on AI Services requires a custom subdomain (TRD.md:251), which the spine does not state.
- **Fix:**
  - Add Stack rows: `Speech fast transcription REST | api-version 2025-10-15 (Azure Transcribe default model, ko-KR, diarization maxSpeakers 2)` and `Document Intelligence | prebuilt-read, api 2024-11-30`.
  - Add to AD-15: "AI Services `customSubDomainName` required (Entra token)" and "region must be in the fast-transcription region list; verify before `azd up`".
  - Keep BUILD_PLAN.md:19-21's real-sample OCR/STT check as a gate.

### F7 — LOW — The Python 3.12 choice is not justified
- **Item:** Stack, Python 3.12.
- **Evidence:** endoflife.date shows 3.12 security-only since 2025-04-02 and EOL 2028-10-31. 3.14 (3.14.10) and 3.15 (3.15.2) are current. All pins support py>=3.11.
- **Fix:** No change is required for a hackathon. State "3.12 (security-only until 2028-10; chosen for wheel availability)" or move to 3.13/3.14 after a one-time `uv pip check`. Pin the patch in the base image (`python:3.12.16-slim`).

### F8 — INFO — Points worth recording (confirmed, no change needed)
- **SSE:** fastapi 0.162 has a native `fastapi.sse.EventSourceResponse` + `ServerSentEvent(id=…, retry=…)` with keep-alive pings. AD-8's `Last-Event-ID` design maps onto it directly, so no extra SSE dependency is needed. Optionally name it in the seed to prevent someone adding `sse-starlette`.
- **`system_message` `replace`:** this removes the SDK's built-in safety and tool-usage guidance (`docs/reference/copilot-sdk.md` §3.6). AD-11/AD-12 prompts must carry the necessary rules themselves. This is a known trade-off, not an error.
- **Timing middleware on the Copilot path:** function middleware does not run there (`docs/reference/agent-framework.md` §4.2). Any per-step timing middleware must be agent-level, or done in `call_agent`, which the spine already centralises.
- **Default permission handler:** when no `on_permission_request` is given, the default `_deny_all_permissions` (`_agent.py` ≈227) denies everything, and MAF tool conversion does not set `skip_permission` (≈1490). So AD-12's explicit allow-list handler is required for the custom tools to work at all. This is correct as designed.

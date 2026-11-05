---
id: T00
title: 계약 골격(모든 모듈 시그니처, 공유 타입, 설정, 테스트 기반)
sprint: S0
priority: P0
cut_rank: 0
deps: []
owns: [requirements.txt, requirements-dev.txt, pytest.ini, app/__init__.py, app/config.py, app/schemas.py, app/rules.py, app/masking.py, app/textnum.py, app/verify.py, app/render.py, app/limits.py, app/runs.py, app/events.py, app/tools.py, app/prompts.py, app/telemetry.py, app/agents.py, app/context.py, app/ingest.py, app/workflow.py, app/executors/, app/service.py, app/replay.py, app/evaluation.py, app/ask.py, app/main.py, app/static/, scripts/record_replay.py, tests/__init__.py, tests/conftest.py, tests/fakes.py, tests/test_contracts.py]
verify: ["python -m compileall -q app", "python -m pytest -q tests/test_contracts.py"]
features: [F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12, F13, F14]
flag: null
---

# T00 — 계약 골격

## 목표

다른 모든 태스크가 서로 기다리지 않고 병렬로 일할 수 있게, 모든 모듈 파일을 시그니처만 있는 상태로 먼저 만든다. 본문은 `raise NotImplementedError("Txx")`(그 함수를 채울 태스크 ID)로 둔다. 공유 타입(`schemas.py`)과 설정(`config.py`)은 이 태스크에서 완성본으로 만든다. 이 태스크가 끝나면 `app/` 아래 모든 모듈이 import되고, 이후 태스크는 자기 파일의 본문만 채운다.

## 근거

- 스파인 AD-1(층), AD-2(공유 타입 먼저 병합), AD-3(ID), AD-4(상태 필드와 쓰는 주체), AD-16(작업 분할·플래그)
- TRD 1절(버전), 4.4절(메시지 타입), 5절(API·이벤트), 6절 표 7(환경변수)
- 스파인 Consistency Conventions "이벤트 데이터"

## 계약

### 의존 패키지

- `requirements.txt`: TRD 1절과 스파인 Stack의 고정 버전 그대로(`fastapi==0.162.0`, `uvicorn==0.54.0`, `pydantic==2.14.2`, `agent-framework-core==1.24.0`, `agent-framework-github-copilot==2.1.1`, `github-copilot-sdk==1.0.28`, `opentelemetry-sdk==1.45.2`, `azure-monitor-opentelemetry==1.8.11`, `azure-ai-documentintelligence==1.0.2`, `azure-identity==1.27.0`, `httpx==0.28.1`, `python-multipart==0.0.33`).
- `requirements-dev.txt`: `-r requirements.txt`, `pytest`, `pytest-asyncio`. 버전은 설치 시점 최신으로 고정한다.
- `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`.

### `app/config.py` (완성본)

- `Settings`(Pydantic 모델, `from_env()` 클래스 메서드). 앱이 읽는 환경변수는 스파인 Conventions "설정"의 9개와 아래 기능 플래그 10개뿐이다. 다른 모듈은 `os.environ`을 읽지 않는다.
- 기능 플래그(모두 `bool`, 기본 `False`): `ENABLE_AI_SERVICES`, `ENABLE_IMAGE_INPUT`, `ENABLE_AUDIO_INPUT`, `STT_DIARIZATION`, `ENABLE_BROWSER_RECORDING`, `ENABLE_REAPPROVAL`, `ENABLE_ASK`, `ENABLE_SESSION_HOOKS`, `ENABLE_CONTEXT_PROVIDER`, `MATCH_PARALLEL`. `"1"`, `"true"`, `"yes"`(대소문자 무시)를 참으로 읽는다. `ENABLE_AI_SERVICES`가 거짓이면 `ENABLE_IMAGE_INPUT`·`ENABLE_AUDIO_INPUT`은 읽은 값과 관계없이 거짓이다.
- `Settings.features() -> Features`(UI에 보낼 플래그 묶음).
- 상수: `MAX_TEXT_CHARS = 4000`, `MAX_IMAGE_BYTES = 5 * 1024 * 1024`, `MAX_AUDIO_BYTES = 10 * 1024 * 1024`, `MAX_AUDIO_MS = 120_000`, `OCR_MIN_CONFIDENCE = 0.8`, `RUN_IDLE_TTL_S = 1800`, `RUN_HARD_TTL_S = 2700`, `MAX_CONCURRENT_RUNS = 4`, `RATE_LIMIT_PER_MIN = 5`, `EVAL_RATE_PER_MIN = 1`, `EVAL_CONCURRENCY = 2`, `EVAL_DEADLINE_S = 360`, `AGENT_TIMEOUT_S = 45`, `AGENT_MAX_ATTEMPTS = 2`, `SUBMIT_REJECT_LIMIT = 2`, `SSE_HEARTBEAT_S = 15`.

### `app/schemas.py` (완성본)

TRD 4.4절의 타입 전부와 아래를 Pydantic v2 모델로 정의한다. 모르는 값은 `None`이 기본이다.

- 리터럴: `Domain`(`living`·`health`·`care`), `Step`(AD-3 단계 이름 12개 + `ask`), `SectionId`(구획 ID 9개), `Decision`(`eligible`·`unknown`·`ineligible`), `RunStatus`(`queued`·`running`·`replaying`·`awaiting_approval`·`resuming`·`finalized`·`drafted`·`failed`·`replaced`·`expired`), `InputSource`(`text`·`image`·`audio`), `Mode`(`live`·`replay`), `Phase`(`workflow`·`ask`), `ErrorCode`(`rate_limit`·`timeout`·`tool_missing`·`other`·`pii_residual`·`input_invalid`·`recognition_failed`).
- 제도·판정: `SchemeRule{condition_id, field, op, value, ratio}`, `Scheme{id, name, domain, summary, rules, required_fields, source_url, checked_at, is_example}`, `SchemeCatalog{median_income_krw: dict[int,int], median_income_source_url, checked_at, schemes}`, `SchemeSummary{id, name, summary, required_fields}`, `ConditionResult{id, met: bool | None, used_values: dict, note}`, `RuleOutcome{scheme_id, decision, conditions, missing_fields, source_url}`, `DecisionRecord{decision_id, scheme_id, domain, decision, conditions, missing_fields, source_url, source: "tool" | "verifier"}`.
- 프로필: `CaseProfile`(TRD 4.1의 13개 필드. `household_type`·`disability`·`housing`은 리터럴).
- 가리기·인식: `PiiSpan{start, end, kind, placeholder}`, `MaskResult{masked_text, spans, pii_map: dict[str,str], residual: list[PiiSpan]}`, `TextSpan{start, end}`, `Transcript{text, uncertain: list[TextSpan], speakers: int | None, duration_ms: int | None, chars}`, `NoteEdit{original, replacement, reason}`, `CleanNote{clean_text, edits, uncertain: list[str]}`.
- 워크플로 메시지: `RunInput{source, note, media: bytes | None (직렬화 제외), media_type, case_id, origin_run_id}`, `RecognizedText{source, text, transcript}`, `MaskedNote{source, masked_text}`, `ProfileReady{run_id}`, `MatchChain{results: list[MatchResult]}`(직렬 매칭용), `Recommendation`, `MatchSubmission`, `MatchResult`, `RemovedItem{scheme_id, decision_id, reason}`, `VerifiedItem{decision: DecisionRecord, explanation, follow_up_questions, priority}`, `VerifiedResult{eligible, needs_check, ineligible: list[VerifiedItem], removed, failed_domains, supplemented: list[str], audit_rule_skipped: list[Step]}`, `DraftDocuments`, `DraftReady{draft}`.
- 승인·확정: `ApprovalRequest{run_id, scheme_ids, documents_summary, draft_snapshot: DraftDocuments}`, `ApprovalDecision{request_id, approved, edited_sections: dict[SectionId,str], scheme_ids: list[str] | None}`, `FinalDocuments{sections: dict[SectionId,str], scheme_ids, finalized_at}`.
- 에이전트 호출: `InvocationKwargs{run_id, step, phase}`, `AuditEntry{tool, call_id, decision_id}`, `StepAudit{entries, calls, results, complete}`, `AgentCallResult{ok, error_code, attempts, text}`.
- 이벤트: `UiEvent{type, step, data: dict}`, `Envelope{run_id, seq, ts, type, step, mode, trace_id, data}`. 이벤트별 `data` 모델은 스파인 Conventions "이벤트 데이터"의 필드 그대로 `MaskedData`, `TranscribedData`, `NormalizedData`, `StepCompletedData`, `StepFailedData`, `StepRetryData`, `TokenData`, `ToolCallData`, `ToolResultData`, `UsageData`, `ApprovalRequiredData`, `ReplacedData`, `QueuedData`, `ErrorData`, `DoneData`로 둔다.
- 재생·평가: `ReplayEvent{type, step, data, t_ms}`, `ReplaySnapshot{verified, draft, approval_request}`, `ReplayFile{case_id, recorded_at, events, snapshot}`, `EvalCase`(TRD 4.3 필드 + `case_id`, `title`, `summary`), `CaseMetrics{case_id, replayed, recall, precision, grounding, total_ms, step_ms: dict[Step,int], pii_recall, pii_false_positives, pii_residual, autofilled_fields, manual_fields, supplemented, cer, required_field_matches}`, `EvalSummary{cases, live_count, replay_count, recall, precision, grounding, p50_ms, p95_ms}`.
- 기타: `Readiness{copilot_started, auth_ok, model_ok, ai_services_ok: bool | None, errors: list[str]}`, `Features{image_input, audio_input, browser_recording, ask, reapproval}`, `ApiError{code, message}`.

### 모듈 골격(본문 `NotImplementedError("Txx")`)

| 파일 | 시그니처 | 채우는 태스크 |
|---|---|---|
| `app/rules.py` | `load_catalog(path=DATA/"schemes.json") -> SchemeCatalog`, `evaluate(scheme, profile, catalog) -> RuleOutcome`, `schemes_for(domain, catalog) -> list[Scheme]`, `FIELD_QUESTIONS: dict[str, str]` | T03 |
| `app/masking.py` | `mask(text, source="text", known: dict[str,str] \| None = None) -> MaskResult`, `residual_pii(text) -> list[PiiSpan]` | T04 |
| `app/textnum.py` | `fix_ocr_digits(text) -> str`, `parse_numbers(text) -> set[int]`, `new_numbers(original, cleaned) -> set[int]` | T04 |
| `app/limits.py` | `check_text(text) -> ApiError \| None`, `sniff_media(data: bytes) -> str \| None`, `check_media(data, kind) -> ApiError \| None`, `class RateLimiter(per_min)` + `allow(key, now) -> bool` | T04 |
| `app/verify.py` | `coverage_gaps(decisions, catalog, domains) -> list[str]`, `check_citations(rec, decisions, domain) -> str \| None`, `verify(matches, decisions, audit, catalog) -> VerifiedResult` | T05 |
| `app/render.py` | `render_final(draft_snapshot, edited_sections, verified, scheme_ids) -> FinalDocuments` | T05 |
| `app/runs.py` | `RunState`(AD-4 필드 + `record_decision(outcome, domain, source) -> DecisionRecord`, `claim_approval(request_id) -> bool`, `replace_session(step)`, `touch()`, `set_status(status)`), `EvalState`, `Registry`(`create_run`, `get`, `create_eval`, `get_eval`, `by_session(session_id)`, `evict(now) -> list`, `clear()`, `on_evict`), `REGISTRY` | T06 |
| `app/events.py` | `EventLog`(`append(ev, mode, trace_id) -> Envelope`, `read_after(seq)`, `wait(seq, timeout)`, `close(status)`, `closed`), `map_workflow_event(ev) -> list[UiEvent]`, `map_agent_update(update, step, ask_id=None) -> list[UiEvent]`, `to_sse(env) -> str` | T06 |
| `app/tools.py` | `record_case_profile`, `search_schemes`, `check_eligibility`, `lookup_decision`, `submit_matches`, `submit_draft`, `record_clean_note`(모두 `async def`, MAF `@tool`), `ALL_TOOLS: dict[str, object]` | T09 |
| `app/prompts.py` | `INSTRUCTIONS: dict[Step, str]`, `case_note(text) -> str`, `normalizer_prompt`, `profiler_prompt`, `match_prompt(domain, profile)`, `documenter_prompt(verified, profile, decisions_text \| None)`, `ask_prompt(question)` | T09 |
| `app/telemetry.py` | `setup(settings)`, `span(name, **attrs)`(컨텍스트 관리자), `current_trace_id() -> str` | T10 |
| `app/agents.py` | `TOOL_ALLOWLIST: dict[Step, list[str]]`, `make_permission_handler(step)`, `build_agents(client, settings) -> dict[Step, object]`, `async call_agent(agent, prompt, run, step, *, emit, phase="workflow") -> AgentCallResult` | T10 |
| `app/context.py` | `class StepTimingMiddleware`, `class VerifiedDecisionsProvider` | T10(미들웨어), T16(공급자) |
| `app/ingest.py` | `async ocr_image(data, media_type, settings) -> Transcript`, `async transcribe_audio(data, media_type, settings) -> Transcript`, `async ai_token_ok(settings) -> bool` | T20 |
| `app/executors/core.py` | `InputRouter`, `IntakeExecutor`, `ProfilerExecutor`, `MatchExecutor(domain)`, `VerifierExecutor`, `DocumenterExecutor` | T11 |
| `app/executors/media.py` | `OcrExecutor`, `SttExecutor`, `NormalizerExecutor` | T21 |
| `app/executors/gate.py` | `ReferralGate` | T11(1회 승인), T18(재승인) |
| `app/workflow.py` | `build_workflow(run, agents, settings) -> Workflow` | T11(직렬), T13(병렬) |
| `app/service.py` | `class RunService`(`start(input, *, mode, purpose)`, `respond(run_id, decision)`, `ask(run_id, question)`, `start_eval()`), `async startup(settings)`, `async shutdown()`, `SERVICE` | T12 |
| `app/replay.py` | `load_replay(case_id) -> ReplayFile`, `to_replay_file(case_id, envelopes, run) -> ReplayFile`, `async play(service, run, replay)` | T14 |
| `app/evaluation.py` | `load_cases() -> list[EvalCase]`, `case_metrics(case, run, replayed) -> CaseMetrics`, `summarize(metrics) -> EvalSummary`, `async run_eval(service, eval_state)` | T15 |
| `app/ask.py` | `async answer(service, run, question, ask_id)` | T17 |
| `app/main.py` | FastAPI `app`, TRD 5절 표 4 라우트 + `GET /api/features`. 각 라우트는 501을 돌려주는 자리만 둔다 | T12 |
| `scripts/record_replay.py` | `main(case_ids)` | T14 |

`app/executors/__init__.py`는 세 모듈의 클래스를 다시 내보낸다. `app/static/`에는 `index.html`(빈 세 구획), `style.css`(빈 파일), `js/app.js`, `js/api.js`, `js/timeline.js`, `js/results.js`, `js/drafts.js`, `js/eval.js`, `js/ask.js`, `js/media.js`를 둔다. JS 모듈은 모두 `export function mount(ctx) {}`만 가진다(`ctx = {bus, api, features}`, `bus`는 SSE 이벤트 타입을 이벤트 이름으로 내보내는 `EventTarget`).

### 테스트 기반

- `tests/conftest.py`: 자동 픽스처 `_clean_registry`(각 테스트 전후 `REGISTRY.clear()`), 픽스처 `catalog`(`data/schemes.json`이 있으면 읽고 없으면 `pytest.skip`), `profile_case1`(사례 1과 같은 독거노인 `CaseProfile`), `settings`(플래그 모두 꺼진 `Settings`).
- `tests/fakes.py`: `FakeAgent`(미리 정한 `AgentResponseUpdate` 목록을 흘리고, 지정한 도구 함수를 지정한 인자로 호출하는 스크립트형 가짜), `FakeCopilotClient`(`delete_session`·`list_models`·`get_auth_status` 기록), `make_update(text=None, call=None, result=None, usage=None)`.
- `tests/test_contracts.py`: (1) `app` 아래 모든 모듈 import, (2) `schemas`의 모든 모델이 `model_validate(model.model_dump())` 왕복, (3) `Settings.from_env({})`의 플래그가 모두 거짓, (4) `ENABLE_AI_SERVICES=0`이면 사진·음성 플래그가 거짓, (5) `SectionId`·`Step` 값이 AD-3 목록과 같다.

## 동작

- 골격 함수의 `NotImplementedError` 메시지는 채울 태스크 ID다. 그래서 어느 단계에서 미구현이 터졌는지 바로 안다.
- `schemas.py`와 `config.py`는 이 태스크 이후 계약 변경 요청(SDD README 4절)으로만 바뀐다.

## 수용 기준

- `python -m compileall -q app`가 통과한다.
- `tests/test_contracts.py` 5개 검사가 통과한다.
- `app/` 아래 모든 공개 함수·클래스가 위 표의 이름과 같다.
- 저장소 안에 가상환경·캐시 디렉터리를 만들지 않는다.

## 하지 않는 것

- 함수 본문 구현(각 태스크가 한다), `data/*.json` 작성(T03·T07), Dockerfile·Bicep(T02).

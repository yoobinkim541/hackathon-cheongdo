---
id: T12
title: RunService와 FastAPI 라우트, SSE
sprint: S2
priority: P0
cut_rank: 0
deps: [T02, T11]
owns: [app/service.py, app/main.py, tests/test_service.py, tests/test_api.py]
verify: ["python -m pytest -q tests/test_service.py tests/test_api.py"]
features: [F1, F8, F11]
flag: null
---

# T12 — 서비스·API

## 목표

모든 실행 진입점(실시간·재생·평가·승인 재개·후속 질문)을 `RunService` 하나로 모으고, TRD 5절의 HTTP 라우트와 SSE를 만든다. 재생·평가·후속 질문의 본문은 각 모듈(T14·T15·T17)이 채우고, 이 태스크는 호출 자리와 상태 전이만 맡는다.

## 근거

- TRD 3.2절 "실행 상태"·"실패 처리", 3.5절 6·7번, 5절 전체, 7절, 8절
- 스파인 AD-7(`/ask` 조건), AD-8(SSE 전송), AD-9(재생 전환 절차), AD-10, AD-13, AD-14, Conventions "입구 검사"·"준비 상태"

## 계약

- `startup(settings)`: `telemetry.setup` → `CopilotClient` 시작(CLI `base_directory`는 임시 경로) → 남은 세션 전부 `delete_session` → `get_auth_status()`·`list_models()`로 `Readiness` 작성 → `build_agents` → `ENABLE_AI_SERVICES`면 `ingest.ai_token_ok` → 30초마다 `REGISTRY.evict` 후 돌려받은 실행의 태스크 취소·세션 삭제. 실패해도 예외로 앱을 죽이지 않고 `Readiness.errors`에 적는다.
- `shutdown()`: 진행 중 태스크 취소, `client.stop()`.
- `RunService.start(inp: RunInput, *, mode="live", purpose="live") -> RunState`:
  - 세마포어(`MAX_CONCURRENT_RUNS`)를 기다리는 동안 `queued{position}`.
  - `mode="replay"`면 `replay.play(self, run, replay.load_replay(case_id))`(T14) 태스크.
  - 아니면 `build_workflow` → 백그라운드 태스크가 `workflow.run(inp, stream=True)` 이벤트를 `events.map_workflow_event`로 바꿔 `run.log.append`.
  - 상태 전이(AD-10): `request_info` → `awaiting_approval`(`pending_request_id`, `pending_request` 저장), `finalized` → `finalized` + `done`, `error`·대기 없이 끝난 스트림 → `failed` + `done`.
  - 재생 전환: `purpose="live"`이고 `case_id`가 있고, `error`의 단계가 `profiler`이거나 분류가 `rate_limit`이면 AD-9 절차(태스크 취소 → 세션 삭제 → `replaced{run_id, reason}` + `done` → 상태 `replaced` → 새 재생 실행).
- `RunService.respond(run_id, decision) -> None`: `claim_approval` 실패 → 409. `edited_sections` 키 검사·`scheme_ids` 부분집합 검사 실패 → 400. 실시간은 `workflow.run(responses={request_id: decision}, stream=True)`를 같은 소비 루프로. 재생 실행은 `render.render_final`을 직접 불러 `finalized` 또는 `approval_kept`를 쌓는다. 거부 후 상태는 `ENABLE_REAPPROVAL`이면 `awaiting_approval`(새 `request_info`의 ID로), 아니면 `drafted` + `done`.
- `RunService.ask(run_id, question) -> str`(ask_id): 플래그 꺼짐·상태 불일치·재생·이미 진행 중 → 409. 통과하면 `ask.answer(...)`(T17) 태스크.
- `RunService.start_eval() -> EvalState`: 전역 1건·분당 1회. `evaluation.run_eval(...)`(T15) 태스크.
- 라우트(`main.py`): TRD 5절 표 4 전부 + `GET /api/features`(`settings.features()`). `main.py`는 L0, `limits`, `service`, `runs`(조회), `events`(읽기)만 import한다.
  - 입구 검사: `limits.check_text`, `sniff_media`, `check_media`, IP별 `RateLimiter`(`X-Forwarded-For` 첫 값). 실패는 `{"error":{"code","message"}}`와 400·429.
  - `GET /api/cases`: 정답 라벨 없이 `case_id`, `title`, `summary`, `input_type`.
  - SSE: `Last-Event-ID` 다음부터 보내고, 새 이벤트를 기다리며, 15초마다 `: hb`, `done`을 보낸 뒤에만 닫는다. 지워진 실행은 404.
  - `GET /`는 `app/static/index.html`, `/static`은 정적 파일.
  - `/healthz`는 항상 200, `/readyz`는 `Readiness`가 정상일 때만 200.

## 수용 기준(테스트: `httpx.AsyncClient` + 가짜 워크플로·가짜 클라이언트)

1. `POST /api/runs {case_id:"case1"}` → `{run_id}`, 이어 SSE가 `approval_required`까지 받는다(가짜 워크플로).
2. 같은 SSE를 `Last-Event-ID: 3`으로 다시 열면 4번부터 온다.
3. `POST /approval` 맞는 `request_id` → 200, 같은 요청 두 번째 → 409. 틀린 ID → 409. 모르는 구획 키 → 400.
4. 승인 뒤 `finalized`와 `done`이 로그에 있고 상태가 `finalized`.
5. 거부 + `ENABLE_REAPPROVAL=False` → 상태 `drafted`, `done`.
6. 프로필러 `error`(데모 사례) → 기존 로그에 `replaced`·`done`, 새 실행이 `mode="replay"`로 시작(재생 본문은 가짜).
7. 같은 상황의 직접 입력 → `failed`, `replaced` 없음.
8. 4,001자 메모 → 400, 같은 IP 6번째 요청 → 429.
9. 확장자만 `.jpg`인 텍스트 업로드 → 400.
10. `/api/cases` 응답에 `expected_` 필드가 없다.
11. `ENABLE_ASK=False`에서 `/ask` → 409. `/api/features`가 플래그를 반영한다.
12. `/healthz` 200, `Readiness.errors`가 있으면 `/readyz` 503.

## 하지 않는 것

- 재생 본문(T14), 평가 본문(T15), 후속 질문 본문(T17), 실제 배포(오케스트레이터).

# 프런트엔드 연결 안내

`app/static/`의 화면이 서버에서 기대하는 것만 정리했다. 계약의 원본은 TRD 5절(API·SSE)과 `app/schemas.py`이고, 이 문서는 화면 쪽에서 실제로 읽는 필드만 짚는다. 실제 형식의 예시는 `app/static/dev/fake-events.json`(사례 1, 봉투 67개)이다.

## 1. 서빙

- `GET /` → `app/static/index.html`
- `/static/*` → `app/static/` (HTML이 `/static/style.css`, `/static/print.css`, `/static/js/app.js`, `/static/dev/fake-events.json`을 이 경로로 읽는다)
- 백엔드 없이 화면 확인: `/static/index.html?fake=1`

## 2. HTTP API

| 호출 | 화면이 보내는 것 | 화면이 읽는 것 |
|---|---|---|
| `GET /api/features` | — | `{image_input, audio_input, browser_recording, ask, reapproval}`(bool). 실패하면 모두 꺼짐으로 본다 |
| `GET /api/cases` | — | `[{case_id, title, summary, input_type}]` |
| `POST /api/runs` | JSON `{case_id, mode:"live"}` 또는 `{note, mode:"live", origin_run_id?}` / multipart `file`, `kind`(`image`·`audio`) | `{run_id}` |
| `POST /api/runs/{id}/approval` | `{request_id, approved, edited_sections}` | 본문은 읽지 않는다. 409면 "이미 처리된 승인 요청" |
| `POST /api/runs/{id}/ask` | `{question}` | `{ask_id}` |
| `POST /api/eval` | — | `{eval_id}` |

오류 응답은 `{"error": {"code", "message"}}`이고 화면은 `message`를 그대로 보여 준다. 본문이 없으면 상태 코드(404·409·429·501)별 기본 문구를 쓴다.

## 3. SSE

- `GET /api/runs/{id}/events`, `GET /api/eval/{id}/events`
- 각 이벤트는 **`event: {type}` 이름이 있어야 한다**(화면은 `onmessage`가 아니라 타입별 `addEventListener`로 받는다). `data`는 봉투 JSON 한 줄.
- 봉투: `{run_id, seq, ts, type, step, mode, trace_id, data}`. 화면은 `mode === "replay"`면 상단 "저장된 실행 재생" 배지를 켠다.
- `done`을 받으면 연결을 닫는다. `replaced`를 받으면 `data.run_id`의 SSE로 옮겨 계속 받는다.
- 화면이 구독하는 타입: 실행 `masked, transcribed, normalized, step_started, step_completed, step_failed, step_retry, token, tool_call, tool_result, usage, verified, draft, approval_required, finalized, approval_kept, error, replaced, queued, done` / 평가 `case_started, case_completed, eval_summary, error, done`

## 4. 이벤트별로 화면이 읽는 `data` 필드

| type | 필드 |
|---|---|
| `masked` | `before`, `after`(자리표시자 `[이름1]` 형식이면 강조 표시) |
| `transcribed` | `chars`, `uncertain`(목록), `speakers` |
| `normalized` | `clean_text`, `edits[{original, replacement, reason}]`, `uncertain[str]`, `skipped` |
| `step_started` | (봉투 `step`, `ts`) |
| `step_completed` | `ms` |
| `step_failed` | `code`, `message` |
| `step_retry` | `attempt`, `reason` |
| `token` | `text`, `ask_id?`(있으면 후속 질문 답변으로 붙인다) |
| `tool_call` | `tool`, `args.scheme_id`·`args.domain`·`args.decision_id` 중 하나 |
| `tool_result` | `decision_id` |
| `usage` | `input`, `output` |
| `verified` | `VerifiedResult` 그대로: `eligible/needs_check/ineligible[{decision{decision_id, scheme_id, domain, conditions[{id, met, used_values, note}], missing_fields, source_url}, explanation, follow_up_questions}]`, `removed[{scheme_id, reason}]`, `failed_domains`, `supplemented`, `audit_rule_skipped` |
| `draft` | `sections`(구획 ID 9개 → 본문) |
| `approval_required` | `request_id`, `scheme_ids`, `documents_summary` |
| `finalized` | `sections`, `finalized_at` |
| `approval_kept` | (없음) |
| `error` | `message` |
| `queued` | `position` |
| `replaced` | `run_id` |
| `done` | `status`(`expired`면 만료 안내) |
| `case_started` | `case_id` |
| `case_completed` | `CaseMetrics`: `case_id, replayed, recall, precision, grounding, pii_recall, pii_residual, autofilled_fields, manual_fields, supplemented, cer, total_ms, step_ms` |
| `eval_summary` | `EvalSummary`: `recall, precision, grounding, p50_ms, p95_ms, live_count, replay_count` |

- 단계 이름(`step`)은 AD-3 목록(`intake`, `profiler`, `match_living`…)이어야 타임라인 라벨이 붙는다. 매칭 3단계는 한 줄에 나란히 그린다.
- 문서 구획 ID는 `record.basic_info` … `referral.officer` 9개(`app/schemas.py`의 `SECTION_IDS`).
- 제도 이름은 화면이 `scheme_id`(13개, AD-3)로 직접 붙인다.

## 5. 연결 확인 순서

1. `/api/features`, `/api/cases`가 응답하면 첫 화면에 사례 목록이 나온다.
2. 사례 1을 눌러 SSE가 `approval_required`까지 오는지 본다(`fake-events.json`과 같은 흐름).
3. "의뢰서 확정" → 승인 → `finalized`가 오면 인쇄 화면이 나온다. 거부 → `approval_kept`.
4. "평가 실행" → 사례 5행과 요약이 채워진다.

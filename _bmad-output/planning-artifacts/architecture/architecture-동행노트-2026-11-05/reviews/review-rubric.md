# 리뷰 — ARCHITECTURE-SPINE.md (동행노트 백엔드)

- 검토자: 독립 아키텍처 리뷰(체크리스트 1–6 기준)
- 대상: `ARCHITECTURE-SPINE.md`(draft, 2026-11-05), 대조 문서: `TRD.md`(기준), `PRD.md`, `SPEC.md`, `.memlog.md`, `docs/reference/*.md`
- 검토 시각: 2026-11-05 13:2x KST (마감 16:20)

## 총평

스파인은 이 해커톤 규모에 비해 잘 만들어졌다. 공유 타입 단일 소유(AD-2), ID 계약(AD-3), 상태 쓰기 주체(AD-4), 단일 이벤트 경로(AD-8), 단일 에이전트 래퍼(AD-10), 허용 목록 단일 원본(AD-12)은 실제 분기 지점을 정확히 잡았다. 그러나 **문자 그대로 구현하면 필수 흐름(F5·F7·F8·F10)이 깨지는 규칙이 4개**(AD-6 숫자 검사 범위, AD-5 필수 필드, AD-1 `verify` 시그니처, 세션 색인 경쟁)이고, TRD의 "조용한 요구사항"(요청 제한·입력 길이·업로드 검사·heartbeat·`/readyz` 캐시·OCR/STT 숫자 보정)이 어느 모듈에 사는지 고정되지 않아 두 사람이 각자 구현하거나 아무도 구현하지 않을 위험이 크다. 또 `UiEvent.data`를 Deferred로 둔 것은 체크리스트 3을 정면으로 위반한다(UI·재생·평가가 모두 이 필드를 파싱한다).

**판정: 조건부 통과** — 아래 critical 1건, high 7건을 반영하면 병렬 구현 기반으로 쓸 수 있다.

| 심각도 | 건수 |
| --- | --- |
| critical | 1 |
| high | 7 |
| medium | 14 |
| low | 8 |

---

## Critical

### C1. AD-6 — "원문에 없는 숫자" 검사가 모든 제출 도구에 걸려 Documenter가 항상 거부된다

- **위치:** AD-6 Rule 다섯째 문장("검사 항목은 … 원문에 없는 숫자가 새로 생기지 않았는지다")
- **문제:** TRD 3.3·3.9는 새 숫자 거부를 `record_clean_note`에만 건다. 스파인은 검사 항목을 제출 도구 전체에 나열해, `submit_draft`·`submit_matches`·`record_case_profile`에도 적용된다고 읽힌다. Documenter 초안(의뢰서 "의뢰 제도와 근거 조건")은 판정 기록의 기준값(예: 생계급여 선정기준 820,556원, 기준 중위소득 32%)과 `monthly_income_krw` 같은 숫자를 반드시 담는데, 이는 메모 원문에 없다 → 매번 거부 → 1회 재요청 뒤 AD-10 실패 → 초안 없음 → F7·F8(필수) 불가. `record_case_profile`도 "삼십만 원"→300000 같은 정규화 숫자를 넣으므로 비교 규칙 없이는 거부된다.
- **수정(문구 제안):** AD-6 검사 항목 문장을 다음으로 교체:
  > 검사 항목은 도구별로 다르다. `submit_matches`: 인용한 `decision_id`·`condition_id`가 같은 실행의 판정 기록에 있는지(`verify.check_citations()` 사용). `submit_draft`: 구획 ID가 AD-3 목록에 있는지, 인용한 `decision_id`가 Verifier 통과 집합에 있는지. `record_clean_note`: 원문(가린 인식 텍스트, Intake 숫자 보정 후)에 없는 숫자(나이·금액·가구원 수)가 정리본에 새로 생기지 않았는지(`textnum.extract_numbers()`로 한글 수사까지 정규화해 비교). `record_case_profile`: Pydantic 검사만. 새 숫자 검사는 `record_clean_note`에만 적용한다.

---

## High

### H1. AD-1 — `verify(matches, decisions, audit, schemes)` 시그니처로는 규칙 6(빠진 제도 채우기)을 구현할 수 없다

- **위치:** AD-1 Rule, AD-4(`decisions` 쓰는 쪽 "Verifier 보완 채움"), Structural Seed 소스 트리 `verify.py`
- **문제:** 규칙 6은 건너뛴 제도를 `rules.evaluate(scheme, profile)`로 판정하고 그 판정을 `decision_id`와 함께 기록해야 한다. 그런데 ① 시그니처에 `profile`이 없고 ② `decision_id`는 `RunState.record_decision()`만 발급하므로(AD-3) 순수 함수가 발급할 수 없다. 담당자마다 "verify 안에서 레지스트리 호출(순수성 위반)", "실행기에서 따로 채움(규칙 6이 verify 밖으로 샘)", "임시 ID 발급(AD-3 위반)"으로 갈라진다.
- **수정:** AD-1 Rule의 함수 부분을 다음으로 교체:
  > Verifier 대조는 2단계 순수 함수로 둔다. ① `verify.uncovered(decisions, schemes, domains) -> list[scheme_id]`. 실행기는 이 목록마다 `rules.evaluate(scheme, run.profile)`를 부르고 `run.record_decision(..., origin="verifier_fill")`로 기록한다. ② `verify.verify(matches, decisions, audit, schemes) -> VerifiedResult`가 규칙 1–5·7을 적용한다(`origin="verifier_fill"` 판정은 규칙 7 대상 아님). 실행기는 ①→기록→②를 이 순서로만 호출한다.

### H2. AD-5 — "필수 필드 6개 중 하나라도 `None`이면 `unknown`"은 제도별 `required_fields`와 모순되어 재현율·정밀도를 깬다

- **위치:** AD-5 Rule 마지막 두 문장
- **문제:** TRD 4.1의 6개는 "규칙 함수가 읽는 필드의 합집합"이고, TRD 4.2는 제도마다 `required_fields`를 둔다. 스파인 문구대로면 `housing`이 비면 기초연금·응급안전안심서비스까지 전부 `unknown`이 된다. `rules.py` 작성자와 `eval_cases.json`의 `expected_unknown` 작성자가 서로 다른 해석으로 정답을 만들게 된다. 또 "알려진 값만으로 이미 탈락(예: 나이 < 65)"인 경우를 `ineligible`로 낼지도 정해지지 않았다.
- **수정:** AD-5 마지막 두 문장을 교체:
  > 규칙 함수가 읽을 수 있는 필드는 TRD 4.1의 6개로 한정하고, 제도마다 읽는 필드는 `schemes.json`의 `required_fields`(6개의 부분집합)가 원본이다. 알려진 값만으로 조건 하나라도 불충족이면 `ineligible`, 그렇지 않고 그 제도의 `required_fields` 중 `None`이 있으면 `unknown`과 누락 필드 목록, 나머지는 `eligible`이다. `eval_cases.json`의 기대 집합도 이 규칙으로 만든다.

### H3. AD-4 / AD-12 — Copilot `sessionId → run` 색인이 첫 도구 호출보다 늦게 등록될 수 있다(권한 거부·감사 누락)

- **위치:** AD-4("Copilot `sessionId`에서 실행을 찾는 색인도 레지스트리가 관리"), AD-12("공통 `on_permission_request`"), TRD 3.6 마지막 훅 문장
- **문제:** MAF는 첫 `agent.run()` 안에서 `create_session`을 호출해 `service_session_id`를 정한다(`docs/reference/agent-framework.md` 104행). 실행기(`call_agent`)가 이 ID를 알고 색인에 넣기 전에 Copilot 런타임이 권한 요청·`on_post_tool_use` 훅을 보낼 수 있다. ① 권한 처리기가 색인으로 단계를 찾으면 첫 도구 호출이 거부되어 단계 전체가 실패한다. ② 훅이 감사 기록을 일부만 남기면 감사 기록이 "비어 있지 않으므로" 규칙 7이 적용되어 **정상 추천이 제거**된다(재현율 하락, F5 화면에 거짓 "검증에서 제외됨"). 전부 비는 경우보다 일부 비는 경우가 더 나쁘다.
- **수정:** AD-12에 추가:
  > 권한 처리기는 에이전트마다 `make_permission_handler(step)` 클로저로 만들고 `TOOL_ALLOWLIST[step]`만 본다. 권한 처리기는 세션 색인을 조회하지 않는다.

  AD-3의 `decision_id` 문장을 교체:
  > `decision_id`는 `RunState.record_decision()`만 발급하며 형식은 `{run_id}:{n}`(n은 실행 안 1부터 증가)이다. 훅은 도구 결과의 `decision_id` 접두로 실행을 찾으므로 세션 색인 없이 감사 기록을 남긴다. 세션 색인은 30분 TTL 삭제와 `on_error_occurred` 기록에만 쓴다.

  AD-4에 추가: "`call_agent`는 `AgentSession.service_session_id`가 생기는 즉시 `RunRegistry.bind_session(run_id, step, session_id)`를 부른다. 색인에 없는 `sessionId`의 훅 입력은 버리지 않고 레지스트리가 보관했다가 바인딩 때 반영한다."

### H4. Deferred — "`UiEvent.data` 세부 필드는 `schemas.py`를 처음 만드는 사람이 정한다"는 체크리스트 3 위반

- **위치:** Deferred 마지막 행
- **문제:** `UiEvent.data`는 UI(app.js), 재생(AD-9: 재생 확정에 `draft`·`verified` 이벤트에서 초안과 통과 집합을 복원해야 함), 평가(F10: 단계 시간·판정 결과 집계), 매퍼(`events.py`) 네 곳이 파싱한다. "먼저 만드는 사람" 규칙은 병렬 작업에서 경쟁이며, 재생 파일은 배포 전 실제 실행으로 만들어지므로(F11) 필드가 나중에 바뀌면 재생 파일을 다시 만들어야 한다.
- **수정:** Deferred에서 이 행을 지우고 Consistency Conventions에 "이벤트 데이터" 행 추가:
  > 이벤트 종류별 `data`는 `schemas.py`의 Pydantic 모델이 원본이다: `masked{before,after,spans[]}`, `transcribed{chars,uncertain[],speakers,ms}`, `normalized{clean_text,edits[],uncertain[],skipped}`, `step_started/step_completed{step,ms?}`, `step_failed{code,message,retryable}`, `token{text}`, `tool_call{tool,args}`, `tool_result{tool,decision_id?}`, `usage{input,output}`, `verified: VerifiedResult`, `draft: DraftDocuments`, `approval_required{request_id,scheme_ids,documents_summary}`, `finalized: FinalDocuments`, `error{code,message}`, `done{status}`. 이 목록을 바꾸면 `data/replays/`를 다시 만든다.

### H5. AD-8 / AD-10 / Conventions — 평가 SSE(`/api/eval/{id}/events`)의 상태·로그·이벤트 이름이 없다

- **위치:** AD-8, AD-4, Conventions "이름" 행("SSE 이벤트·`UiEvent.type`은 TRD 표 5 + `step_failed`")
- **문제:** TRD 5는 평가 스트림에 `case_started`, `case_completed`, `eval_summary`, `heartbeat`를 정의하지만 스파인의 이름 규칙은 "표 5 + `step_failed`"로 닫혀 있어 평가 이벤트를 금지한다. `eval_id`의 상태 소유자, `EventLog` 사용 여부, TTL, 봉투의 `run_id` 자리가 정해지지 않았다. F10은 필수다.
- **수정:** AD-8 끝에 추가:
  > 평가도 같은 경로를 쓴다. `RunRegistry`가 `EvalState(eval_id, EventLog)`를 만들고 30분 TTL로 지운다. 평가 이벤트 `case_started`, `case_completed`, `eval_summary`는 `RunService.start_eval`만 `EventLog.append()`로 쌓는다. 봉투의 `run_id` 자리에는 `eval_id`를 넣는다.

  Conventions "이름" 행을 "TRD 표 5 + `step_failed` + 평가 이벤트 3종"으로 고친다.

### H6. AD-7 / AD-4 / AD-12 — `/ask`가 Documenter 세션을 재사용하면 `submit_draft`로 승인 대기 중인 초안을 덮어쓸 수 있고, `/ask` 응답 경로도 미정

- **위치:** AD-7("워크플로 밖 에이전트 호출은 `/ask` 하나"), AD-4("`draft`는 `submit_draft`"), AD-12 허용 목록(documenter: `lookup_decision`, `submit_draft`), AD-8("SSE 응답은 `EventLog`를 읽기만")
- **문제:** ① `/ask`는 같은 Documenter 에이전트·세션을 쓰므로 `submit_draft`가 노출된다. 지시문이 "제출 도구를 써라"(Conventions 프롬프트 행)이므로 모델이 후속 질문에 `submit_draft`를 다시 부르기 쉽고, 담당자가 승인 창에서 본 초안과 확정 템플릿이 쓰는 `run.draft`가 달라진다(F8 신뢰 위반). ② TRD는 `/ask`가 자체 SSE 응답이라 하고, AD-8은 SSE는 `EventLog`만 읽는다고 해 `main.py`와 UI 구현이 갈라진다. ③ 어떤 실행 상태에서 `/ask`를 허용하는지 없다.
- **수정:** AD-4에 추가: "`draft`는 한 번만 쓴다. `submit_draft`는 `run.status == running`이고 `draft is None`일 때만 받고, 아니면 거절 문자열을 돌려준다." AD-7에 추가:
  > `/ask`는 `awaiting_approval`·`finalized` 상태에서만 받는다(그 밖은 409). 답변 이벤트(`token`, `tool_call`, `tool_result`, `done`)는 `step="ask"`로 같은 실행의 `EventLog`에 쌓고, `POST /ask`는 `202 {"seq_from"}`만 돌려준다. UI는 기존 `/events` 연결로 받는다.

  (대안: TRD대로 `/ask`를 자체 SSE로 두려면 AD-8에 "`/ask` 응답만 예외"라고 명시.)

### H7. 조용한 요구사항의 소속 모듈이 없다 — 요청 제한·입력 길이·업로드 검사·heartbeat·`/readyz` 캐시

- **위치:** 스파인 전반(AD-10·AD-14·Conventions에 일부 흔적만), 체크리스트 4
- **문제:** 아래 TRD 요구가 스파인에 없거나 위치가 없다. 위치가 없으면 `main.py`와 `service.py` 담당이 둘 다 구현(이중 카운트)하거나 둘 다 안 한다.

  | TRD 요구 | 스파인 상태 | 갈라지는 방식 |
  | --- | --- | --- |
  | IP별 실행 분당 5회, `X-Forwarded-For` 첫 값(8절) | AD-14 "카운터 메모리"만 | 어떤 경로를 세는지(`/runs`만? `/ask`·`/approval` 포함?), 어디서 세는지 |
  | `/api/eval` 전역 분당 1회(8절) | AD-10 동시 1만 | 분당 제한 누락 |
  | 입력 4,000자(8절) | 없음 | 메모만? `/ask` 질문·재실행 정리본·OCR/STT 인식 텍스트 포함? 400 vs `step_failed` |
  | 업로드 5MB·10MB·2분, 시그니처 검사(8절) | 없음 | `main.py`(400) vs `ingest.py`(워크플로 안 `step_failed`) |
  | heartbeat 15초(5·7절) | 없음 | heartbeat를 `EventLog`에 넣으면 `seq`가 늘고 재생 파일이 오염됨 |
  | `/readyz` 시작 시 1회 캐시(2·5·6·3.9절) | 없음 | `agents.py` vs `main.py`가 각자 확인, 요청마다 모델 호출 위험 |

- **수정:** Consistency Conventions에 "입구 검사" 행 추가:
  > 입구 검사는 `main.py`가 `RunService` 호출 전에 모두 끝내고 실패는 400/429로 돌려준다(워크플로 안 `step_failed`로 보내지 않는다). 검사 함수는 L1 `app/limits.py`(순수): `check_text(s, max=4000)`, `sniff_media(bytes) -> "jpeg"|"png"|"wav"|"mp3"|"webm"|None`, `check_media(kind, bytes)`(사진 5MB, 음성 10MB·2분). 요청 제한은 `main.py`의 의존성 하나가 `X-Forwarded-For` 첫 값 기준으로 `POST /api/runs`만 분당 5회, `POST /api/eval`은 전역 분당 1회로 센다. 4,000자는 메모·`/ask` 질문·재실행 정리본에 적용하고 인식 텍스트에는 적용하지 않는다.

  AD-8에 추가: "`heartbeat`는 `EventLog`에 쌓지 않는다. SSE 응답이 15초마다 `seq` 없는 `event: heartbeat`를 직접 쓴다. `done`은 `RunService`가 실행이 `awaiting_approval`·`finalized`·`failed`에 들어갈 때 `EventLog`에 쌓는다." Structural Seed에 추가: "`main.py` lifespan이 `service.startup()`을 부르고, 이 함수가 `CopilotClient` 시작·`get_auth_status()`·`list_models()`·AI Services 토큰 발급 결과를 `Readiness`로 한 번 만들어 둔다. `/readyz`는 이 값만 돌려준다."

---

## Medium

### M1. OCR/STT 숫자 보정과 한글 수사 정규화의 소속이 없다 (체크리스트 4)

- **위치:** AD-11, 소스 트리 `masking.py`
- **문제:** TRD 3.9는 OCR 텍스트에서 숫자 사이 O·o·l→숫자, 하이픈 없는 10~11자리 전화번호; TRD 8은 STT의 한글 숫자 전화번호("공일공")를 요구한다. TRD 3.3은 `record_clean_note`에서 "삼십만 원"→300000 정규화 비교를 요구한다. 한글 수사 파서가 `masking.py`와 `tools.py`에 따로 생기고, 보정이 `ingest.py`·Intake·`masking.py` 중 어디서 일어날지 갈라진다. 보정 위치가 다르면 `record_clean_note`의 "원문" 기준도 달라진다.
- **수정:** L1에 `app/textnum.py` 추가, AD-11에 문장 추가:
  > 숫자 보정·정규화는 L1 `textnum.py` 하나에 둔다: `fix_ocr_digits(text)`, `parse_korean_numbers(text) -> list[int]`. `masking.mask(text, source: Literal["text","image","audio"])`가 `source=="image"`면 `fix_ocr_digits`를 먼저 적용하고, 전화번호 규칙은 한글 숫자 표기도 찾는다. `record_clean_note`의 "원문"은 `mask()`가 돌려준 가린 텍스트다.

### M2. AD-10 — 단계 시간 기록의 출처가 둘(실행기, `StepTimingMiddleware`)이고 코드 단계는 미들웨어가 못 잰다

- **위치:** AD-4("`sessions`·`timings`는 실행기와 `StepTimingMiddleware`가 쓴다"), Capability Map "관측"
- **문제:** "필드마다 쓰는 쪽은 하나"라는 같은 AD 안에서 두 쓰기 주체를 둔다. F10은 가리기(Intake)·검증(Verifier) 같은 코드 단계의 시간도 요구하는데 `AgentMiddleware`는 에이전트 실행에서만 돈다.
- **수정:** AD-4 해당 부분 교체:
  > `sessions`는 `call_agent`만 쓴다. 단계 소요 시간은 `events.map_workflow_event()`가 `executor_invoked`·`executor_completed` 짝으로 계산해 `step_completed.data.ms`에 싣고 `run.timings[step]`에 쓴다(유일한 쓰기 주체). `StepTimingMiddleware`는 토큰 사용량(`run.usage[step]`)과 span 속성만 쓴다.

### M3. AD-4 — 쓰기 주체 목록이 불완전하다

- **위치:** AD-4 Rule
- **문제:** `status`, `verified`(VerifiedResult; AD-13 부분집합 검사에 필요), `final_documents`, `pending_request_id`(AD-13 409 판정에 필요), `workflow` 인스턴스, `transcript`(OCR/STT 결과), `errors`(`on_error_occurred` 기록), `clean_note_skipped`가 빠졌다. 목록에 없는 필드는 아무나 쓰게 된다.
- **수정:** AD-4에 추가:
  > `status`·`pending_request_id`·`workflow`는 `RunService`만(`pending_request_id`는 `request_info` 이벤트를 받을 때), `transcript`는 `ocr`/`stt` 실행기, `verified`는 `verifier` 실행기, `final_documents`는 `documents.finalize()`를 부른 쪽(AD-13), `errors`는 `on_error_occurred` 훅만 쓴다. 이 목록에 없는 필드를 추가하면 쓰기 주체를 함께 적는다.

### M4. AD-9 ↔ AD-13 — "확정 문서는 `@response_handler`만 만든다"와 "재생의 승인도 같은 템플릿으로 처리"가 충돌

- **위치:** AD-9 마지막 문장, AD-13 첫 문장
- **문제:** 재생에는 워크플로 인스턴스·`request_info`가 없으므로 `@response_handler`가 없다. 또 재생 실행에는 `draft`·`verified`·`pending_request_id`가 없어 AD-13의 409·부분집합 검사를 할 수 없다. 템플릿 함수의 위치도 없다.
- **수정:** AD-13 첫 두 문장 교체:
  > 확정 문서는 L1 순수 함수 `documents.finalize(draft, edited_sections, approved_scheme_ids, verified_ids) -> FinalDocuments`만 만든다. 호출자는 실시간에서 `referral_gate`의 `@response_handler`, 재생에서 `RunService.respond` 둘뿐이다.

  AD-9에 추가: "재생 시작 때 `RunService`는 재생 파일의 `verified`·`draft`·`approval_required` 이벤트 데이터로 `run.verified`·`run.draft`·`run.pending_request_id`를 채운다."

### M5. AD-10 ↔ TRD 3.1 — 데모 사례의 Profiler 실패 처리 모순

- **위치:** AD-10("가리기 잔존·Profiler 실패는 실행을 `failed`로 끝낸다"), 상태도(`running --> replaying: rate_limit · 데모 사례`)
- **문제:** TRD 3.1은 "데모 사례는 저장된 실행 재생으로 바꾸고, 직접 입력은 오류와 재시도 버튼"이라 한다. 스파인은 재생 전환을 `rate_limit`에만 건다. 심사 중 데모 사례가 `failed`로 끝나면 F1·F11 시연이 실패한다.
- **수정:** AD-10 해당 문장 교체:
  > 가리기 잔존은 항상 `failed`. Profiler 실패와 `rate_limit`은 데모 사례면 `RunService`가 재생으로 전환하고, 직접 입력이면 `failed`로 끝낸다.

  상태도 전이 라벨을 `running --> replaying: 데모 사례의 rate_limit·Profiler 실패`로 고친다.

### M6. AD-10 — "예외를 던지지 않고 실행을 `failed`로 끝낸다"의 메커니즘이 없다; `error`와 `step_failed`의 구분도 없다

- **위치:** AD-10, Conventions "이름"·"오류 형식"
- **문제:** 실행기가 예외 없이 실행을 끝내는 방법(다음 메시지를 보내지 않음 → 워크플로 idle)과 `RunService`가 이를 어떻게 `failed`로 판정하는지가 없다. 표 5의 `error`(워크플로 failed, 단계 실패 결과)와 새 `step_failed`가 겹쳐 UI가 무엇을 종료 신호로 볼지 갈라진다.
- **수정:** AD-10에 추가:
  > `step_failed`는 실행이 계속되는 단계 실패(매칭 1개, 정리 생략)에만 쓴다. 실행을 끝내는 실패는 실행기가 `UiEvent(error, step, {code,message})`를 내보내고 다음 메시지를 보내지 않는다. `RunService`는 워크플로가 `request_info` 없이 끝났거나 `error` 이벤트가 있으면 상태를 `failed`로 바꾸고 `done{status:"failed"}`를 쌓는다.

### M7. AD-6 / TRD 3.2 — 매칭 → Verifier fan-in 메시지 타입이 `MatchResult`인지 `MatchSubmission`인지 불명

- **위치:** AD-6, ER 다이어그램, TRD 3.2·3.1
- **문제:** TRD는 실행기 메시지 `MatchResult(domain, status="failed", error)`, 스파인은 도구 인자 `MatchSubmission`을 도입했다. 실패 분기 표현과 Verifier 핸들러 타입(`list[MatchResult]`)이 갈라진다.
- **수정:** AD-6에 추가:
  > fan-in 메시지는 `MatchResult(domain, status: "ok"|"failed", submission: MatchSubmission | None, error: str | None)`다. 매칭 실행기는 `run.match_submissions[domain]`을 읽어 이 메시지를 만든다. Verifier 핸들러는 `list[MatchResult]`를 받는다.

### M8. AD-6 — `submit_matches` 사전 검사와 `verify` 규칙 2–3이 이중 구현된다

- **위치:** AD-6, AD-1
- **문제:** 같은 인용 검사가 `tools.py`와 `verify.py`에 따로 생기면 기준이 어긋날 수 있다. 또 도구 단계에서 모두 걸러지면 F5의 "제거 사실 표시"가 시연되지 않는다(사례 5 인젝션에서 보여 줘야 함).
- **수정:** AD-6에 "인용 검사는 `verify.check_citations(rec, decisions) -> str | None` 하나를 `submit_matches`와 `verify()`가 함께 쓴다"를 추가. 또 제출 거부 재시도 횟수 상한을 명시: "제출 도구 거부는 단계당 2회까지, 그 뒤에는 마지막 제출을 받아 Verifier가 제거하게 둔다(`record_clean_note`는 TRD 3.9대로 1회 뒤 정리 생략)."

### M9. Conventions "설정" — 환경변수 이름이 계약으로 고정되지 않았다 (Bicep ↔ `config.py`)

- **위치:** Conventions "설정" 행 [ASSUMPTION]
- **문제:** `infra/main.bicep`(배포 담당)과 `app/config.py`(앱 담당)가 같은 이름을 써야 하는데 이름이 없다. BUILD_PLAN에는 `AZURE_AI_ENDPOINT`, `AZURE_CLIENT_ID`가 나온다. `DefaultAzureCredential`의 사용자 할당 ID는 `AZURE_CLIENT_ID`가 없으면 실패한다.
- **수정:** "설정" 행 교체:
  > 환경변수는 `app/config.py`의 `Settings`에서만 읽는다. 이름: `COPILOT_GITHUB_TOKEN`(secretRef), `AZURE_CLIENT_ID`, `AZURE_AI_ENDPOINT`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `COPILOT_MODEL`, `REASONING_PROFILER`·`REASONING_MATCH`·`REASONING_DOCUMENTER`, `ENABLE_AI_SERVICES`. SDK가 직접 읽는 `COPILOT_CLI_EXTRACT_DIR`·`COPILOT_SKIP_CLI_DOWNLOAD`·`HOME`은 Dockerfile에서만 정한다. 제한값(4,000자, 5회/분 등)은 상수로 `config.py`에 둔다.

### M10. 층 표 — 문자 그대로면 `main.py`가 `schemas.py`·`config.py`를 import할 수 없고, MAF 허용 층이 불명확

- **위치:** Design Paradigm 층 표, "표에 없는 것은 금지"
- **문제:** L7 허용이 "L6, runs, events"뿐이라 FastAPI 요청 모델(AD-2상 `schemas.py`)을 쓸 수 없다. 외부 의존 허용이 L2(MAF 이벤트)·L4(Copilot·Azure SDK)에만 적혀 있어 L3 `tools.py`(`@tool`, `FunctionInvocationContext`), L4 `context.py`(`ContextProvider`), L5 `workflow.py`(`WorkflowBuilder`)의 MAF 사용이 금지로 읽힌다. `telemetry.py`(L3)는 lifespan에서 `main.py`가 불러야 한다.
- **수정:** 표 아래 문장 교체:
  > L0(`schemas`, `config`)은 모든 층이 import할 수 있다. MAF(`agent_framework`)는 L2 이상, Copilot SDK·Azure SDK는 L4 이상에서만 import한다. `main.py`는 L0, L6, `runs`(조회), `events`(읽기)만 import하고 시작·종료는 `service.startup()/shutdown()`을 통해서만 한다(텔레메트리 설정 포함). 이 밖의 역방향·건너뛰기 import는 금지한다.

### M11. AD-3 — `domain` 값과 `input_router` 단계 ID가 빠졌다

- **위치:** AD-3
- **문제:** `search_schemes(domain: Literal["living","health","care"])`(TRD 3.3)와 `schemes.json`의 `domain` 필드가 같은 값이어야 하는데 고정되지 않았다(데이터 작성자가 "생계·주거"로 쓰기 쉽다). 실행기 ID 목록에 InputRouter가 없어 `executor_invoked`가 매핑되지 않는 단계가 생긴다. 13개 `scheme_id`도 열거되지 않아 `rules.py`·`schemes.json`·`eval_cases.json`·STT 구문 목록을 병렬로 만들 수 없다.
- **수정:** AD-3에 추가:
  > `domain`은 `living`·`health`·`care`이고 `schemes.json`·`search_schemes`·`MatchResult`·실행기 ID 접미사가 같은 값을 쓴다. 실행기 ID에 `input_router`를 더한다. 13개 `scheme_id`: `livelihood_benefit`, `housing_benefit`, `emergency_livelihood`, `energy_voucher`, `medical_benefit`, `copay_reduction`, `disability_pension`, `health_checkup_visit`, `basic_pension`, `elderly_care_service`, `emergency_safety_service`, `senior_job_public`, `lonely_death_prevention`.
  (이름은 예시. 핵심은 스파인에 목록을 박아 두는 것.)

### M12. 상태도 — 축소 경로와 재생 전환이 표현되지 않는다

- **위치:** Structural Seed "실행 상태", AD-13, AD-9
- **문제:** ① 기능 축소 (4) "거부 뒤 재승인"을 자르면 TRD는 "거부 시 초안으로 끝냄"인데 AD-13·상태도는 `awaiting_approval`로만 돌아간다(종료 상태 없음). ② `running → replaying` 때 이미 쌓인 실시간 이벤트와 재생 이벤트가 같은 `EventLog`에 이어져 UI 타임라인이 중복된다. 진행 중 워크플로 태스크 취소 규칙도 없다. ③ `queued`의 대기열 순서 이벤트가 표 5에 없다.
- **수정:** 상태도에 `awaiting_approval --> drafted: 거부(재승인 축소 시)`, `drafted --> [*]` 추가. AD-9에 추가: "실시간 → 재생 전환 때 `RunService`는 워크플로 태스크를 취소하고 `UiEvent(mode_switched, data={reason})`를 쌓는다. UI는 이 이벤트를 받으면 타임라인을 비우고 재생 배지를 단다." Conventions 이름에 `mode_switched`, `queued{position}` 추가.

### M13. AD-10 — 평가 사례가 실시간 세마포어(4)를 쓰는지 불명

- **위치:** AD-10("동시 실행 제한(실시간 4, 평가 전역 1)")
- **문제:** TRD 7은 평가가 사례 2건씩 동시 처리한다. 평가 사례가 실시간 세마포어를 같이 쓰는지에 따라 심사 중 실시간 실행이 막히거나 프로세스가 6건 동시로 과부하된다. 평가 6분 상한·실패 사례 재생 전환·평균 제외도 스파인에 없다(`service.py` 내부라 해도 지표 정의는 UI와 공유).
- **수정:** AD-10에 추가: "평가 사례는 실시간 세마포어와 별도인 평가 세마포어(2)로 돌고, 평가 중 실시간 세마포어는 2로 줄인다. 평가 전체 상한 6분, 실패·상한 초과 사례는 재생으로 처리해 `case_completed.data.mode="replay"`로 표시하고 지표 평균에서 뺀다."

### M14. AD-14 ↔ 실제 동작 — "디스크를 쓰지 않는다"는 Copilot 런타임의 세션 저장과 모순

- **위치:** AD-14 둘째 문장
- **문제:** Copilot SDK 세션은 `~/.copilot/session-state/{sessionId}/`에 대화 이력(가린 메모 포함)을 디스크로 남긴다(`docs/reference/copilot-sdk.md` 95행). 심사 문서·RAI 주장과 실제가 다르다.
- **수정:** AD-14 둘째 문장 교체:
  > 상담 데이터는 앱이 디스크·DB·Blob에 쓰지 않는다. 예외는 Copilot 런타임의 세션 상태(`HOME/.copilot/session-state/`, 가린 텍스트만 포함)이며, `RunRegistry`가 30분 TTL 때 `delete_session`으로 지운다. 컨테이너 디스크는 임시이고 재시작 때 사라진다.

---

## Low

### L1. AD-15 ↔ TRD 6 대체안
TRD 6은 "마감 90분 전까지 Key Vault 참조가 안 되면 Container Apps secret으로 토큰을 넣고 README에 사유"를 허용한다. AD-15는 "Key Vault에만"이라 대체안을 금지한다. **수정:** AD-15에 "단, TRD 6 대체안(14:50까지 Key Vault 참조 실패 시 Container Apps secret, README에 사유)은 허용한다"를 추가.

### L2. TRD 3.4 규칙 7 건너뜀 표시가 계약에 없다
`VerifiedResult`에 건너뜀 표시가 없으면 UI·평가가 "규칙 7 적용됨"으로 오해한다. **수정:** AD-1에 "`VerifiedResult.audit_rule_skipped: bool`을 두고, 감사 기록이 비면 True로 하고 span 속성 `app.verify.rule7_skipped`를 단다"를 추가. 규칙 7을 실행 단위가 아니라 매칭 분야 단위 감사 기록과 대조할지도 명시(권장: 분야 단위, 다른 분야 에이전트가 받은 판정 인용 방지).

### L3. `on_error_occurred`와 `call_agent`의 오류 분류 출처 이중화
TRD 3.6은 훅 기록으로 재생 전환을 판단, AD-10은 `call_agent` 분류로 판단. 훅을 자르면(축소 6) 동작이 달라진다. **수정:** AD-10에 "재생 전환 판단은 `call_agent`의 분류만 쓴다. `on_error_occurred` 기록은 관측용이다"를 추가.

### L4. 확정 문서의 가명 복원(`pii_map`) 여부 미정
인쇄용 확정 문서에 원래 이름을 되돌릴지(템플릿)와 UI 표시가 갈라질 수 있다. **수정:** Open question으로 추가하거나 AD-13에 "확정 문서도 가린 값 그대로 둔다. `pii_map`은 `masked` 이벤트의 전/후 표시에만 쓴다"를 고정.

### L5. AD-7에 [ADOPTED] 표시 누락
다른 AD와 상태 표기가 다르다. memlog상 채택된 결정이다. **수정:** 제목을 `### AD-7 — MAF가 유일한 오케스트레이터 [ADOPTED]`로.

### L6. 소스 트리 ↔ TRD 11 — OCR·STT 실행기 위치
TRD 11은 `ingest.py`에 "OCR·STT 실행기"를 두고, 스파인은 실행기를 `workflow.py`에, `ingest.py`는 L4 Azure 호출로 둔다. **수정:** 소스 트리 주석을 `ingest.py # Azure OCR·STT 호출 함수(실행기 아님). OcrExecutor·SttExecutor는 workflow.py`로.

### L7. 운영 — 배포 중 진행 실행 유실, 리비전 모드
ACA가 다중 리비전 모드거나 배포 중 새 리비전이 뜨면 메모리 상태가 사라지고 일시적으로 프로세스가 둘이 된다. **수정:** AD-14에 "Container App은 단일 리비전 모드로 둔다. 재배포는 진행 중 실행을 버리며 최종 제출(16:20) 뒤에는 배포하지 않는다"를 추가. 또한 프로브(`/healthz` liveness, `/readyz` readiness)를 배포 다이어그램에 적는다.

### L8. Stack — `pydantic` 미고정, SPEC 축소 순서 불일치
AD-2의 핵심인 Pydantic 버전이 표에 없다(MAF가 끌어오는 버전에 의존). SPEC 10의 축소 순서도 스파인·TRD와 다르다. **수정:** Stack 표에 `pydantic`(MAF 1.24.0 호환 버전, 최소 샘플에서 `pip freeze`로 확인) 행 추가. "기능 축소 순서" 행 끝에 "SPEC 10도 같이 고친다"를 추가.

---

## 체크리스트별 판정

| # | 항목 | 판정 | 근거 |
| --- | --- | --- | --- |
| 1 | 실제 분기 지점을 빠짐없이 고정 | 부분 | 핵심 분기는 잡음. 입구 검사 위치(H7), 평가 상태(H5), 이벤트 데이터(H4), 숫자 정규화(M1), 환경변수 이름(M9), domain·scheme_id 목록(M11) 누락 |
| 2 | 각 Rule이 강제 가능하고 분기를 실제로 막음 | 부분 | AD-6 검사 범위(C1), AD-5(H2), AD-1 시그니처(H1), AD-4 "쓰기 주체 하나" 자기모순(M2·M3), 층 표(M10)가 문자 그대로 강제 불가·오동작 |
| 3 | Deferred 항목이 분기를 허용하지 않음 | 불합격 | `UiEvent.data`(H4). 나머지 Deferred(인증, 영속 저장, CI/CD, 스테이징, 소득 계산, 프롬프트 문구)는 안전 |
| 4 | 스펙 기능·조용한 요구사항 반영 | 부분 | F1–F14 매핑 있음. 요청 제한·eval 분당 1·4,000자·업로드 검사·heartbeat·`/readyz` 캐시·숫자 보정 누락(H7·M1). Last-Event-ID·30분 TTL은 반영. 새 숫자 거부는 범위 오류(C1). 규칙 7 건너뜀은 표시 계약 누락(L2) |
| 5 | 구조 차원 결정·연기·질문 | 대체로 통과 | 배포·환경(prod 1 + 로컬)·인프라(azd+Bicep)·비밀·관측 결정됨. 리비전 모드·프로브(L7), Bicep 매개변수 `enableAiServices`·AI Services 지역은 TRD에 있으나 스파인에 언급 없음(허용 가능). Open questions 절이 아예 없다 → L4·리비전 모드 등을 담을 "Open Questions" 절 추가 권장 |
| 6 | TRD와의 모순 명시 | 부분 | 아래 표. 스파인은 "충돌하면 AD를 TRD에 반영"이라고만 하고 개정 목록이 없다 |

## 스파인 ↔ TRD 모순 목록(빌더 혼동 지점)

스파인 서두 "TRD와 충돌하면 이 문서의 AD를 TRD에 반영한다"만으로는 빌더가 어느 쪽을 따를지 모른다. 스파인에 "TRD 개정 목록" 절을 두고 아래를 명시할 것을 권한다.

| # | TRD | 스파인 | 처리 |
| --- | --- | --- | --- |
| 1 | 3.1·3.3·3.6: 매칭 도구 `search_schemes`·`check_eligibility`, Documenter `lookup_decision`만. 도구 5개 | AD-6·AD-12: `submit_matches`·`submit_draft` 추가, 도구 7개 | 의도된 개정. 명시 필요 |
| 2 | 3.2: 실행기가 `agent.run(...)` 직접 호출 | AD-10: `agents.call_agent()`만 | 의도된 개정. 명시 필요 |
| 3 | 3.2: fan-in `MatchResult` | AD-6·ER: `MatchSubmission` | 불명확 → M7 |
| 4 | 3.3·3.9: 새 숫자 거부는 `record_clean_note`만 | AD-6: 모든 제출 도구 | 스파인 오류 → C1 |
| 5 | 3.1: 데모 사례 Profiler 실패 → 재생 | AD-10: `failed` | 모순 → M5 |
| 6 | 4.2: 제도별 `required_fields` | AD-5: 6개 중 하나라도 없으면 `unknown` | 스파인 오류 → H2 |
| 7 | 3.6: `on_error_occurred`로 재생 전환 판단 | AD-10: `call_agent` 분류 | 이중 출처 → L3 |
| 8 | 5: `/ask`는 자체 SSE 응답 | AD-8: SSE는 `EventLog`만 읽음 | 모순 → H6 |
| 9 | 5: 평가 이벤트 `case_*`·`eval_summary` | Conventions: 표 5 + `step_failed`만 | 모순 → H5 |
| 10 | 6 대체안: Container Apps secret 허용 | AD-15: Key Vault에만 | 모순 → L1 |
| 11 | 8 "저장 없음" + Copilot 세션 디스크 상태 | AD-14: 디스크 안 씀 | 사실과 모순 → M14 |
| 12 | 10: 축소 순서 (1)가용성 (2)훅 (3)Provider (4)재승인 (5)F9 (6)녹음 (7)화자분리 (8)병렬 (9)F13 (10)F12·F14 | Conventions: 녹음·화자분리를 앞당김 | 의도된 개정, 이미 명시됨(좋음). SPEC 10도 다름 → L8 |
| 13 | 11: `main.py`에 실행 상태·승인 응답, `ingest.py`에 OCR·STT 실행기 | `runs.py`·`service.py` 분리, 실행기는 `workflow.py` | 의도된 개정. `ingest.py` 주석만 정리 → L6 |
| 14 | 3.5-4: 응답 처리기 안 재요청 실패 시 Documenter→ReferralGate 간선 대체안 | AD-13: 언급 없음 | AD-13에 "대체안 사용 시에도 새 `request_id`를 `RunService`가 `pending_request_id`로 기록" 추가 권장 |

## 잘된 점(유지)

- AD-2·AD-3·AD-12는 짧고 기계적으로 검사 가능하다(grep·테스트로 강제 가능).
- AD-4의 "상태 변경 메서드는 동기 함수" 규칙은 병렬 fan-out의 경쟁을 싸게 막는 좋은 결정이다.
- AD-8·AD-9로 재생을 "기록된 EventLog"로 정의한 것은 UI 분기를 없애고 F11을 F10과 일관되게 만든다.
- AD-6이 TRD 3.7(`response_format` 미지원)과 3.1 Documenter·매칭의 자유 텍스트 파싱 모순을 해소했다.
- 운영 범위(단일 복제본, 단일 환경, 관리 ID, Key Vault, 텔레메트리 민감 데이터 끔)가 명확하다.

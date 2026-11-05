# SPEC — 동행노트

`PRD.md`와 `TRD.md`를 요약한 구현 명세다. 기준 문서는 PRD/TRD이며, 충돌하면 그쪽을 따른다.

## 1. 서비스 개요

- **정의:** 읍·면 행정복지센터 맞춤형복지팀 담당자가 방문 상담 메모를 붙여 넣거나 손글씨 메모 사진·상담 녹음을 올리면, 이를 텍스트로 바꾸고 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱. 담당자 승인 후에만 문서가 확정된다.
- **사용자:** 청도군 맞춤형복지팀 담당 공무원(수혜자: 방문 상담 대상 가구).
- **문제:** 상담 1건당 문서 작업 약 55분(추정): 메모 정리, 제도 대조, 의뢰서 작성, 후속 질문 정리.
- **원칙:** AI는 자격을 판정하지 않는다. 판정은 규칙 함수가 하고, AI는 사실 구조화·우선순위 선정·설명·초안·질문 생성만 한다. 도구 결과와 맞지 않는 추천은 검증에서 제거된다.
- **범위 제외:** 사회보장정보시스템 연동, 실제 개인정보 저장, 사용자 계정, 신청서 자동 제출.

## 2. 사용자 흐름

1. "데모 사례로 시작", 메모 직접 입력, 손글씨 메모 사진·상담 녹음 올리기(음성은 브라우저 녹음 가능). 로그인 없음. 사진·음성이면 인식 원문(가린 뒤)과 정리본을 나란히 보이고, 담당자는 정리본을 고쳐 텍스트로 다시 실행할 수 있다
2. 개인정보 가리기 전/후 표시
3. 타임라인 진행: (사진·음성이면 인식 → 인식 결과 정리 →) 사실 구조화 → 분야별 매칭(3개 병렬) → 근거 검증 → 문서 초안
4. 결과: "자격 충족" / "확인 필요" / "해당 없음(이유)". 항목별 충족·미충족 조건, 판정 값, 공식 출처
5. 상담기록지·의뢰서 초안을 구획별로 수정, 되돌리기
6. "의뢰서 확정" → 승인 창 → 승인 시 인쇄용 문서 생성, 거부 시 초안 복귀
7. 후속 질문(예: "기초연금은 왜 확인 필요야?")

## 3. 기능 요구사항

| ID | 기능 | 수용 기준 | 우선순위 |
|---|---|---|---|
| F1 | 데모 사례 5건 | 버튼 한 번으로 전체 흐름 완료 | 필수 |
| F2 | 개인정보 가리기 | 이름·주민번호·전화·상세주소·계좌를 모델 호출 전에 치환, 전/후 표시 | 필수 |
| F3 | 사실 구조화 | `CaseProfile` 추출, 모르는 값은 null | 필수 |
| F4 | 분야별 매칭 | 생계·주거 / 건강·의료 / 돌봄·고립·일자리 병렬 매칭 | 필수 |
| F5 | 근거 검증 | 제도 ID·판정 ID 불일치 추천 제거, 제거 사실 표시 | 필수 |
| F6 | 확인 필요 + 추가 질문 | 값 부족 시 "확인 필요", 다음 방문 질문 생성 | 필수 |
| F7 | 문서 초안 | 상담기록지·의뢰서, 구획별 수정·되돌리기 | 필수 |
| F8 | 승인 후 확정 | 승인 없이 확정 불가, 모델은 확정 실행 불가, 거부 시 초안 복귀 | 필수 |
| F9 | 후속 질문 | 같은 세션 맥락 유지. 저장된 실행 재생 중에는 쓸 수 없고 칩을 숨김 | 선택 |
| F10 | 평가 실행 | 5건 실처리, 재현율·정밀도·근거 일치율·처리 시간·가리기 재현율·자동 채움 필드 수·Verifier 보완 건수 표시, 사진·녹음 사례는 CER과 필수 필드 일치 수 | 필수 |
| F11 | 실행 재생 | 한도 초과·지연 시 저장된 실행을 "저장된 실행 재생"으로 표시 | 필수 |
| F12 | 사진 입력(OCR) | 손글씨·인쇄 메모 사진(JPEG·PNG, 5MB 이하)을 Document Intelligence로 인식, 낮은 신뢰도 단어 표시, 가리기 뒤에만 모델로 전달 | 필수(15:35 판단) |
| F13 | 음성 입력(STT) | 상담 녹음(WAV·MP3·WebM, 2분·10MB 이하)을 Speech 빠른 전사로 담당자·대상자 발화 분리 전사 | 필수(15:35 판단) |
| F14 | 인식 결과 정리 | NoteNormalizer가 반복·끊김·오인식 정리, 원문에 없는 숫자 추가 금지(`record_clean_note`가 거부), 바꾼 구간 표시 | F12·F13과 함께 |

## 4. 제도(13개, `data/schemes.json`)

- 생계·주거(`living`): 생계급여 `livelihood_benefit`, 주거급여 `housing_benefit`, 긴급복지 생계지원 `emergency_livelihood`, 에너지바우처 `energy_voucher`
- 건강·의료(`health`): 의료급여 `medical_benefit`, 본인부담 경감(차상위) `copay_reduction`, 장애인연금 `disability_pension`, 건강검진·방문건강관리 `health_checkup_visit`
- 돌봄·고립·일자리(`care`): 기초연금 `basic_pension`, 노인맞춤돌봄서비스 `elderly_care_service`, 응급안전안심서비스 `emergency_safety_service`, 노인일자리(공익활동) `senior_job_public`, 고독사 예방 안부 확인 `lonely_death_prevention`

항목: `id`, `name`, `domain`, `summary`, `rules`, `required_fields`, `source_url`, `checked_at`, `is_example: true`. 조건 ID는 `{scheme_id}.{접미사}`이고 제도별 조건·기준 비율은 TRD 4.2를 따른다.

- **소득인정액 단순화:** `소득인정액 = monthly_income_krw`(재산 환산 없음, `assets_krw`는 표시만). 기준액은 `기준 중위소득 × 비율`에서 원 미만을 버리고 이하(≤)로 비교한다. 수급 여부는 입력받지 않고 선행 제도 판정으로 대신한다. 화면·데이터에 표기한다.

## 5. 데이터 모델

`CaseProfile`: `age`, `household_type`(독거/부부/조손/한부모/기타), `household_size`, `monthly_income_krw`, `assets_krw`, `disability`(없음/경증/중증), `chronic_illness`, `housing`(자가/전세/월세/무상), `monthly_rent_krw`, `caregiver_available`, `isolation_signals`, `crisis_events`, `missing_fields`. 모르는 값은 `null`이고, 목록 필드는 메모에 언급이 없으면 `null`, 없다고 밝힌 경우만 빈 목록이다.

규칙 함수 필수 필드 6개: `age`, `household_type`, `household_size`, `monthly_income_krw`, `disability`, `housing`(제도마다 그중 읽는 필드를 `required_fields`에 둔다). `crisis_events`·`isolation_signals` 같은 서술 신호는 매칭 우선순위와 Documenter 입력에만 쓴다.

평가 사례(`data/eval_cases.json`) 5건: ① 저소득 독거노인 ② 고령 부부·소득 누락(손글씨 메모 사진) ③ 장애인 가구 ④ 실직 위기 가구(방문 녹음) ⑤ 인젝션 포함 사례. 필드: `note`, `input_type`(`text`·`image`·`audio`), `media_path`, `reference_text`, `expected_profile`, `expected_eligible/unknown/ineligible`, `pii_spans`.

지표 정의: 재현율 = (`expected_eligible` ∪ `expected_unknown`) 중 최종 `eligible`·`unknown`인 비율, 정밀도 = 최종 `eligible` 중 `expected_eligible` 비율, 근거 일치율 = 표시된 추천 중 판정 기록과 일치하는 비율(제거·보완 건수는 따로 표시), CER = 공백 제외 문자 단위 편집 거리 ÷ `reference_text` 길이.

문서 구획 ID(고정): `record.basic_info`, `record.summary`, `record.needs`, `record.linked_schemes`, `record.follow_up`, `referral.agency`, `referral.subject`, `referral.schemes`, `referral.officer`.

## 6. 워크플로와 도구

`InputRouter`(switch-case) → [`OCR`·`STT`(Azure AI)] → `Intake`(가리기, 코드) → [`NoteNormalizer`(AI, 사진·음성일 때)] → `Profiler`(AI) → 매칭 ×3(AI+도구, fan-out) → `Verifier`(코드, fan-in) → `Documenter`(AI) → `ReferralGate`(승인 대기, `request_info`). 단계 순서·분기·병렬·승인은 MAF 워크플로 간선으로만 표현하고, 에이전트 호출은 모두 `call_agent` 래퍼(시간 제한 45초, 단계당 최대 2회 시도, 오류 분류, 감사 기록)를 거친다.

| 도구 | 사용처 | 동작 |
|---|---|---|
| `record_clean_note` | NoteNormalizer | 정리본 저장. 원문에 없는 숫자가 생기면 거부 |
| `record_case_profile` | Profiler | 프로필 저장, 누락 필드 반환 |
| `search_schemes` | 매칭 | 분야별 제도 목록(호출 단계의 분야만) |
| `check_eligibility` | 매칭 | 서버가 실행 상태의 프로필로 규칙 판정(`eligible`/`ineligible`/`unknown`, `decision_id`) |
| `submit_matches` | 매칭 | 추천 목록 제출. 인용 검사 후 저장 |
| `lookup_decision` | Documenter | 같은 실행의 판정 기록 읽기 전용 조회 |
| `submit_draft` | Documenter | 문서 초안 제출(구획 ID 고정) |

구조화 결과는 제출 도구 인자로만 받는다. 판정 순서는 불충족 → `ineligible`, 필수 필드 누락 → `unknown`, 나머지 → `eligible`이다.

**Verifier 규칙:** (1) `scheme_id`·`decision_id` 필수 (2) 판정 기록과 일치 (3) `condition_ids`가 기록의 조건에 존재 (4) 불일치 시 제거 후 `removed`에 이유 기록 (5) `unknown`은 "확인 필요" (6) 에이전트가 건너뛴 제도는 규칙 함수로 직접 채움(실패 분야 포함) (7) 모델이 실제로 받지 않은 `decision_id` 인용 시 제거(`call_agent`의 감사 기록이 불완전한 단계는 생략) (8) 질문이 없는 확인 필요 항목은 누락 필드별 고정 질문으로 보완.

## 7. API

| 경로 | 설명 |
|---|---|
| `GET /` | UI |
| `GET /api/cases` | 데모 사례 목록(`case_id`, 제목, 요약, `input_type`) |
| `POST /api/runs` | JSON `{note \| case_id, mode, origin_run_id?}` 또는 multipart(`file`, `kind`: `image`\|`audio`) → `{run_id}` |
| `GET /api/runs/{id}/events` | SSE, `Last-Event-ID` 재접속, 15초 heartbeat 주석 줄, `done` 뒤에만 종료 |
| `POST /api/runs/{id}/approval` | `{request_id, approved, edited_sections, scheme_ids?}`. 이중 제출은 409 |
| `POST /api/runs/{id}/ask` | 후속 질문 → `202 {ask_id}`, 답변은 실행 SSE로. 승인 대기·확정 상태에서만 |
| `POST /api/eval` | `{eval_id}` 반환 |
| `GET /api/eval/{id}/events` | 평가 진행 SSE |
| `GET /healthz`, `GET /readyz` | 상태(`/readyz`는 시작 시 결과 캐시) |

SSE 이벤트: `masked`, `transcribed`, `normalized`, `step_started`, `step_completed`, `step_failed`, `step_retry`, `token`, `tool_call`, `tool_result`, `usage`, `verified`, `draft`, `approval_required`, `approval_kept`, `finalized`, `replaced`, `queued`, `error`, `done`. 평가 SSE: `case_started`, `case_completed`, `eval_summary`.

## 8. 비기능 요구사항

- **성능:** 1건 90초 이내, 모델 호출 45초 제한(넘으면 세션 삭제 후 새 세션으로 재시도, 단계당 최대 2회 시도), 동시 실행 4건(평가 포함).
- **성공 지표:** 재현율 ≥90%, 정밀도 ≥90%, 근거 일치율 100%, 가리기 잔존 0건·가리기 재현율 100%, 사진·녹음 사례의 CER과 필수 필드 일치 수 기록.
- **신뢰성:** 데모 사례에서 Profiler 실패·429·할당량 초과 시 새 실행으로 저장된 실행 재생(`data/replays/*.json`). 직접 입력은 재생 없이 오류·재시도 버튼.
- **보안:** IP별 분당 5회(실행·`/ask`), 입력 4,000자 제한, `/api/eval` 전역 동시 1건·분당 1회, 내장 도구 숨김 + 단계별 권한 허용 목록, 메모는 `<case_note>` 데이터로만 취급, 토큰은 Key Vault(사용자 할당 관리 ID, `AZURE_CLIENT_ID`), 상담 데이터 저장 없음(30분 후 삭제, Copilot CLI 세션 파일도 함께 삭제).
- **접근성:** `aria-live="polite"`, 키보드 조작, 명도 대비 4.5:1 이상, 색+글자 배지.
- **책임 있는 AI:** 상단 배너(합성 데이터 전용, AI 초안, 담당자 검토 필요), 모든 AI 문장에 "AI 초안" 표시, 제도 데이터는 예시임을 표시.

## 9. 기술 스택과 배포

- Python 3.12, FastAPI 0.162.0, Uvicorn 0.54.0, Pydantic 2.14.2, `agent-framework-core==1.24.0`, `agent-framework-github-copilot==2.1.1`, `github-copilot-sdk==1.0.28`(Copilot CLI 런타임 1.0.105), OpenTelemetry, Azure AI Services(Document Intelligence·Speech), 정적 HTML/바닐라 JS, SSE.
- Azure Container Apps(단일 리비전, 최소·최대 복제본 1), ACR, Key Vault, AI Services, Application Insights. `azd up` + Bicep.
- 구조화 출력은 `response_format` 미지원이므로 도구 인자(Pydantic)로만 받는다.

## 10. 구현 순서

기준은 `docs/sdd/SPRINTS.md`, 태스크 명세는 `docs/sdd/tasks/`(25개), 워커 루프는 `docs/sdd/LOOP.md`다.

1. S0(14:00–14:15): 계약 골격 T00, 최소 샘플 T01, 인프라 T02 → G0 빈 앱 배포
2. S1(14:15–14:45): 규칙·가리기·검증·상태·평가 사례·UI 골격을 병렬로
3. S2(14:45–15:10): 도구·에이전트·워크플로(직렬)·서비스·결과 UI → G1 1차 제출(F1~F8)
4. S3(15:10–15:40): 재생(F11)·평가(F10), 병렬화·공급자·훅·F9·재승인 → G2
5. S4(15:40–16:00): 사진·음성(F12~F14), 가용성 테스트 → G3 코드 동결
6. S5(16:00–16:20): 지표 기록·문서 동기화 → 최종 제출

자를 수 있는 기능은 기능 플래그 뒤에 만들고, 게이트에서 켠다(플래그 10개는 TRD 6절).

**자르는 순서(시간 부족 시, TRD 10절과 스파인 동일):** 가용성 테스트 → 브라우저 녹음 → STT 화자 분리 → F13 → F12·F14 → 거부 후 재승인 → F9 → 세션 훅 → `VerifiedDecisionsProvider` → 매칭 병렬화. F12·F13을 모두 자르면 `enableAiServices`를 끈다. F1~F8, F10, F11은 유지한다.

## 11. 저장소 구조

```text
app/{config,schemas}.py                                  # L0 계약 (schemas.py 먼저 병합)
app/{rules,masking,textnum,verify,render,limits}.py      # L1 순수 코어
app/{runs,events}.py                                     # L2 실행 상태, 이벤트 로그
app/{tools,prompts,telemetry}.py                         # L3
app/{agents,context,ingest}.py                           # L4
app/workflow.py, app/executors/{core,media,gate}.py     # L5 간선, 실행기
app/{service,replay,evaluation,ask}.py                   # L6
app/main.py                                              # L7
app/static/{index.html,style.css,print.css}, app/static/js/{app,api,timeline,results,drafts,eval,ask,media}.js
data/{schemes.json,eval_cases.json,samples/,replays/}
scripts/record_replay.py, scripts/sdd.py
docs/{reference/,sdd/,eval-result.md}
infra/main.bicep, azure.yaml, Dockerfile, requirements.txt, requirements-dev.txt, pytest.ini
tests/
```

아래층은 위층을 import하지 않는다. 모듈별 불변 규칙은 `_bmad-output/planning-artifacts/architecture/architecture-동행노트-2026-11-05/ARCHITECTURE-SPINE.md`(AD-1~AD-16)를 따른다.

테스트(MAF·네트워크 없이): 가리기·OCR 숫자 보정 패턴, 규칙 함수 경계값·판정 순서, Verifier 대조 규칙 1~5·7·8, 확정 문서 생성, 입력 검사, 제출 도구 거부 규칙, 권한 처리기 허용 목록.

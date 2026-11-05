# SPEC — 동행노트

`PRD.md`와 `TRD.md`를 요약한 구현 명세다. 기준 문서는 PRD/TRD이며, 충돌하면 그쪽을 따른다.

## 1. 서비스 개요

- **정의:** 읍·면 행정복지센터 맞춤형복지팀 담당자가 방문 상담 메모를 입력하거나 손글씨 메모 사진·상담 녹음을 올리면, 텍스트로 바꾸고 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱. 담당자 승인 후에만 문서가 확정된다.
- **사용자:** 청도군 맞춤형복지팀 담당 공무원(수혜자: 방문 상담 대상 가구).
- **문제:** 상담 1건당 문서 작업 약 55분(추정): 메모 정리, 제도 대조, 의뢰서 작성, 다음 방문 확인 사항 정리.
- **원칙:** AI는 자격을 판정하지 않는다. 판정은 규칙 함수가 하고, AI는 인식 결과 정리·사실 구조화·우선순위 선정·설명·초안·추가 질문 작성만 한다. 도구 결과와 맞지 않는 추천은 검증에서 제거된다.
- **범위 제외:** 사회보장정보시스템 연동, 실제 개인정보 저장, 사용자 계정, 신청서 자동 제출.

## 2. 사용자 흐름

1. "데모 사례로 시작", 메모 직접 입력, 또는 손글씨 메모 사진·상담 녹음 올리기(브라우저 녹음 포함, 로그인 없음). 사진·음성이면 인식 원문과 정리본, 불확실 구간, 바꾼 구간을 나란히 표시
2. 개인정보 가리기 전/후 표시
3. 타임라인 진행: 사실 구조화 → 분야별 매칭(3개 병렬) → 근거 검증 → 문서 초안
4. 결과: "자격 충족" / "확인 필요" / "해당 없음(이유)". 항목별 충족·미충족 조건, 판정 값, 공식 출처
5. 상담기록지·의뢰서 초안을 구획별로 수정, 되돌리기
6. "의뢰서 확정" → 승인 창 → 승인 시 인쇄용 문서 생성, 거부 시 실행이 초안 상태로 끝남("확정 취소됨")

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
| F8 | 승인 후 확정 | 승인 없이 확정 불가, 모델은 확정 실행 불가, 거부 시 실행은 초안 상태로 끝남 | 필수 |
| F10 | 평가 실행 | 5건 실처리, 재현율·정밀도·근거 일치율·처리 시간·가리기 재현율·인식 CER 표시, 라이브/재생 구분 | 필수 |
| F11 | 실행 재생 | 한도 초과·지연 시 저장된 실행을 "저장된 실행 재생"으로 표시. 데모 사례 실패나 Copilot 미준비 시 화면이 재생으로 자동 시작 | 필수 |
| F12 | 사진 입력(OCR) | JPEG·PNG 5MB 이하, 한국어 손글씨 인식, 낮은 신뢰도 단어 표시 | 필수(15:55 판단, TRD 10절) |
| F13 | 음성 입력(STT) | WAV·MP3·WebM 2분·10MB 이하, 담당자·대상자 화자 분리, 브라우저 녹음과 파일 올리기 | 필수(15:55 판단, TRD 10절) |
| F14 | 인식 결과 정리 | NoteNormalizer가 반복·끊김·오인식 정리, 원문에 없는 숫자 추가 불가, 바꾼 구간 표시 | F12·F13과 함께 |

## 4. 제도(13개, `data/schemes.json`)

- 생계·주거: 생계급여, 주거급여, 긴급복지 생계지원, 에너지바우처
- 건강·의료: 의료급여, 본인부담 경감(차상위), 장애인연금, 건강검진·방문건강관리
- 돌봄·고립·일자리: 기초연금, 노인맞춤돌봄서비스, 응급안전안심서비스, 노인일자리(공익활동), 고독사 예방 안부 확인

항목: `id`, `name`, `domain`, `summary`, `rules`, `required_fields`, `source_url`, `checked_at`, `is_example: true`. 소득인정액 계산은 단순화하고 화면·데이터에 표기한다.

## 5. 데이터 모델

`CaseProfile`: `age`, `household_type`(독거/부부/조손/한부모/기타), `household_size`, `monthly_income_krw`, `assets_krw`, `disability`, `chronic_illness`, `housing`, `monthly_rent_krw`, `caregiver_available`, `isolation_signals`, `crisis_events`, `missing_fields`.

규칙 함수 필수 필드 6개: `age`, `household_type`, `household_size`, `monthly_income_krw`, `disability`, `housing`. 판정 순서는 불충족 → `ineligible`, 필수 필드 누락 → `unknown`, 나머지 → `eligible`이다.

평가 사례(`data/eval_cases.json`) 5건: ① 저소득 독거노인 ② 고령 부부·소득 누락(손글씨 메모 사진) ③ 장애인 가구 ④ 실직 위기 가구(방문 녹음) ⑤ 인젝션 포함 사례. 필드: `note`, `expected_profile`, `expected_eligible/unknown/ineligible`, `pii_spans`, `input_type`, `media_path`, `reference_text`. 사례 2·4는 인식 텍스트와 정답 원문의 문자 오류율(CER)과 판정 필수 필드 일치 수를 계산한다.

## 6. 워크플로와 도구

`InputRouter`(switch-case) → [`OCR`·`STT`(Azure AI)] → `Intake`(가리기, 코드) → [`NoteNormalizer`(AI, 사진·음성일 때)] → `Profiler`(AI) → 매칭 ×3(AI+도구, fan-out) → `Verifier`(코드, fan-in) → `Documenter`(AI) → `ReferralGate`(승인 대기, `request_info`). 단계 순서·분기·병렬·승인은 MAF 워크플로 간선으로만 표현하고, 에이전트 호출은 모두 `call_agent` 래퍼(시간 제한 45초, 단계당 최대 2회 시도, 시도 번호 `attempt` 검사, 오류 분류, 감사 기록)를 거친다. Documenter 프롬프트에는 `prompts.py`가 검증 통과 판정 목록을 직접 넣는다. 추론 강도는 Profiler·매칭 `low`, Documenter `medium`이다.

| 도구 | 사용처 | 동작 |
|---|---|---|
| `record_clean_note` | NoteNormalizer | 정리본 저장. 원문에 없는 숫자가 생기면 거부 |
| `record_case_profile` | Profiler | 프로필 저장, 누락 필드 반환 |
| `search_schemes` | 매칭 | 분야별 제도 목록(호출 단계의 분야만) |
| `check_eligibility` | 매칭 | 서버가 실행 상태의 프로필로 규칙 판정(`eligible`/`ineligible`/`unknown`, `decision_id`) |
| `submit_matches` | 매칭 | 추천 목록 제출. 인용 검사 후 저장 |
| `lookup_decision` | Documenter | 같은 실행의 판정 기록 읽기 전용 조회 |
| `submit_draft` | Documenter | 문서 초안 제출(구획 ID 고정) |

구조화 결과는 제출 도구 인자로만 받는다.

**Verifier 규칙:** (1) `scheme_id`·`decision_id` 필수 (2) 판정 기록과 일치 (3) `condition_ids`가 기록의 조건에 존재 (4) 불일치 시 제거 후 `removed`에 이유 기록 (5) `unknown`은 "확인 필요" (6) 에이전트가 건너뛴 제도는 규칙 함수로 직접 채움(실패 분야 포함) (7) 모델이 실제로 받지 않은 `decision_id` 인용 시 제거. 감사 기록은 `call_agent`가 스트림의 `function_call`·`function_result` 콘텐츠로 남기며, 기록이 불완전한 단계는 규칙 7을 생략한다.

## 7. API

| 경로 | 설명 |
|---|---|
| `GET /` | UI |
| `GET /api/cases` | 데모 사례 목록 |
| `POST /api/runs` | JSON `{note \| case_id, mode}` 또는 multipart(`file`, `kind`: `image`\|`audio`) → `{run_id}` |
| `GET /api/runs/{id}/events` | SSE, `Last-Event-ID` 재접속, 15초 heartbeat 주석 줄, `done` 뒤에만 종료 |
| `POST /api/runs/{id}/approval` | `{request_id, approved, edited_sections, scheme_ids?}`. 이중 제출은 409 |
| `POST /api/eval` | `{eval_id}` 반환 |
| `GET /api/eval/{id}/events` | 평가 진행 SSE |
| `GET /healthz`, `GET /readyz` | 상태(`/readyz`는 시작 시 결과 캐시, Copilot 미준비면 UI가 데모 사례를 재생으로 시작) |

SSE 이벤트: `masked`, `transcribed`, `normalized`, `step_started`, `step_completed`, `step_failed`, `step_retry`, `token`, `tool_call`, `tool_result`, `usage`, `verified`, `draft`, `approval_required`, `approval_kept`, `finalized`, `error`, `done`. 평가 SSE: `case_started`, `case_completed`, `eval_summary`.

실행 상태: `running|replaying → awaiting_approval → resuming → finalized`, 그 밖에 `failed`, `drafted`(승인 거부).

## 8. 비기능 요구사항

- **성능:** 1건 90초 이내, 모델 호출 45초 제한(넘으면 세션 삭제 후 새 세션으로 재시도, 단계당 최대 2회 시도), 동시 실행 4건(평가 포함, 넘으면 자리가 날 때 시작).
- **성공 지표:** 재현율 ≥90%, 정밀도 ≥90%, 근거 일치율 100%, 가리기 잔존 0건·가리기 재현율 100%, 사진·녹음 사례의 CER과 필수 필드 일치 수 기록.
- **신뢰성:** 서버는 진행 중인 실행을 재생으로 바꾸지 않는다. 데모 사례 실행이 실패로 끝나면 UI가 같은 사례로 `mode:"replay"` 새 실행을 시작하고 "저장된 실행 재생" 배지를 보인다(`data/replays/*.json`). 직접 입력은 재생 없이 오류·재시도 버튼.
- **보안:** IP별 분당 5회(`POST /api/runs`), 입력 4,000자 제한, 사진 5MB·음성 10MB·2분 제한(내용 시그니처 검사), `/api/eval` 전역 동시 1건·분당 1회, 내장 도구 숨김 + 단계별 권한 허용 목록, 메모는 `<case_note>` 데이터로만 취급, 토큰은 Key Vault(사용자 할당 관리 ID, `AZURE_CLIENT_ID`, 실패 시 Container Apps secret 대체), 사진·음성 원본은 Azure AI Services로만 보내고 모델에는 가린 텍스트만 전달, 상담 데이터 저장 없음(마지막 활동 뒤 30분, 생성 후 최대 45분에 삭제, Copilot CLI 세션 파일도 함께 삭제).
- **관측:** Application Insights trace, `/readyz` 가용성 테스트와 경고 3개(가용성 실패, 5xx, `rate_limit`).
- **접근성:** `aria-live="polite"`, 키보드 조작, 명도 대비 4.5:1 이상, 색+글자 배지.
- **책임 있는 AI:** 상단 배너(합성 데이터 전용, AI 초안, 담당자 검토 필요), 모든 AI 문장에 "AI 초안" 표시, 제도 데이터는 예시임을 표시.

## 9. 기술 스택과 배포

- Python 3.12, FastAPI 0.162.0, Uvicorn 0.54.0, Pydantic 2.14.2, `agent-framework-core==1.24.0`, `agent-framework-github-copilot==2.1.1`, `github-copilot-sdk==1.0.28`(Copilot CLI 런타임 1.0.105), OpenTelemetry, Azure AI Services(Document Intelligence `prebuilt-read`·Speech 빠른 전사), 정적 HTML/바닐라 JS, SSE.
- Azure Container Apps(단일 리비전, 최소·최대 복제본 1), ACR, Key Vault, AI Services(`enableAiServices`로 켬), Application Insights. `azd up` + Bicep.
- 구조화 출력은 `response_format` 미지원이므로 도구 인자(Pydantic)로만 받는다.

## 10. 구현 순서

1. 14:00–14:15 최소 샘플로 라이브러리 시그니처 확인
2. 14:15–14:45 빈 앱 `azd up`(`enableAiServices` 끔) 뒤 AI Services 켜고 재배포, 팀원 1명이 합성 사진·녹음 제작(병렬)
3. 14:45–15:30 F1~F8(매칭 병렬 포함)과 UI, 15:30 1차 제출
4. 15:30–15:40 재생 파일 생성(F11)
5. 15:40–15:55 사진·음성 입력(F12~F14)
6. 15:55 판단 시각: 배포 앱에서 사진·음성 경로가 통과하지 않으면 그 시각에 자르고 문서에서도 지운다
7. 15:55–16:10 평가 실행(F10)
8. 16:10–16:20 문서 동기화, 16:20 최종 제출

**자르는 순서(시간 부족 시, TRD 10절):** 가용성 테스트·경고 → 브라우저 녹음 → STT 화자 분리 → F13 음성 입력 전체 → F12 사진 입력 전체와 F14. F1~F8, F10, F11은 유지한다.

## 11. 저장소 구조

```text
app/{config,schemas}.py                                  # L0 계약 (schemas.py 먼저 병합)
app/{rules,masking,textnum,verify,render,limits}.py      # L1 순수 코어
app/{runs,events}.py                                     # L2 실행 상태, 이벤트 로그
app/{tools,prompts,telemetry}.py                         # L3
app/{agents,ingest}.py                                   # L4
app/workflow.py, app/service.py, app/main.py             # L5–L7
app/static/{index.html,app.js,style.css}
data/{schemes.json,eval_cases.json,samples/,replays/}
scripts/record_replay.py
docs/{reference/,eval-result.md}
infra/main.bicep, azure.yaml, Dockerfile, requirements.txt
tests/
```

아래층은 위층을 import하지 않는다. 모듈별 불변 규칙은 TRD 본문(3.2절 상태 쓰기 주체와 이벤트 경로, 3.3절 ID 계약과 단일 판정 원천, 3.5절 승인 뒤 코드 확정, 11절 모듈 의존 방향)을 따른다.

테스트(MAF·네트워크 없이): 가리기·OCR 숫자 보정 패턴, 규칙 함수 경계값·판정 순서, Verifier 대조 규칙 1~7, 확정 문서 생성, 입력 검사, 제출 도구 거부 규칙, 권한 처리기 허용 목록.

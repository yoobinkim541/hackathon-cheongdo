# SPEC — 동행노트

`PRD.md`와 `TRD.md`를 요약한 구현 명세다. 기준 문서는 PRD/TRD이며, 충돌하면 그쪽을 따른다. API와 보안의 상세는 `docs/api.md`에 있다.

## 1. 서비스 개요

- **정의:** 읍·면 행정복지센터 맞춤형복지팀 담당자가 방문 상담 메모를 입력하거나 손글씨 메모 사진·상담 녹음을 올리면, 텍스트로 바꾸고 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱. 담당자 승인 후에만 문서가 확정된다.
- **사용자:** 청도군 맞춤형복지팀 담당 공무원(수혜자: 방문 상담 대상 가구).
- **문제:** 상담 1건당 문서 작업 [가정] 45분(30~60분): 메모 정리, 제도 대조, 의뢰서 작성, 다음 방문 확인 사항 정리. 현장 실측값이 아니며 절감량 산정은 PRD 5.1절([측정]·[가정]·[계산] 구분).
- **원칙:** AI는 자격을 판정하지 않는다. 판정은 규칙 함수가 하고, AI는 인식 결과 정리·사실 구조화·우선순위 선정·설명·초안·추가 질문 작성만 한다. 도구 결과와 맞지 않는 추천은 검증에서 제거된다.
- **범위 제외:** 사회보장정보시스템 연동, 실제 개인정보 저장, 사용자 계정, 신청서 자동 제출.

## 2. 사용자 흐름

1. "데모 사례로 시작", 메모 직접 입력, 또는 손글씨 메모 사진·상담 녹음 올리기(브라우저 녹음 포함, 로그인 없음). 사진·음성이면 인식 원문과 정리본, 불확실 구간, 바꾼 구간을 나란히 표시
2. 개인정보 가리기 전/후 표시
3. 타임라인 진행: 사실 구조화 → 분야별 매칭(3개 병렬) → 근거 검증 → 문서 초안
4. 결과: "규칙상 충족" / "확인 필요" / "해당 없음(이유)". "규칙상 충족"은 단순화한 공개 기준에 따른 규칙 함수 결과이며 담당자가 최종 확인한다는 안내를 함께 표시. 항목별 충족·미충족 조건, 판정 값, 공식 출처
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
| F7 | 문서 초안 | 상담기록지·의뢰서, 구획별 수정·되돌리기. 초안 에이전트 실패 시 판정 결과로 만든 기본 초안 | 필수 |
| F8 | 승인 후 확정 | 승인 없이 확정 불가, 모델은 확정 실행 불가, 거부 시 실행은 초안 상태로 끝남 | 필수 |
| F10 | 평가 실행 | 5건 실처리, 재현율·정밀도·근거 일치율·처리 시간·가리기 잔존·가리기 재현율·오검출·인식 CER·자동 채움 필드·Verifier 보완 표시, 라이브/재생 구분, 평균은 라이브 사례만 | 필수 |
| F11 | 실행 재생 | 한도 초과·지연 시 저장된 실행을 "저장된 실행 재생"으로 표시. 데모 사례 실패나 Copilot 미준비 시 화면이 재생으로 자동 시작. 재생 파일은 사례 5건 모두 있음(사례 2·4는 OCR·STT 포함) | 필수 |
| F12 | 사진 입력(OCR) | JPEG·PNG 5MB 이하, 한국어 손글씨 인식, 낮은 신뢰도 단어 표시 | 필수(15:55 판단, TRD 10절), 구현됨 |
| F13 | 음성 입력(STT) | WAV·MP3·WebM·OGG 2분·10MB 이하, 담당자·대상자 화자 분리, 브라우저 녹음과 파일 올리기 | 필수(15:55 판단, TRD 10절), 구현됨 |
| F14 | 인식 결과 정리 | NoteNormalizer가 반복·끊김·오인식 정리, 원문에 없는 숫자 추가 불가, 바꾼 구간 표시, 실패 시 정리 생략 | F12·F13과 함께, 구현됨 |

## 4. 제도(13개, `data/schemes.json`)

- 생계·주거: 생계급여, 주거급여, 긴급복지 생계지원, 에너지바우처
- 건강·의료: 의료급여, 본인부담 경감(차상위), 장애인연금, 건강검진·방문건강관리
- 돌봄·고립·일자리: 기초연금, 노인맞춤돌봄서비스, 응급안전안심서비스, 노인일자리(공익활동), 고독사 예방 안부 확인

항목: `id`, `name`, `domain`, `summary`, `rule`(규칙 함수 이름), `params`(기준값), `required_fields`, `source_url`, `checked_at`, `is_example: true`. 소득인정액은 월 소득만으로 단순화하고 제도 요약에 표기한다. 긴급복지 생계지원(`rule: income_pct_crisis`)은 소득 조건과 함께 `crisis_events`에 법정 위기 사유 낱말(실직·폐업·사망·중한 질병 등)이 있어야 충족이며, 위기 사유가 기록되지 않았으면 `unknown`("확인 필요")이다.

## 5. 데이터 모델

`CaseProfile`: `age`, `household_type`(독거/부부/조손/한부모/기타), `household_size`, `monthly_income_krw`, `assets_krw`, `disability`(없음/경증/중증), `chronic_illness`, `housing`, `monthly_rent_krw`, `caregiver_available`, `isolation_signals`, `crisis_events`, `current_benefits`(메모에 받고 있다고 적힌 제도 이름), `missing_fields`.

규칙 함수 필수 필드 6개: `age`, `household_type`, `household_size`, `monthly_income_krw`, `disability`, `housing`. 판정 순서는 불충족 → `ineligible`, 필수 필드 누락·미판정 조건 → `unknown`, 나머지 → `eligible`이다. `current_benefits`에 제도 이름이 맞는 항목이 있으면 그 제도에 조건 "이미 받는 중이 아님"(불충족)을 붙여 `ineligible`("해당 없음")로 둔다.

평가 사례(`data/eval_cases.json`) 5건: ① 저소득 독거노인 ② 고령 부부·소득 누락(손글씨 메모 사진) ③ 장애인 가구 ④ 실직 위기 가구(방문 녹음) ⑤ 인젝션 포함 사례. 필드: `id`, `title`, `household`, `note`, `expected_profile`, `expected_eligible/unknown/ineligible`, `pii_spans`, `names`, `input_type`, `media_path`, `reference_text`. 사례 2·4를 OCR·STT로 실제 처리하면 인식 텍스트와 정답 원문의 문자 오류율(CER)을 계산한다.

## 6. 워크플로와 도구

`InputRouter`(switch-case) → [`OCR`·`STT`(Azure AI)] → `Intake`(가리기, 코드) → [`NoteNormalizer`(AI, 사진·음성일 때)] → `Profiler`(AI) → 매칭 ×3(AI+도구, fan-out) → `Verifier`(코드, fan-in) → `Documenter`(AI) → `ReferralGate`(승인 대기, `request_info`). 단계 순서·분기·병렬·승인은 MAF 워크플로 간선으로만 표현하고, 에이전트 호출은 모두 `call_agent` 래퍼(시간 제한 45초, 단계당 최대 2회 시도, 시도 번호 `attempt` 검사, 오류 분류, 감사 기록)를 거친다. 에이전트 스트림은 `call_agent` 안에서 `events.map_update`가 UI 이벤트로 바꾸고, 모든 실행기는 `UiEvent`만 출력한다. 최종 출력(`output_from`)은 `ReferralGate`뿐이다. Documenter 프롬프트에는 `prompts.py`가 검증 통과 판정 목록을 직접 넣는다. 추론 강도는 NoteNormalizer·Profiler·매칭 `low`, Documenter `medium`이다(모델이 지원할 때만 적용). 실패 처리: NoteNormalizer 실패는 정리 생략(`normalized.skipped=true`), 매칭 실패는 해당 분야 규칙 판정으로 보완, Documenter 실패는 기본 초안(`fallback_draft`), Profiler 실패는 실행 실패.

| 도구 | 사용처 | 동작 |
|---|---|---|
| `record_clean_note` | NoteNormalizer | 정리본 저장. 원문에 없는 숫자가 생기면 거부 |
| `record_case_profile` | Profiler | 프로필 저장, 누락 필드 반환 |
| `search_schemes` | 매칭 | 분야별 제도 목록(호출 단계의 분야만) |
| `check_eligibility` | 매칭 | 서버가 실행 상태의 프로필로 규칙 판정(`eligible`/`ineligible`/`unknown`, `decision_id`) |
| `submit_matches` | 매칭 | 추천 목록 제출. 인용 검사 후 저장 |
| `lookup_decision` | Documenter | 같은 실행의 판정 기록 읽기 전용 조회 |
| `submit_draft` | Documenter | 문서 초안 제출(구획 ID 고정) |

구조화 결과는 제출 도구 인자로만 받는다. MAF가 중첩 인자를 `dict`로 넘기므로 도구가 Pydantic으로 직접 검증하고(`tools._coerce`), 오류는 거부 문자열로 모델에 돌려준다.

**Verifier 규칙:** (1) `scheme_id`·`decision_id` 필수 (2) 판정 기록의 제도·분야와 일치, `ineligible` 판정은 추천 불가 (3) `condition_ids`가 기록의 조건에 존재 (4) 불일치·중복 시 제거 후 `removed`에 이유 기록 (5) `unknown`은 "확인 필요" (6) 에이전트가 건너뛴 제도는 규칙 함수로 직접 채움(실패 분야 포함) (7) 모델이 실제로 받지 않은 `decision_id` 인용 시 제거. 감사 기록은 `call_agent` 안에서 스트림의 `function_call`·`function_result` 콘텐츠로 남기며, 기록이 불완전한 단계는 규칙 7을 생략하고 `audit_rule_skipped`에 표시한다.

## 7. API

| 경로 | 설명 |
|---|---|
| `GET /` | UI |
| `GET /api/cases` | 데모 사례 목록(`media_url`, `replay_available`) |
| `GET /api/schemes` | 제도 목록 |
| `GET /samples/{name}` | 데모 사진·음성(사례 데이터의 파일만) |
| `POST /api/runs` | JSON `{note \| case_id, mode}` 또는 multipart(`file`, `kind`: `image`\|`audio`) → `201 {run_id, mode}`. 직접 입력은 Copilot 미준비 시 409 |
| `GET /api/runs/{id}` | 실행 상태 |
| `GET /api/runs/{id}/events` | SSE, `Last-Event-ID` 재접속, 15초 heartbeat 주석 줄, `done` 뒤에만 종료 |
| `POST /api/runs/{id}/approval` | `{request_id, approved, edited_sections, scheme_ids?}` → 202. 이중 제출은 409 |
| `POST /api/eval` | `201 {eval_id}` 반환 |
| `GET /api/eval/{id}/events` | 평가 진행 SSE |
| `GET /healthz`, `GET /readyz` | 상태(`/readyz`는 시작 시 결과 캐시, 판정은 정적 데이터 적재만. Copilot 미준비면 UI가 데모 사례를 재생으로 시작) |

모든 `/api/` POST는 `X-Requested-With: dongheng` 헤더가 필요하고, 실행·평가는 만든 브라우저의 세션 쿠키 `dh_sid`로만 접근할 수 있다(다르면 403).

SSE 이벤트: `run_started`, `masked`, `transcribed`, `normalized`, `profile`, `step_started`, `step_completed`, `step_failed`, `step_retry`, `token`, `tool_call`, `tool_result`, `usage`, `verified`, `draft`, `approval_required`, `approval_kept`, `finalized`, `error`, `done`. 평가 SSE: `case_started`, `case_completed`, `eval_summary`, `error`, `done`.

실행 상태: `running|replaying → awaiting_approval → resuming → finalized`, 그 밖에 `failed`, `drafted`(승인 거부). 만료로 지워지는 실행은 `done {"status": "expired"}`를 마지막으로 쓴다.

## 8. 비기능 요구사항

- **성능:** 1건 90초 이내, 모델 호출 45초 제한(시간 초과·오류 시 세션 삭제 후 새 세션으로 재시도, 단계당 최대 2회 시도, `rate_limit`은 재시도 없음), 동시 실행 4건(평가 포함, 넘으면 자리가 날 때 시작).
- **성공 지표(PRD 표 3):** 재현율 ≥90%("확인 필요"도 찾은 것으로 셈), 정밀도 ≥90%("규칙상 충족"만 대상), 둘 다 사례별 값의 5건 평균. 근거 일치율 100%(모델이 인용한 판정과 규칙 함수 결과의 일치이며 정답 자격 정확도가 아님). 처리 시간 90초 이내. 가리기 잔존 0건·가리기 재현율 100%. CER 사진 ≤0.10, 녹음 ≤0.15. 배포 앱 실측(2026-11-05 15:37–15:39 KST, 커밋 `a9a4b1ae`, 라이브 5건): 재현율·정밀도·근거 일치율 1.00, 평균 40.6초(35.4~49.7초), 잔존 0건, CER 사진 0.000·녹음 0.117, Verifier 보완 0건. 이전 리비전(`5bb3c20`)에서는 사례 4 정밀도 0.00이 배포 앱에서 2회 재현되었고(STT 오인식), `2674bead`에서 고쳤다(`docs/eval-result.md`).
- **신뢰성:** 서버는 진행 중인 실행을 재생으로 바꾸지 않는다. 데모 사례 실행이 실패로 끝나면 UI가 같은 사례로 `mode:"replay"` 새 실행을 시작하고 "저장된 실행 재생" 배지를 보인다(`data/replays/case1~case5.json`). 직접 입력은 재생 없이 오류·재시도 버튼.
- **보안:** 세션 쿠키 `dh_sid`(HttpOnly, SameSite=Strict, https에서 Secure)로 실행·평가를 만든 브라우저에 묶음, POST에 `X-Requested-With: dongheng` 필수, CSP 등 보안 헤더와 `no-store`, OpenAPI 문서 끔, IP별 분당 5회(`POST /api/runs`), 입력 4,000자 제한, 본문 JSON 64KB, 사진 5MB·음성 10MB·WAV 2분 제한(내용 시그니처 검사), `/api/eval` 전역 동시 1건·분당 1회, 내장 도구 숨김 + 단계별 권한 허용 목록, 메모는 `<case_note>` 데이터로만 취급, 토큰은 Key Vault(사용자 할당 관리 ID, `AZURE_CLIENT_ID`), 사진·음성 원본은 Azure AI Services(키 없는 관리 ID 인증)로만 보내고 모델에는 가린 텍스트만 전달, 상담 데이터 저장 없음(마지막 활동 뒤 30분, 생성 후 최대 45분에 삭제, Copilot CLI 세션 파일도 함께 삭제). 상세와 한계는 `docs/api.md` 3절.
- **관측:** Application Insights trace(예: `4c4b94fd281063f0ccf0fb2da3e2c707`, 루트 span `dongheng.run`), `/healthz` 가용성 테스트와 경고 3개(가용성 실패, 5xx, `rate_limit`). `ALERT_EMAIL`을 정했을 때만 메일 작업 그룹을 연결한다. 확정 이벤트에 담당자 검토 시간 `review_seconds`와 고친 구획 수 `edited_sections`를 기록한다.
- **복구 한계:** 최소·최대 복제본 1, 실행 상태는 프로세스 메모리. 재배포·재시작 시 진행 중인 실행이 사라지고(`run_not_found`), 데모 사례는 실패 시 저장된 실행 재생으로 자동 전환한다.
- **접근성·UX:** 진행·검증·확정 알림 `aria-live="polite"`, 검증 완료·확정 시 포커스를 결과 제목(`#result-title`)으로 이동, 근거 패널 열림 시 근거 제목으로 이동하고 닫으면 누른 항목으로 복귀, 탭 좌우 화살표 이동, 승인 창 `<dialog>`(Esc로 닫힘), `:focus-visible` 3px 외곽선, 본문 글자 명도 대비 4.5:1 이상(측정값 TRD 9절), 색+글자 배지, 버튼·탭 터치 영역 44px 이상. 타임라인의 도구 호출은 쉬운 한국어 칩(예: "기초연금 → 해당 없음")으로, 모델 출력은 단계별 "에이전트 설명 보기"에 글로 표시한다.
- **책임 있는 AI:** 상단 배너(합성 데이터 전용, AI 초안, 담당자 검토 필요), AI 설명과 초안에 "AI 초안" 표시, 제도 데이터는 예시임을 표시.

## 9. 기술 스택과 배포

- Python 3.12, FastAPI 0.162.0, Uvicorn 0.54.0, Pydantic 2.14.2, `agent-framework-core==1.24.0`, `agent-framework-github-copilot==2.1.1`, `github-copilot-sdk==1.0.28`(Copilot CLI 런타임 1.0.105), OpenTelemetry·Azure Monitor, Azure AI Services(Document Intelligence `prebuilt-read`·Speech 빠른 전사), `azure-identity`, `httpx`, 정적 HTML/바닐라 JS, SSE. 모델은 `COPILOT_MODEL`(배포 값 `claude-sonnet-5.5`).
- Azure Container Apps(단일 리비전, 최소·최대 복제본 1), ACR, Key Vault, AI Services(`enableAiServices`로 켬), Application Insights. 리소스 그룹 `rg-dongheng-prod`, 지역 Korea Central(Container Apps·AI Services 모두). `azd up` + Bicep(`infra/main.bicep`, `infra/modules/*.bicep`).
- 구조화 출력은 `response_format` 미지원이므로 도구 인자(Pydantic)로만 받는다.

## 10. 구현 순서

1. 14:00–14:15 최소 샘플로 라이브러리 시그니처 확인
2. 14:15–14:45 빈 앱 `azd up`(`enableAiServices` 끔) 뒤 AI Services 켜고 재배포, 팀원 1명이 합성 사진·녹음 제작(병렬)
3. 14:45–15:30 F1~F8(매칭 병렬 포함)과 UI, 15:30 1차 제출
4. 15:30–15:40 재생 파일 생성(F11)
5. 15:40–15:55 사진·음성 입력(F12~F14) — 구현됨
6. 15:55 판단 시각: 배포 앱에서 사진·음성 경로가 통과하지 않으면 그 시각에 자르고 문서에서도 지운다
7. 15:55–16:10 평가 실행(F10)
8. 16:10–16:20 문서 동기화, 16:20 최종 제출

**자르는 순서(시간 부족 시, TRD 10절):** 가용성 테스트·경고 → 브라우저 녹음 → STT 화자 분리 → F13 음성 입력 전체 → F12 사진 입력 전체와 F14. F1~F8, F10, F11은 유지한다.

## 11. 저장소 구조

```text
app/{config,schemas}.py                                  # L0 계약
app/{rules,masking,textnum,verify,render,limits}.py      # L1 순수 코어
app/{runs,events}.py                                     # L2 실행 상태·이벤트 로그, 이벤트 변환
app/{tools,prompts,telemetry}.py                         # L3
app/{agents,ingest}.py                                   # L4
app/workflow.py, app/service.py, app/main.py             # L5–L7
app/static/{index.html,app.js,style.css}
data/{schemes.json,eval_cases.json,samples/,replays/}
scripts/record_replay.py
docs/{api.md,reference/}
infra/main.bicep, infra/main.parameters.json, infra/modules/{resources,ai,alerts,fetch-image}.bicep
azure.yaml, Dockerfile, requirements.txt
tests/{test_core.py,test_rules.py}   # 단위 테스트 44개
.github/workflows/ci.yml              # CI: pytest, az bicep build
```

아래층은 위층을 import하지 않는다. 모듈별 불변 규칙은 TRD 본문(3.2절 상태 쓰기 주체와 이벤트 경로, 3.3절 ID 계약과 단일 판정 원천, 3.5절 승인 뒤 코드 확정, 11절 모듈 의존 방향)을 따른다.

테스트(MAF·네트워크 없이, `python -m pytest` 44개 통과): 가리기·OCR 숫자 보정 패턴, 한글 수사 정규화, 규칙 함수 경계값·판정 순서·평가 사례 기대값(긴급복지 위기 사유 조건, 이미 받는 제도 조건 포함), Verifier 대조 규칙과 보완·규칙 7 생략, 확정 문서 생성, 입력 검사. 제출 도구 거부 규칙과 권한 처리기는 테스트가 없다. GitHub Actions CI(`.github/workflows/ci.yml`)가 push·PR마다 pytest와 `az bicep build`를 실행한다.

배포 앱 E2E 확인(브라우저로 데모 사례를 승인까지 진행): 확정 문서 구획이 `[object HTMLHeadingElement]`로 찍히던 결함을 찾아 고쳤다(`el()`이 중첩 배열 자식을 끝까지 펼치도록 `children.flat(Infinity)`). 확정 뒤 상태 배지가 "확정 처리 중"에 머무는 결함도 고쳤다(SSE `finalized`·`approval_kept`가 승인 POST 응답보다 먼저 도착해 실행이 끝난 경우, 응답 처리가 끝난 상태를 덮어쓰지 않음). 두 결함은 단위 테스트 범위(서버 순수 코어) 밖이라 E2E 점검 항목으로 둔다(TRD 10절).

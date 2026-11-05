# SPEC — 동행노트

`PRD.md`와 `TRD.md`를 요약한 구현 명세다. 기준 문서는 PRD/TRD이며, 충돌하면 그쪽을 따른다.

## 1. 서비스 개요

- **정의:** 읍·면 행정복지센터 맞춤형복지팀 담당자가 방문 상담 메모를 붙여 넣으면, 개인정보를 가린 뒤 연계 가능한 복지 제도를 근거와 함께 찾고 상담기록지와 서비스 연계 의뢰서 초안을 만드는 웹 앱. 담당자 승인 후에만 문서가 확정된다.
- **사용자:** 청도군 맞춤형복지팀 담당 공무원(수혜자: 방문 상담 대상 가구).
- **문제:** 상담 1건당 문서 작업 약 55분(추정): 메모 정리, 제도 대조, 의뢰서 작성, 후속 질문 정리.
- **원칙:** AI는 자격을 판정하지 않는다. 판정은 규칙 함수가 하고, AI는 사실 구조화·우선순위 선정·설명·초안·질문 생성만 한다. 도구 결과와 맞지 않는 추천은 검증에서 제거된다.
- **범위 제외:** 사회보장정보시스템 연동, 실제 개인정보 저장, 사용자 계정, 신청서 자동 제출.

## 2. 사용자 흐름

1. "데모 사례로 시작" 또는 메모 직접 입력(로그인 없음)
2. 개인정보 가리기 전/후 표시
3. 타임라인 진행: 사실 구조화 → 분야별 매칭(3개 병렬) → 근거 검증 → 문서 초안
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
| F9 | 후속 질문 | 같은 세션 맥락 유지 | 선택 |
| F10 | 평가 실행 | 5건 실처리, 재현율·정밀도·근거 일치율·처리 시간·가리기 재현율 표시 | 필수 |
| F11 | 실행 재생 | 한도 초과·지연 시 저장된 실행을 "저장된 실행 재생"으로 표시 | 필수 |

## 4. 제도(13개, `data/schemes.json`)

- 생계·주거: 생계급여, 주거급여, 긴급복지 생계지원, 에너지바우처
- 건강·의료: 의료급여, 본인부담 경감(차상위), 장애인연금, 건강검진·방문건강관리
- 돌봄·고립·일자리: 기초연금, 노인맞춤돌봄서비스, 응급안전안심서비스, 노인일자리(공익활동), 고독사 예방 안부 확인

항목: `id`, `name`, `domain`, `summary`, `rules`, `required_fields`, `source_url`, `checked_at`, `is_example: true`. 소득인정액 계산은 단순화하고 화면·데이터에 표기한다.

## 5. 데이터 모델

`CaseProfile`: `age`, `household_type`(독거/부부/조손/한부모/기타), `household_size`, `monthly_income_krw`, `assets_krw`, `disability`, `chronic_illness`, `housing`, `monthly_rent_krw`, `caregiver_available`, `isolation_signals`, `crisis_events`, `missing_fields`.

규칙 함수 필수 필드 6개: `age`, `household_type`, `household_size`, `monthly_income_krw`, `disability`, `housing`.

평가 사례(`data/eval_cases.json`) 5건: ① 저소득 독거노인 ② 고령 부부·소득 누락 ③ 장애인 가구 ④ 실직 위기 가구 ⑤ 인젝션 포함 사례. 필드: `note`, `expected_profile`, `expected_eligible/unknown/ineligible`, `pii_spans`.

## 6. 워크플로와 도구

`Intake`(가리기, 코드) → `Profiler`(AI) → 매칭 ×3(AI+도구, fan-out) → `Verifier`(코드, fan-in) → `Documenter`(AI) → `ReferralGate`(승인 대기, `request_info`)

| 도구 | 사용처 | 동작 |
|---|---|---|
| `record_case_profile` | Profiler | 프로필 저장, 누락 필드 반환 |
| `search_schemes` | 매칭 | 분야별 제도 목록 |
| `check_eligibility` | 매칭 | 서버가 실행 상태의 프로필로 규칙 판정(`eligible`/`ineligible`/`unknown`, `decision_id`) |
| `lookup_decision` | Documenter | 같은 실행의 판정 기록 읽기 전용 조회 |

**Verifier 규칙:** (1) `scheme_id`·`decision_id` 필수 (2) 판정 기록과 일치 (3) `condition_ids`가 기록의 조건에 존재 (4) 불일치 시 제거 후 `removed`에 이유 기록 (5) `unknown`은 "확인 필요" (6) 에이전트가 건너뛴 제도는 규칙 함수로 직접 채움 (7) 모델이 실제로 받지 않은 `decision_id` 인용 시 제거(감사 기록이 비면 생략).

## 7. API

| 경로 | 설명 |
|---|---|
| `GET /` | UI |
| `GET /api/cases` | 데모 사례 목록 |
| `POST /api/runs` | `{note \| case_id, mode}` → `{run_id}` |
| `GET /api/runs/{id}/events` | SSE, `Last-Event-ID` 재접속, 15초 heartbeat |
| `POST /api/runs/{id}/approval` | `{request_id, approved, edited_sections}` |
| `POST /api/runs/{id}/ask` | 후속 질문(SSE) |
| `POST /api/eval` | `{eval_id}` 반환 |
| `GET /api/eval/{id}/events` | 평가 진행 SSE |
| `GET /healthz`, `GET /readyz` | 상태(`/readyz`는 시작 시 결과 캐시) |

SSE 이벤트: `masked`, `step_started`, `step_completed`, `token`, `tool_call`, `tool_result`, `usage`, `verified`, `draft`, `approval_required`, `finalized`, `error`, `heartbeat`, `done`.

## 8. 비기능 요구사항

- **성능:** 1건 90초 이내, 모델 호출 45초 제한 후 1회 재시도, 동시 실행 4건.
- **성공 지표:** 재현율 ≥90%, 정밀도 ≥90%, 근거 일치율 100%, 가리기 잔존 0건·가리기 재현율 100%.
- **신뢰성:** 429·할당량 초과 시 저장된 실행 재생(`data/replays/*.json`). 직접 입력은 재생 없이 오류·재시도 버튼.
- **보안:** IP별 분당 5회, 입력 4,000자 제한, `/api/eval` 전역 동시 1건·분당 1회, 내장 도구 숨김 + 권한 허용 목록, 메모는 `<case_note>` 데이터로만 취급, 토큰은 Key Vault, 저장 없음(30분 후 삭제).
- **접근성:** `aria-live="polite"`, 키보드 조작, 명도 대비 4.5:1 이상, 색+글자 배지.
- **책임 있는 AI:** 상단 배너(합성 데이터 전용, AI 초안, 담당자 검토 필요), 모든 AI 문장에 "AI 초안" 표시, 제도 데이터는 예시임을 표시.

## 9. 기술 스택과 배포

- Python 3.12, FastAPI, Uvicorn, `agent-framework-core==1.24.0`, `agent-framework-github-copilot==2.1.1`, `github-copilot-sdk==1.0.28`, OpenTelemetry, 정적 HTML/바닐라 JS, SSE.
- Azure Container Apps(최소·최대 복제본 1), ACR, Key Vault, Application Insights. `azd up` + Bicep.
- 구조화 출력은 `response_format` 미지원이므로 도구 인자(Pydantic)로만 받는다.

## 10. 구현 순서

1. 최소 샘플로 라이브러리 시그니처 확인
2. 빈 FastAPI 앱 `azd up` 배포
3. 직렬 실행으로 F1~F8 통과 (1차 제출 15:10)
4. 저장된 실행 재생 파일 생성(F11)
5. 매칭 병렬화
6. 평가 실행(F10)
7. 문서 확정, PRD/TRD 동기화 (최종 제출 16:20)

**자르는 순서(시간 부족 시):** 가용성 테스트 → 세션 훅 → `VerifiedDecisionsProvider` → 거부 후 재승인 → F9 → 병렬화. F1~F8, F10, F11은 유지한다.

## 11. 저장소 구조

```text
app/{main,workflow,agents,tools,context,rules,masking,telemetry}.py
app/static/{index.html,app.js,style.css}
data/{schemes.json,eval_cases.json,replays/}
docs/{reference/,eval-result.md}
infra/main.bicep, azure.yaml, Dockerfile, requirements.txt
tests/
```

테스트: 가리기 패턴, 규칙 함수 경계값, Verifier 대조 규칙, 권한 처리기 허용 목록.

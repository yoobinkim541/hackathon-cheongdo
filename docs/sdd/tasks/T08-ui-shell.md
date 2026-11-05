---
id: T08
title: UI 골격, API 클라이언트, 단계 타임라인
sprint: S1
priority: P0
cut_rank: 0
deps: [T00]
owns: [app/static/index.html, app/static/style.css, app/static/js/app.js, app/static/js/api.js, app/static/js/timeline.js, app/static/dev/, tests/test_static_shell.py]
verify: ["python -m pytest -q tests/test_static_shell.py"]
features: [F1, F2]
flag: null
---

# T08 — UI 골격

## 목표

빌드 단계 없는 정적 UI의 뼈대를 만든다: 첫 화면, 세 구획 배치, 반응형·접근성 기본, SSE 클라이언트, 단계 타임라인. 백엔드 없이도 개발할 수 있게 가짜 이벤트 재생기를 둔다.

## 근거

- TRD 9절 전체, 5절 SSE 봉투와 표 5
- PRD 1.1절(심사 에이전트용 빠른 시작), 3절 사용자 흐름 1~3
- Figma UI 시안(README 링크)

## 계약

- `index.html`: 고정 배너 → 한 줄 소개 → 주 버튼 "데모 사례로 시작"과 사례 목록 → 보조 버튼 "직접 입력"·"평가 실행". 세 구획 `#input`, `#timeline`, `#results`, 평가 구획 `#eval`(숨김). 모듈 `<script type="module" src="/static/js/app.js">`.
- `api.js` 내보내기: `getCases()`, `getFeatures()`, `startRun({note|case_id, mode})`, `startUpload(file, kind)`, `openEvents(runId, onEnvelope, onState)`, `sendApproval(runId, body)`, `ask(runId, question)`, `startEval()`, `openEvalEvents(evalId, onEnvelope, onState)`. `openEvents`는 `EventSource`를 쓰고, 끊기면 상태 `"reconnecting"`, 다시 받으면 `"open"`, `done`을 받으면 닫는다. `replaced`를 받으면 새 `run_id`로 다시 연다.
- `app.js`: `bus = new EventTarget()`. 봉투마다 `bus.dispatchEvent(new CustomEvent(env.type, {detail: env}))`. `features = await getFeatures()`(실패하면 모두 꺼짐). 다른 모듈의 `mount({bus, api, features})`를 모두 부른다(`timeline`, `results`, `drafts`, `eval`, `ask`, `media`).
- `timeline.js`: `step_started`·`step_completed`·`step_failed`·`step_retry`·`tool_call`·`tool_result`·`usage`·`token`·`masked`를 받아 단계별 행(이름, 스피너, 경과 시간, 토큰 수, 도구 호출 목록)을 그린다. 병렬 단계(`match_*`)는 같은 줄에 세 칸. `masked`는 가리기 전/후를 나란히 보인다.
- `app/static/dev/fake-events.json`과 `?fake=1` 쿼리: 저장된 봉투를 시간 간격대로 `bus`에 흘린다(백엔드 없이 UI 확인용).

## 동작

- 768px 이하에서 세 구획을 세로로 쌓고, 버튼·탭 터치 영역 44px 이상. 명도 대비 4.5:1 이상, 배지는 색과 글자를 함께.
- 진행 상태 영역 `aria-live="polite"`. 단계가 끝나면 포커스를 결과 구획 제목으로.
- `step_failed`를 받은 단계는 이후 `step_completed`로 덮어쓰지 않는다. `step_retry`는 그 단계 토큰 표시를 비운다.
- 재연결 중이면 타임라인 위에 "연결이 끊겨 다시 연결하는 중"을 띄운다.
- 재생 모드(`env.mode === "replay"`)면 상단 고정 배지 "저장된 실행 재생".
- 입력 오류 문구는 TRD 9절 "오류·지연"의 문장을 그대로 쓴다.
- 외부 CDN을 쓰지 않는다.

## 수용 기준(테스트: HTML·JS 정적 검사)

1. `index.html`에 배너 문구("합성 데이터 전용", "AI 생성 초안", "담당자 검토")가 있다.
2. `#input`, `#timeline`, `#results`, `#eval`과 `aria-live="polite"` 요소가 있다.
3. `style.css`에 `max-width: 768px` 미디어 쿼리와 `min-height: 44px`가 있다.
4. `api.js`가 계약의 9개 함수를 `export`한다.
5. `app.js`가 6개 모듈의 `mount`를 import한다.
6. `dev/fake-events.json`이 봉투 형식(`seq`, `type`, `step`, `mode`, `data`)의 배열이고 `step_started`부터 `approval_required`까지 있다.
7. 정적 파일에 `http://`·`https://` 외부 스크립트 참조가 없다.

## 하지 않는 것

- 결과·초안·승인(T19), 평가 화면(T15), 후속 질문(T17), 사진·음성 탭(T22).

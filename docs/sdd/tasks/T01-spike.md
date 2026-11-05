---
id: T01
title: 최소 샘플로 라이브러리 동작 확인
sprint: S0
priority: P0
cut_rank: 0
deps: []
owns: [docs/eval-result.md]
verify: ["python -c \"import pathlib,sys; t=pathlib.Path('docs/eval-result.md').read_text(encoding='utf-8'); sys.exit(0 if t.count('| Q')>=6 else 1)\""]
features: [F4, F8, F12, F13]
flag: null
---

# T01 — 스파이크

## 목표

TRD·스파인이 가정한 라이브러리 동작 6가지를 실제로 실행해 확인하고, 결과를 `docs/eval-result.md` 1절에 표로 남긴다. 결과가 가정과 다르면 해당 태스크가 고를 대안을 함께 적는다.

## 근거

- TRD 1절 마지막 문단, 3.6절, 3.9절
- 스파인 Open Questions 표(6개)

## 계약

- 샘플 코드는 저장소 밖(OS 임시 디렉터리)에 둔다. 저장소에는 결과 문서만 남긴다.
- `docs/eval-result.md` 1절 형식:

```markdown
## 1. 최소 샘플 확인

| ID | 질문 | 결과 | 근거(출력 요약) | 영향 태스크 |
|---|---|---|---|---|
| Q1 | `@response_handler` 안에서 `request_info` 재요청 | 됨/안 됨 | ... | T18 |
```

## 동작(확인 항목)

| ID | 확인 | 안 되면 적을 대안 |
|---|---|---|
| Q1 | `@response_handler` 안에서 `ctx.request_info`를 다시 걸 수 있다 | T18은 `drafted`로 끝낸다 |
| Q2 | `WorkflowContext[Out, AgentResponseUpdate \| UiEvent]` 합집합 출력이 받아들여진다 | T11은 에이전트 갱신도 `UiEvent(token…)`로 감싼다 |
| Q3 | 스트림에 모든 도구 호출의 `function_result`가 온다 | 규칙 7이 `complete=False`로 건너뛴다(코드 변경 없음) |
| Q4 | `default_options`의 `available_tools`·`hooks`가 `create_session`에 도달해 내장 도구가 숨겨진다 | T10은 권한 거부만으로 막고 README에 적는다 |
| Q5 | `system_message` `replace`에서도 도구 호출이 된다 | T10은 `customize` + `environment_context` 제거 |
| Q6 | 한국어 빠른 전사 + 화자 분리(2명) | T20은 `STT_DIARIZATION`을 무시하고 분리 없이 전사 |

추가로 1줄씩 적는다: 사용할 `COPILOT_MODEL` ID와 `supported_reasoning_efforts`, `GitHubCopilotAgent` 스트림 1회 소요 시간, Document Intelligence `prebuilt-read` 한국어 손글씨 1장 결과 글자 수.

## 수용 기준

- `docs/eval-result.md`에 Q1~Q6 행이 모두 있고 "결과" 칸이 비어 있지 않다.
- 가정과 다른 항목은 "영향 태스크" 칸의 태스크 문서에 대안이 이미 적혀 있다(위 표). 표에 없는 새 차이가 나오면 `docs/sdd/requests/T01-<이름>.md`를 쓴다.
- 토큰·키·로컬 경로를 문서에 적지 않는다.

## 하지 않는 것

- 앱 코드 작성. Q6에 Azure AI Services가 아직 없으면 그 행만 "보류"로 두고, T02가 리소스를 만든 뒤 오케스트레이터가 채운다.

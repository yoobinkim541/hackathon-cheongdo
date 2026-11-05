---
id: T17
title: 후속 질문(F9)
sprint: S3
priority: P1
cut_rank: 7
deps: [T16, T19]
owns: [app/ask.py, app/static/js/ask.js, tests/test_ask.py]
verify: ["python -m pytest -q tests/test_ask.py"]
features: [F9]
flag: ENABLE_ASK
---

# T17 — 후속 질문

## 목표

같은 상담 맥락에서 "기초연금은 왜 확인 필요야?" 같은 질문에 판정 기록을 근거로 답한다. 워크플로 밖에서 에이전트를 부르는 유일한 경로다.

## 근거

- PRD 3절 7번, 4절 F9
- TRD 3.2절 후속 질문 문단, 5절 `/ask` 행, 9절 추가 질문 칩
- 스파인 AD-7(`/ask` 조건), AD-8(`map_agent_update`), AD-11(`known=run.pii_map`)

## 계약

- `answer(service, run, question, ask_id)`:
  1. `masking.mask(question, "text", known=run.pii_map)`. 잔존 개인정보가 있으면 `error`를 쌓고 끝낸다. 질문에서 새로 찾은 항목은 저장하지 않는다.
  2. `call_agent(agents["documenter"], prompts.ask_prompt(masked), run, "documenter", emit=..., phase="ask")`. `emit`은 `events.map_agent_update(update, "ask", ask_id)` 결과를 `run.log.append`.
  3. 끝나면 `run.ask_busy = False`. 쓰기 도구는 `phase="ask"`라서 거부된다(T09).
- `ask.js` `mount(ctx)`: `features.ask`가 거짓이거나 재생 모드면 아무것도 그리지 않는다. "확인 필요" 항목마다 칩 두 개("왜 확인 필요인가요?", "조건이 바뀌면?") + 자유 질문 입력. `token{ask_id}`를 그 질문 아래에 이어 붙인다.

## 수용 기준(테스트)

1. 질문 속 메모와 같은 이름이 같은 자리표시자로 가려져 프롬프트에 들어간다.
2. 질문에 새 전화번호 → 가려지고 `run.pii_map`이 바뀌지 않는다.
3. `call_agent`가 `phase="ask"`로 불린다.
4. 이벤트의 `step`이 `ask`이고 `data.ask_id`가 있다.
5. 답변 중 가짜 에이전트가 `submit_draft`를 부르면 거부되고 `run.draft`가 그대로다.
6. 완료 뒤 `ask_busy`가 거짓.

## 하지 않는 것

- `/ask` 라우트·409 조건(T12), 문서 수정(질문은 읽기 전용).

---
id: T14
title: 저장된 실행 재생과 재생 파일 생성
sprint: S3
priority: P0
cut_rank: 0
deps: [T12, T07]
owns: [app/replay.py, scripts/record_replay.py, data/replays/, tests/test_replay.py]
verify: ["python -m pytest -q tests/test_replay.py"]
features: [F11]
flag: null
---

# T14 — 재생

## 목표

호출 한도 초과나 지연 때 데모 사례를 "저장된 실행 재생"으로 보여 준다. 재생 파일은 실제 실행에서 기록한다.

## 근거

- TRD 3.5절 7번, 7절 "재생 파일 형식"
- 스파인 AD-9 전체, AD-10 "재생 전환"
- PRD 4절 F11, 5절(재생 결과는 지표 평균에서 뺀다)

## 계약

- `load_replay(case_id) -> ReplayFile`: `data/replays/{case_id}.json`. 없으면 `FileNotFoundError`(서비스가 `error`로 바꾼다).
- `to_replay_file(case_id, envelopes, run) -> ReplayFile`: 봉투에서 `type`, `step`, `data`, `t_ms`(첫 이벤트 기준 상대 ms)만 남기고 `approval_required`까지 자른다. `snapshot = {verified, draft, approval_request}`. `finalized`는 담지 않는다.
- `play(service, run, replay)`: `run.verified`·`run.draft`·`run.pending_request`를 스냅샷으로 채우고 `pending_request_id`는 새 UUID. 이벤트를 `t_ms` 간격(최대 간격 1.5초로 눌러 담는다)대로 `run.log.append(..., mode="replay")`. `approval_required` 이벤트의 `request_id`는 새 ID로 바꿔 쌓는다. 끝나면 상태 `awaiting_approval`.
- `scripts/record_replay.py`: 로컬에서 `RunService`를 직접 써서 `case1`~`case5`를 실시간 실행하고(실제 Copilot 토큰 필요), `approval_required`에 이르면 `to_replay_file`로 저장한다. 실행은 사람이 G1 직후에 한다.

## 동작

- 재생 이벤트 `data`는 실제 실행과 같은 모델로 검증된다(`schemas`). 이벤트 데이터 모델이 바뀌면 파일을 다시 만든다.
- 재생 실행에는 Documenter 세션이 없으므로 `/ask`는 409(T12).

## 수용 기준(테스트)

1. 가짜 봉투 목록 → `to_replay_file`이 `approval_required` 뒤를 자르고 `finalized`가 없다.
2. `ReplayFile` JSON 왕복이 같다.
3. `play`가 모든 이벤트를 `mode="replay"`로 쌓고, 상태가 `awaiting_approval`, `pending_request_id`가 원본과 다르다.
4. `play` 뒤 `RunService.respond` 승인 → `render_final`로 `finalized`(T12 경로).
5. `data/replays/`에 파일이 있으면 5개 모두 `ReplayFile`로 읽히고 각 파일에 `approval_required`가 있다. 없으면 이 검사는 `skip`.
6. 재생 이벤트 사이 간격이 1.5초를 넘지 않는다(가짜 시계).

## 배포 확인(G2)

- `data/replays/case1~5.json`이 이미지에 들어 있고, `mode=replay`로 사례 1을 시작하면 상단에 "저장된 실행 재생"이 보이며 승인까지 된다.

## 하지 않는 것

- 재생 전환 판단(T12), 평가 대체(T15가 이 모듈을 부른다).

---
id: T13
title: 분야별 매칭 병렬화(fan-out/fan-in)
sprint: S3
priority: P1
cut_rank: 10
deps: [T12]
owns: [app/workflow.py, tests/test_workflow_parallel.py]
verify: ["python -m pytest -q tests/test_workflow_parallel.py tests/test_workflow.py"]
features: [F4]
flag: MATCH_PARALLEL
---

# T13 — 병렬 매칭

## 목표

`settings.MATCH_PARALLEL`이 참이면 매칭 3개를 `add_fan_out_edges(profiler, matchers)`·`add_fan_in_edges(matchers, verifier)`로 잇는다. 실행기 코드는 바꾸지 않는다(T11이 `ProfileReady` 핸들러를 이미 만들었다). 거짓이면 T11의 직렬 간선을 그대로 쓴다.

## 근거

- TRD 3.1절 매칭 행, 3.2절 코드, PRD 4절 F4
- 스파인 AD-7(간선만 바꾼다)

## 계약

- `build_workflow`의 `NotImplementedError("T13")` 분기만 채운다. 다른 분기·실행기는 건드리지 않는다.
- fan-in 메시지 순서는 `add_fan_in_edges`에 나열한 순서(`living`, `health`, `care`).

## 수용 기준(테스트)

1. `MATCH_PARALLEL=True` + 가짜 에이전트(각 매칭이 0.2초 걸림) → 매칭 세 단계의 `step_started`가 모두 첫 `step_completed`보다 먼저 나온다.
2. 한 분기 실패 → 나머지 두 분기 결과로 Verifier가 실행되고 `failed_domains`에 그 분야. 워크플로 전체가 실패하지 않는다.
3. Verifier가 받는 목록 순서가 `living, health, care`.
4. `tests/test_workflow.py`(직렬)가 여전히 통과한다.
5. 병렬과 직렬의 최종 `VerifiedResult`가 같은 가짜 입력에서 같다.

## 배포 확인(G2, 오케스트레이터)

- `MATCH_PARALLEL=true`로 배포 후 사례 1 전체 시간이 직렬보다 짧거나 같고, 타임라인에 세 칸이 동시에 진행된다. 불안정하면 플래그를 끈다(cut_rank 10).

## 하지 않는 것

- `asyncio.gather` 같은 직접 병렬화(AD-7 금지).

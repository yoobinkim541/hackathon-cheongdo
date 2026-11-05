---
id: T24
title: 지표 기록과 문서 동기화(최종 제출 준비)
sprint: S5
priority: P0
cut_rank: 0
deps: [T15, T19, T01]
owns: [docs/eval-result.md, README.md, PRD.md, TRD.md, SPEC.md]
verify: ["python -m pytest -q", "python scripts/sdd.py lint"]
features: [F10]
flag: null
---

# T24 — 마감 문서

## 목표

실측 결과를 기록하고, 잘린 기능과 실제 구현에 맞춰 문서를 고친다. 코드 동결(G3) 뒤에 오케스트레이터나 사람이 한다.

## 근거

- PRD 5절(실측값은 목표 미달이어도 그대로, 스톱워치 측정)
- TRD 6절 "관측 범위", 10절 "평가 실행"·"배포 후 확인"
- SPRINTS.md 4절(꺼진 플래그 = 자른 기능)

## 동작

1. `docs/eval-result.md` 2절: 배포 앱 평가 실행 결과(사례별 라이브/재생, 지표, 단계별 시간), 3절: trace ID 예시와 span 목록, p50/p95, 4절: 수작업 스톱워치 측정(사례 1, 측정자 1인, 한계 명시)과 앱 처리 시간 비교.
2. 꺼진 플래그의 기능을 PRD 4절·TRD·SPEC·README에서 지우거나 "제외"로 표시한다. AI Services를 껐으면 README 구성·심사 기준 표에서도 뺀다.
3. PRD 5절 표 3의 "실측값" 칸을 채운다.
4. README에 배포 URL과 "심사 에이전트용 빠른 시작"(PRD 1.1) 링크를 둔다.
5. 로컬 경로·토큰·에이전트 이름이 문서에 없는지 확인한다.

## 수용 기준

- `python -m pytest -q` 전체 통과.
- `docs/eval-result.md`에 1~4절이 모두 있다.
- 켜진 플래그 목록과 문서에 남은 기능 목록이 같다.

## 하지 않는 것

- 최종 제출 뒤 재배포(AD-14).

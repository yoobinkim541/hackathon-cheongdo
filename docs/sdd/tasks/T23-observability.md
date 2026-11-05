---
id: T23
title: 관측 마무리와 가용성 테스트
sprint: S4
priority: P3
cut_rank: 1
deps: [T12, T02]
owns: [infra/modules/availability.bicep, app/telemetry.py, tests/test_telemetry.py]
verify: ["python -m pytest -q tests/test_telemetry.py"]
features: []
flag: null
---

# T23 — 관측·가용성

## 목표

실행마다 trace ID가 UI에 보이고 Application Insights에서 단계별 span을 찾을 수 있게 마무리한다. `/readyz` 표준 가용성 테스트를 Bicep 모듈로 채운다(매개변수 `enableAvailabilityTest`).

## 근거

- TRD 6절 Application Insights 행과 "관측 범위", 8절 "비밀"(민감 데이터 끔)
- 스파인 Conventions "텔레메트리"

## 계약

- `infra/modules/availability.bicep`: 표준 테스트, 5분 간격, 대상 `{SERVICE_WEB_URI}/readyz`, 지역 3곳. T02의 조건부 참조를 그대로 쓴다(그 파일은 고치지 않는다).
- `telemetry.py`: span 속성 `app.run_id`, `app.step`, `app.mode`, `app.verify.rule7_skipped`를 다는 헬퍼. 메모 원문·가린 값·토큰을 속성에 넣으려 하면 넣지 않는다(키 이름 허용 목록 방식). `current_trace_id()`는 32자리 16진수 또는 빈 문자열.

## 수용 기준(테스트)

1. 허용 목록 밖 속성 키(`app.note`)는 버려진다.
2. 연결 문자열이 없으면 `setup`이 아무것도 설치하지 않고 예외도 없다.
3. `enable_sensitive_telemetry`를 호출하지 않는다(정적 검사).

## 배포 확인(최종 전)

- trace ID 하나로 `workflow.run` → 실행기 → `invoke_agent` → `execute_tool` span이 보이고, 그 목록과 p50/p95를 T24가 `docs/eval-result.md`에 적는다.

## 하지 않는 것

- `infra/main.bicep` 수정(필요하면 요청), 경고 규칙·대시보드.

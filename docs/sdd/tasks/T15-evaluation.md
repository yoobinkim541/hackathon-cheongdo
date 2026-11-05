---
id: T15
title: 평가 실행(지표 계산, 평가 SSE, 평가 화면)
sprint: S3
priority: P0
cut_rank: 0
deps: [T12, T14]
owns: [app/evaluation.py, app/static/js/eval.js, tests/test_evaluation.py]
verify: ["python -m pytest -q tests/test_evaluation.py"]
features: [F10]
flag: null
---

# T15 — 평가

## 목표

"평가 실행"으로 정답이 있는 사례 5건을 실제로 처리하고, 재현율·정밀도·근거 일치율·처리 시간·가리기 지표·자동 채움·보완 건수·CER을 보인다. 재생으로 처리한 사례는 평균에서 빼고 따로 표시한다.

## 근거

- PRD 4절 F10, 5절 표 3·표 4와 아래 문단
- TRD 4.3절(지표 정의), 7절 평가 문단
- 스파인 AD-8 "평가", AD-10 "평가"

## 계약

- `load_cases() -> list[EvalCase]`.
- `case_metrics(case, run, replayed) -> CaseMetrics`(순수 계산):
  - 재현율·정밀도·근거 일치율: TRD 4.3 정의. 최종 결과는 `run.verified`.
  - `step_ms`: `run.timings`, `total_ms`: 첫 이벤트부터 `approval_required`까지.
  - 가리기: `pii_recall`(`pii_spans` 중 `run.pii_map`에 가려진 비율), `pii_false_positives`, `pii_residual`(`masking.residual_pii(run.masked_note)` 개수).
  - `autofilled_fields`·`manual_fields`: 프로필의 필드 중 `None` 아닌 수·`None`인 수.
  - `supplemented`: `len(run.verified.supplemented)`.
  - `cer`·`required_field_matches`: 사례 2·4만. CER = 공백 뺀 인식 텍스트와 `reference_text`의 편집 거리 ÷ 정답 글자 수.
- `summarize(metrics) -> EvalSummary`: 재생 사례를 뺀 평균, p50·p95, 라이브/재생 건수.
- `run_eval(service, eval_state)`: 사례를 `EVAL_CONCURRENCY`(2)건씩 `service.start(RunInput, purpose="eval")`. 사례는 `approval_required`나 `failed`에 이르면 끝. 실패·`EVAL_DEADLINE_S`(6분) 초과 사례는 `replay.load_replay`의 스냅샷으로 지표를 계산하고 `replayed=True`. `eval_state.log`에 `case_started`, `case_completed`(`CaseMetrics`), 마지막에 `eval_summary`, `done`. 끝난 사례 실행은 바로 지운다.
- `eval.js` `mount(ctx)`: "평가 실행" → `api.startEval()` → `openEvalEvents`. 사례별 행(라이브/재생 배지, 단계별 시간 막대, 지표), 요약(목표 대비, 라이브/재생 비율). 목표 미달도 그대로 보인다.

## 수용 기준(테스트)

1. 기대 집합과 같은 결과 → 재현율·정밀도 1.0.
2. `expected_unknown` 제도가 `ineligible`로 나오면 재현율이 그만큼 떨어진다.
3. `eligible` 중 기대 밖 제도 → 정밀도가 떨어진다.
4. `pii_spans` 3개 중 2개만 가려짐 → `pii_recall == 2/3`.
5. CER: 정답 "가나다라", 인식 "가나다" → 0.25. 공백 차이는 무시.
6. `summarize`가 재생 사례를 평균에서 빼고 `replay_count`에 센다.
7. 가짜 서비스로 `run_eval` → 이벤트가 `case_started`×5, `case_completed`×5, `eval_summary`, `done` 순서 규칙을 지킨다(사례 간 섞임은 허용).
8. 한 사례 실패 → 그 사례 `replayed=True`.

## 배포 확인(G2)

- 배포 앱에서 평가 실행이 6분 안에 끝나고, 결과를 `docs/eval-result.md` 2절에 옮긴다(T24).

## 하지 않는 것

- 평가 정답 작성(T07), 평가 동시성·속도 제한(T12).

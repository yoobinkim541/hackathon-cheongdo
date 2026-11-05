---
id: T11
title: 워크플로 그래프와 핵심 실행기(텍스트 경로, 매칭 직렬, 1회 승인)
sprint: S2
priority: P0
cut_rank: 0
deps: [T04, T05, T06, T10]
owns: [app/workflow.py, app/executors/__init__.py, app/executors/core.py, app/executors/gate.py, tests/test_workflow.py]
verify: ["python -m pytest -q tests/test_workflow.py"]
features: [F2, F3, F4, F5, F6, F7, F8]
flag: null
---

# T11 — 워크플로

## 목표

MAF `WorkflowBuilder`로 상담 1건의 전체 그래프를 만든다. 이 태스크는 텍스트 경로를 끝까지 동작시키고, 매칭은 직렬 간선으로, 승인은 1회만 받는다. 사진·음성 실행기(T21), 병렬 간선(T13), 재승인(T18)이 들어올 자리는 그래프에 미리 둔다.

## 근거

- TRD 3.1절 표 2, 3.2절 전체, 3.4절, 3.5절 1~4번
- 스파인 AD-6(Verifier 순서), AD-7, AD-8(실행기 출력 타입), AD-10(실패 처리), AD-11, AD-13
- T01 결과 Q1·Q2

## 계약

- `build_workflow(run, agents, settings) -> Workflow`: 실행마다 새로 만든다. 실행기 ID는 AD-3 단계 이름.
  - `input_router` switch-case: `source == "image"`이고 `settings.ENABLE_IMAGE_INPUT` → `ocr`, `source == "audio"`이고 `ENABLE_AUDIO_INPUT` → `stt`, 기본 → `intake`. 플래그가 꺼져 있으면 `ocr`·`stt` 실행기를 그래프에 넣지 않는다.
  - `intake` → (`source != "text"`면 `normalizer`) → `profiler`.
  - 매칭: `settings.MATCH_PARALLEL`이 거짓이면 `profiler → match_living → match_health → match_care → verifier` 직렬(`MatchChain`), 참이면 fan-out/fan-in. 이 태스크는 직렬만 테스트하고, 참 분기는 `NotImplementedError("T13")`로 둔다.
  - `verifier → documenter → referral_gate`. `intermediate_output_from`은 게이트를 뺀 전부, `output_from=[referral_gate]`.
- `executors/core.py`:
  - `InputRouter`: `RunInput`을 그대로 넘긴다.
  - `IntakeExecutor`: 핸들러 두 개. `RunInput`(텍스트, 또는 플래그가 꺼져 `note`로 실행하는 사진·음성 사례)과 `RecognizedText`(T21의 OCR·STT 결과). 둘 다 `masking.mask(text, source, None)`. `residual`이 있으면 `UiEvent("error", "intake", {code:"pii_residual", ...})`를 내고 멈춘다. 아니면 `run.masked_note`·`run.pii_map`을 쓰고 `UiEvent("masked", ...)`를 낸 뒤 `MaskedNote` 전송. 원문은 이벤트에 `before`로만 넣는다(브라우저 표시용, 로그·span에는 남기지 않는다).
  - `ProfilerExecutor`: `call_agent(agents["profiler"], prompts.profiler_prompt(...), run, "profiler", emit=ctx.yield_output)`. 성공해도 `run.profile`이 없으면 실패로 본다. 실패하면 `UiEvent("error", "profiler", {code, retryable})`를 내고 멈춘다(재생 전환 판단은 T12). 성공하면 `ProfileReady`.
  - `MatchExecutor(domain)`: 두 핸들러. `ProfileReady`(병렬용)와 `MatchChain`(직렬용). `call_agent` 뒤 `run.match_submissions.get(domain)`으로 `MatchResult`를 만들고, 호출 실패·제출 없음이면 `status="failed"`와 `UiEvent("step_failed", ...)`. 직렬이면 `MatchChain.results`에 붙여 다음 매칭이나(마지막이면) `verifier`에 `list[MatchResult]`로 보낸다. 예외를 간선 밖으로 던지지 않는다.
  - `VerifierExecutor`: AD-6 순서(`coverage_gaps` → 빠진 제도 `record_decision(..., "verifier")` → `verify`). `run.verified` 저장, `UiEvent("verified", ...)`.
  - `DocumenterExecutor`: 공급자 플래그가 꺼져 있으면 판정 목록 텍스트를 프롬프트에 직접 넣는다. 성공하면 `UiEvent("draft", ...)`와 `DraftReady`. 실패하면 `error`.
- `executors/gate.py` `ReferralGate`:
  - `DraftReady`를 받으면 `ApprovalRequest(run_id, scheme_ids=eligible ∪ needs_check, documents_summary, draft_snapshot=draft.model_copy(deep=True))`로 `ctx.request_info(..., ApprovalDecision)`.
  - `@response_handler`: 승인이면 `render.render_final(...)` → `run.final_documents` → `UiEvent("finalized", ...)`를 `yield_output`. 거부면 `UiEvent("approval_kept", ...)`를 내고 끝낸다(재승인은 T18, 플래그 `ENABLE_REAPPROVAL`).
- 실행기 예외 처리는 `except Exception`까지. `CancelledError`는 잡지 않는다.

## 수용 기준(테스트: `tests/fakes.py`의 가짜 에이전트, 네트워크 없음)

1. 텍스트 사례 1 + 가짜 에이전트(각 단계 제출 도구를 정상 호출) → 이벤트 순서에 `masked`, `step_started(profiler)`, `verified`, `draft`, `request_info`가 이 순서로 있다.
2. `request_info` 응답 승인 → `finalized`가 `output`으로 나오고 `run.final_documents`가 9개 구획.
3. 거부 → `approval_kept`, `final_documents is None`.
4. 가리기 잔존(가짜 `mask`가 `residual` 반환) → `error(pii_residual)`, 프로필러가 호출되지 않는다.
5. 프로필러 가짜가 제출하지 않음 → `error`, 매칭이 호출되지 않는다.
6. `match_health` 가짜가 실패 → `step_failed(match_health)`, Verifier가 그 분야 제도를 `source="verifier"`로 채우고 `failed_domains == ["health"]`.
7. 매칭 가짜가 13개 중 일부만 판정 → `supplemented`에 나머지가 있다.
8. `ENABLE_IMAGE_INPUT=False`에서 `source="image"` 입력 → `intake`로 간다(`note` 텍스트 사용).
9. 모든 실행기 ID가 AD-3 단계 이름이다.

## 하지 않는 것

- 실행 진입·상태 전이·재생 전환(T12), 병렬(T13), 재승인(T18), OCR·STT·정리 실행기(T21).

---
id: T21
title: OCR·STT 실행기와 NoteNormalizer 실행기
sprint: S4
priority: P2
cut_rank: 5
deps: [T11, T20]
owns: [app/executors/media.py, tests/test_media.py]
verify: ["python -m pytest -q tests/test_media.py"]
features: [F12, F13, F14]
flag: ENABLE_IMAGE_INPUT
---

# T21 — 미디어 실행기

## 목표

`ocr`·`stt`·`normalizer` 실행기를 채운다. 그래프 연결은 T11이 플래그에 따라 이미 해 두었다.

## 근거

- TRD 3.1절 OCR·STT·NoteNormalizer 행, 3.9절 "NoteNormalizer"·"정리본 수정 후 재실행"
- 스파인 AD-4(`transcript`, `clean_note` 쓰는 주체), AD-6(`record_clean_note`), AD-11

## 계약

- `OcrExecutor`·`SttExecutor`: `RunInput.media`로 `ingest.ocr_image`·`transcribe_audio`. 성공하면 `run.transcript` 저장, `UiEvent("transcribed", step, {chars, uncertain, speakers, ms})`(인식 텍스트 자체는 넣지 않는다), `RecognizedText`를 `intake`로. 실패하면 `UiEvent("error", step, {code:"recognition_failed", message:"사진·녹음을 읽지 못했습니다. 텍스트로 입력하거나 다시 올려 주세요"})`. 음성 길이 초과도 같은 경로에 한도 문구.
- `IntakeExecutor`(T11)가 `RecognizedText`도 받는지 확인한다. 받지 않으면 요청을 낸다.
- `NormalizerExecutor`: `MaskedNote`를 받아 `call_agent(agents["normalizer"], prompts.normalizer_prompt(masked), run, "normalizer", emit=...)`. `record_clean_note`가 두 번 거부되거나 호출이 실패하면 정리를 건너뛰고 `UiEvent("step_failed", "normalizer", {code, message:"정리 생략", retryable:false})` + `UiEvent("normalized", ..., {skipped:true})` 뒤 가린 텍스트 그대로 `MaskedNote`를 `profiler`로. 성공하면 `normalized{clean_text, edits, uncertain, skipped:false}`와 정리본 `MaskedNote`.
- 원본 바이트는 실행기 처리 뒤 `RunInput.media = None`으로 버린다.

## 수용 기준(테스트: 가짜 ingest·가짜 에이전트)

1. 가짜 OCR 성공 → `transcribed` 데이터에 텍스트 본문이 없고, 다음 메시지가 `intake`로 간다.
2. 가짜 OCR 실패 → `error(recognition_failed)`이고 프로필러가 호출되지 않는다.
3. 정리 성공 → `normalized.skipped is False`, 프로필러가 정리본을 받는다.
4. 정리 2회 거부 → `step_failed(normalizer)`, `normalized.skipped is True`, 프로필러가 가린 원문을 받는다.
5. 처리 뒤 `RunInput.media is None`.

## 하지 않는 것

- 업로드 라우트(T12), 사진·음성 탭(T22), 정리본 수정 후 재실행 라우트(T12의 `origin_run_id`).

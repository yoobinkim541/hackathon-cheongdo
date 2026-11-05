---
id: T22
title: UI 사진·음성 탭, 인식 결과 대조, 브라우저 녹음
sprint: S4
priority: P2
cut_rank: 4
deps: [T19]
owns: [app/static/js/media.js, tests/test_static_media.py]
verify: ["python -m pytest -q tests/test_static_media.py"]
features: [F12, F13, F14]
flag: ENABLE_AUDIO_INPUT
---

# T22 — UI 사진·음성

## 목표

입력 구획에 "사진"·"음성" 탭을 더하고, 인식 원문(가린 뒤)과 정리본을 나란히 보여 준다. 브라우저 녹음은 별도 플래그(`ENABLE_BROWSER_RECORDING`, cut_rank 2) 뒤에 둔다.

## 근거

- PRD 3절 1번, 4절 F12~F14
- TRD 9절 "세 구획"·"인식 결과 확인"·"오류·지연"(마이크 권한 문구), 3.9절 녹음 120초 자동 정지

## 계약

- `media.js` `mount(ctx)`:
  - `features.image_input`이면 "사진" 탭(JPEG·PNG, 5MB 표시), `features.audio_input`이면 "음성" 탭(WAV·MP3·WebM, 2분·10MB 표시). 둘 다 거짓이면 아무것도 그리지 않는다.
  - 올리기 → `api.startUpload(file, kind)`. 크기는 보내기 전에 브라우저에서도 확인한다.
  - `features.browser_recording`이면 녹음 버튼(`MediaRecorder`, 120초에 자동 정지). 권한 거부 → "녹음 권한이 없어 파일 올리기를 이용하세요".
  - `masked`(사진·음성 실행)와 `normalized` 이벤트로 원문·정리본을 나란히. 불확실 구간은 밑줄 + "확인 필요" 글자, 바뀐 구간은 바꾸기 전 글을 함께. `skipped`면 "정리 생략".
  - 정리본 편집 후 "고친 내용으로 다시 실행" → `api.startRun({note, origin_run_id})`.

## 수용 기준(정적 검사)

1. `media.js`가 `features.image_input`·`features.audio_input`·`features.browser_recording`을 확인한다.
2. `MediaRecorder`와 120초(120000 또는 120) 정지 코드가 있다.
3. 마이크 권한 거부 문구가 TRD 9절과 같다.
4. `origin_run_id`를 보낸다.
5. "정리 생략", "확인 필요" 문자열이 있다.

## 하지 않는 것

- 서버 검사(T04·T12), 인식(T20·T21).

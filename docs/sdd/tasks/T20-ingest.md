---
id: T20
title: Azure OCR·STT 호출 함수
sprint: S4
priority: P2
cut_rank: 5
deps: [T00]
owns: [app/ingest.py, tests/test_ingest.py]
verify: ["python -m pytest -q tests/test_ingest.py"]
features: [F12, F13]
flag: ENABLE_AI_SERVICES
---

# T20 — OCR·STT 호출

## 목표

Document Intelligence `prebuilt-read`(사진)와 Speech 빠른 전사(음성)를 관리 ID로 호출해 `Transcript`를 돌려주는 함수를 만든다. 의존이 T00뿐이라 S1·S2에 손이 비는 워커가 먼저 가져가도 된다.

## 근거

- TRD 3.9절 "OCR 실행기"·"STT 실행기"·"원본 처리"·"관측", 6절 AI Services 행
- 스파인 AD-11(원본은 Azure로만), AD-15(`DefaultAzureCredential`, `AZURE_CLIENT_ID`)
- T01 결과 Q6

## 계약

- `ocr_image(data, media_type, settings) -> Transcript`: `DocumentIntelligenceClient(endpoint=settings.AZURE_AI_ENDPOINT, credential=DefaultAzureCredential())`로 `prebuilt-read`. 단어 신뢰도 `< OCR_MIN_CONFIDENCE`인 단어를 `uncertain` 구간으로. `speakers=None`.
- `transcribe_audio(data, media_type, settings) -> Transcript`: `httpx`로 `POST {endpoint}/speechtotext/transcriptions:transcribe?api-version=2025-10-15`, 헤더 `Authorization: Bearer <Entra 토큰(범위 https://cognitiveservices.azure.com/.default)>`, multipart `audio` + `definition`(`locales:["ko-KR"]`, `settings.STT_DIARIZATION`이면 `diarization:{maxSpeakers:2, enabled:true}`, 구문 목록: 제도 이름 13개와 "차상위", "기준 중위소득", "맞춤형급여"). 화자별 발화를 `"화자1: ..."` 줄로 이어 붙인다. `durationMilliseconds > MAX_AUDIO_MS`면 결과를 버리고 `ValueError("audio_too_long")`.
- `ai_token_ok(settings) -> bool`: 토큰 발급만 시도(인식 호출 없음).
- 원본 바이트를 디스크·로그·span에 남기지 않는다. span 속성은 성공 여부, 소요 ms, 글자 수, 불확실 구간 수만.
- 실패는 `RuntimeError("recognition_failed: <짧은 이유>")`로 올린다(실행기가 사용자 문구로 바꾼다).

## 수용 기준(테스트: Azure SDK·httpx 가짜, 네트워크 없음)

1. 가짜 OCR 결과(신뢰도 0.95, 0.5 단어) → `uncertain`에 0.5 단어 구간 하나.
2. 가짜 전사 응답(화자 2명) → 줄이 `"화자1:"`·`"화자2:"`로 시작, `speakers == 2`.
3. `STT_DIARIZATION=False` → 요청 `definition`에 `diarization`이 없다.
4. `durationMilliseconds = 130000` → `ValueError`.
5. 요청 `definition.phraseList`에 제도 이름 13개가 있다.
6. 가짜 HTTP 500 → `RuntimeError`이고 메시지에 원본 데이터가 없다.
7. `ingest.py`가 `open(`·`write_bytes`를 쓰지 않는다(정적 검사).

## 배포 확인(G3)

- `ENABLE_AI_SERVICES=true`, `ENABLE_IMAGE_INPUT=true` 배포에서 사례 2 사진이 인식되고 `transcribed` 이벤트가 온다. 음성은 `ENABLE_AUDIO_INPUT=true`로 사례 4.

## 하지 않는 것

- 실행기·가리기·정리(T21), 업로드 검사(T04·T12).

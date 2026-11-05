---
id: T04
title: 개인정보 가리기, 숫자 정규화, 입력 검사
sprint: S1
priority: P0
cut_rank: 0
deps: [T00]
owns: [app/masking.py, app/textnum.py, app/limits.py, tests/test_masking.py, tests/test_textnum.py, tests/test_limits.py]
verify: ["python -m pytest -q tests/test_masking.py tests/test_textnum.py tests/test_limits.py"]
features: [F2, F12, F13, F14]
flag: null
---

# T04 — 가리기·숫자·입력 검사

## 목표

모델로 가는 모든 사용자 유래 텍스트가 거치는 가리기(`masking`), OCR·STT 숫자 보정과 새 숫자 검사(`textnum`), API 입구 검사(`limits`)를 순수 함수로 만든다.

## 근거

- TRD 3.9절 "한계와 보정", 8절 "개인정보 가리기"·"업로드"
- 스파인 AD-11, Conventions "입구 검사"
- PRD 5절 "가리기 누락" 지표

## 계약

- `mask(text, source="text", known=None) -> MaskResult`
  - 종류(`kind`): `rrn`(주민등록번호), `phone`, `account`, `address`(번지·호수), `name`.
  - 자리표시자: `[이름1]`, `[전화1]`, `[주민번호1]`, `[계좌1]`, `[주소1]`. 같은 원문은 같은 자리표시자.
  - `known`(자리표시자→원문)이 있으면 같은 원문에 기존 자리표시자를 쓰고, 번호는 기존 최댓값 다음부터 매긴다.
  - `source="image"`면 먼저 `textnum.fix_ocr_digits`.
  - 결과의 `residual`은 가린 뒤 `residual_pii(masked_text)`.
- `residual_pii(text)`: 주민등록번호 형태, 10~11자리 연속 숫자, 계좌번호 형태를 찾는다.
- `fix_ocr_digits(text)`: 숫자 사이의 `O`·`o` → `0`, `l`·`I` → `1`.
- `parse_numbers(text) -> set[int]`: 아라비아 숫자(쉼표 포함)와 한글 수사("삼십만" → 300000, "칠십오" → 75, "팔만 오천" → 85000, "공일공" 같은 숫자 읽기는 자릿수 그대로)를 정수 집합으로.
- `new_numbers(original, cleaned)`: `parse_numbers(cleaned) - parse_numbers(original)`.
- `check_text(text)`: 빈 문자열 → `ApiError("input_invalid", "상담 메모를 입력하거나 데모 사례를 고르세요")`, 4,000자 초과 → 현재 글자 수와 한도를 담은 메시지.
- `sniff_media(data)`: 시그니처로 `image/jpeg`, `image/png`, `audio/wav`, `audio/mpeg`, `audio/webm` 중 하나 또는 `None`.
- `check_media(data, kind)`: 형식 불일치·크기 초과면 허용 형식과 한도를 담은 `ApiError`. 음성 길이는 여기서 보지 않는다(WAV 헤더 길이만 확인 가능하면 확인).
- `RateLimiter(per_min).allow(key, now)`: 슬라이딩 60초 창. 인스턴스 상태만 쓰고 모듈 전역 상태는 없다.

## 동작

- 이름은 호칭 앞 이름("○○ 어르신", "○○ 씨", "○○님", "○○ 할머니", "○○ 할아버지")과 모듈 상수 `DEMO_NAMES`(데모 사례에 나오는 합성 이름 목록)로 찾는다. `DEMO_NAMES`는 이 태스크가 TRD 4.3의 사례 구성에 맞춰 정하고, T07은 사례 메모에 이 목록의 이름만 쓴다.
- 전화번호는 하이픈 있음·없음, 한글 숫자 읽기("공일공 일이삼사 오육칠팔")를 모두 찾는다.

## 수용 기준(테스트)

1. `"김순자 어르신 010-1234-5678"` → 이름·전화가 가려지고 `residual == []`.
2. 하이픈 없는 `01012345678`과 `"공일공 일이삼사 오육칠팔"`이 `phone`으로 가려진다.
3. `"8001011234567"`과 `"800101-1234567"`이 `rrn`으로 가려진다.
4. `source="image"`의 `"O1O-l234-5678"`이 보정 뒤 가려진다.
5. 같은 이름이 두 번 나오면 자리표시자가 같다. `known={"[이름1]": "김순자"}`로 `"김순자 씨 아들"`을 가리면 `[이름1]`을 다시 쓴다.
6. 가리기 뒤 남은 11자리 숫자를 `residual_pii`가 찾는다.
7. `parse_numbers("월 삼십만 원, 칠십오 세")`에 300000과 75가 있다. `parse_numbers("1,200,000원")`에 1200000이 있다.
8. `new_numbers("나이 75", "나이 75, 소득 50만")`이 `{500000}`이다.
9. `check_text("")`와 4,001자 입력이 `ApiError`, 4,000자는 `None`.
10. PNG·JPEG·WAV·MP3·WebM 시그니처를 맞게 판별하고, 확장자만 바꾼 텍스트 파일은 `None`.
11. `RateLimiter(5)`가 같은 키 6번째 요청을 60초 안에서 거부하고 61초 뒤 허용한다.

## 하지 않는 것

- 실행 상태에 결과 저장(T11 intake), 음성 실제 길이 확인(T20), API 응답 형식(T12).

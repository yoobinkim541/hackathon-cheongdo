"""Number handling for Korean notes: OCR digit repair and numeral normalization."""

from __future__ import annotations

import re

_OCR_CONFUSABLE = re.compile(
    r"(?<=[\d-])[OolI](?=[\d-])|(?<![A-Za-z\d])[OolI](?=\d)|(?<=\d)[OolI](?![A-Za-z\d])"
)
_OCR_MAP = {"O": "0", "o": "0", "l": "1", "I": "1"}
_PLACEHOLDER = re.compile(r"\[[^\[\]\s]{1,10}\]")

_SINO_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_SMALL_UNITS = {"십": 10, "백": 100, "천": 1000}
_BIG_UNITS = {"만": 10_000, "억": 100_000_000}
_UNITS = _SMALL_UNITS | _BIG_UNITS
_SINO_CHARS = set(_SINO_DIGITS) | set(_UNITS)

_ARABIC = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_COUNTER = re.compile(r"\s?(?:원|세|살|명|식구|가구|개월|년|달|대|평|회|번|시간|퍼센트|%)")
_PARTICLES = set("이가은는을를의도에만로와과")

_NATIVE_TENS = {"열": 10, "스물": 20, "서른": 30, "마흔": 40, "쉰": 50, "예순": 60, "일흔": 70, "여든": 80, "아흔": 90}
_NATIVE_ONES = {
    "한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5,
    "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9,
}
_NATIVE = re.compile(
    r"(?<![가-힣])(" + "|".join(_NATIVE_TENS) + r")?\s?("
    + "|".join(sorted(_NATIVE_ONES, key=len, reverse=True))
    + r")?\s?(?:명|식구|분(?![야리석류])|사람|살|가구|달)"
)


def fix_ocr_digits(text: str) -> str:
    """Replace O/o with 0 and l/I with 1 when they sit between digits or hyphens."""
    prev = None
    while prev != text:
        prev = text
        text = _OCR_CONFUSABLE.sub(lambda m: _OCR_MAP[m.group(0)], text)
    return text


def _is_hangul(ch: str) -> bool:
    return "가" <= ch <= "힣"


def _evaluate(tokens: list[float | str]) -> int:
    """Evaluate a Korean-style number from numeric values and unit characters."""
    total = 0.0
    section = 0.0
    cur = 0.0
    for tok in tokens:
        if isinstance(tok, str):
            if tok in _SMALL_UNITS:
                section += (cur or 1) * _SMALL_UNITS[tok]
            else:
                total += (section + cur or 1) * _BIG_UNITS[tok]
                section = 0.0
            cur = 0.0
        else:
            cur = tok
    return int(round(total + section + cur))


def _sino_tokens(seq: str) -> list[float | str]:
    return [float(_SINO_DIGITS[c]) if c in _SINO_DIGITS else c for c in seq]


def _sino_valid(prefix: str, rest: str) -> bool:
    if _COUNTER.match(rest) and (len(prefix) > 1 or rest.startswith(" ")):
        return True
    if len(prefix) < 2 or prefix[-1] not in _UNITS:
        return False
    if not rest or not _is_hangul(rest[0]):
        return True
    return rest[0] in _PARTICLES and (len(rest) == 1 or not _is_hangul(rest[1]))


def _read_arabic_piece(text: str, i: int) -> tuple[list[float | str], int] | None:
    m = _ARABIC.match(text, i)
    if not m:
        return None
    tokens: list[float | str] = [float(m.group(0).replace(",", ""))]
    j = m.end()
    while j < len(text) and text[j] in _UNITS:
        tokens.append(text[j])
        j += 1
    return tokens, j


def _read_sino_piece(text: str, i: int) -> tuple[list[float | str], int] | None:
    j = i
    while j < len(text) and text[j] in _SINO_CHARS:
        j += 1
    for end in range(j, i, -1):
        if _sino_valid(text[i:end], text[end:]):
            return _sino_tokens(text[i:end]), end
    return None


def _scan(text: str) -> set[int]:
    found: set[int] = set()
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isdigit() and (i == 0 or not (text[i - 1].isdigit() or text[i - 1] in ",.")):
            reader = _read_arabic_piece
        elif ch in _SINO_CHARS and (i == 0 or not _is_hangul(text[i - 1])):
            reader = _read_sino_piece
        else:
            i += 1
            continue
        piece = reader(text, i)
        if piece is None:
            i += 1
            continue
        tokens, j = piece
        # Continue across one space after a 만/억 (or 천) unit: "1억 2천만", "삼십만 오천 원".
        while isinstance(tokens[-1], str) and tokens[-1] in ("억", "만", "천"):
            k = j + 1 if j < n and text[j] == " " else j
            nxt = reader(text, k) if k < n else None
            if nxt is None:
                break
            tokens += nxt[0]
            j = nxt[1]
        found.add(_evaluate(tokens))
        i = j
    return found


def parse_numbers(text: str) -> set[int]:
    """Return every number stated in the text, normalizing Korean numerals and units."""
    text = _PLACEHOLDER.sub(" ", text)
    found = _scan(text)
    for m in _NATIVE.finditer(text):
        tens, ones = m.group(1), m.group(2)
        if tens or ones:
            found.add(_NATIVE_TENS.get(tens or "", 0) + _NATIVE_ONES.get(ones or "", 0))
    return found


def new_numbers(original: str, cleaned: str) -> set[int]:
    """Numbers that appear in the cleaned text but not in the original."""
    return parse_numbers(cleaned) - parse_numbers(original)

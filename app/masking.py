"""Personal data masking for consultation notes. Pure functions only."""

from __future__ import annotations

import re

from app.schemas import MaskResult, MaskSpan
from app.textnum import fix_ocr_digits

LABELS = {"name": "이름", "phone": "전화", "rrn": "주민번호", "account": "계좌", "address": "주소"}

_RRN = re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)")
_MOBILE = re.compile(r"(?<!\d)01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")
_LANDLINE = re.compile(r"(?<!\d)0\d{1,2}[-)]\s?\d{3,4}-\d{4}(?!\d)")
_DIGIT_RUN = re.compile(r"(?<!\d)\d{10,11}(?!\d)")
_KOREAN_DIGITS = "공영일이삼사오육칠팔구"
_KOREAN_PHONE = re.compile(rf"[{_KOREAN_DIGITS}](?:[\s-]*[{_KOREAN_DIGITS}]){{9,}}")
_ACCOUNT = re.compile(r"(?<![\d-])\d{2,6}-\d{2,6}-\d{2,7}(?:-\d{1,3})?(?![\d-])")
_ADDR_BLOCK = r"(?![\d,]|\.\d|\s?(?:[만천백억원세살명년월일개시분회층%]|km|번(?!지)))"
_ADDRESS = [
    re.compile(r"(?<!\d)\d+동\s?\d+호(?!선)"),
    re.compile(r"(?<![\d-])\d+(?:-\d+)?번지"),
    re.compile(r"[가-힣]+(?:\d+)?(?:로|길)\s?\d+(?:-\d+)?(?:번지)?" + _ADDR_BLOCK),
    re.compile(r"(?<![가-힣])[가-힣]{1,4}리\s?\d+(?:-\d+)?(?:번지)?" + _ADDR_BLOCK),
    re.compile(r"(?<!\d)\d+호(?![선가-힣])"),
]
_TITLES = "선생님|아버님|어머님|할아버지|할머니|어르신|여사|씨|님"
_TITLE_NAME = re.compile(rf"(?<![가-힣])([가-힣]{{2,4}})\s?(?={_TITLES})")
_SURNAMES = set(
    "김이박최정강조윤장임한오서신권황안송류유홍전고문양손배백허남심노하곽성차주우구민진나지엄변채원천방공현함염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉경사부"
)
_NOT_NAMES = {
    "이웃", "이장", "이분", "이번", "이제", "이미", "이전", "주민", "주무관", "손자", "손녀", "손님", "남편", "남자",
    "부인", "부모", "부녀회장", "마을", "마을회관", "사모", "사회복지사", "선생", "정말", "정도", "고객", "한분",
    "어제", "오늘", "모두", "모든", "우리", "저희", "그분", "장남", "장녀", "차남", "형님", "동생", "조카", "고모",
    "이모", "삼촌", "변호사", "간호사", "의사", "기사", "공무원", "반장", "팀장", "과장", "계장", "면장", "읍장",
    "조합장", "회장", "원장", "소장", "교장", "목사", "신부", "스님", "도우미", "요양보호사", "방문간호사",
    "아저", "아가", "솜", "마음", "날", "글", "말", "전화", "문자", "옆집", "앞집", "건너편", "노인", "어머", "아버",
    "할머", "할아", "하느", "하나", "따님", "아드님", "며느리", "사위", "손주", "주인", "집주인", "임대인", "가족",
}
_VERB_ENDINGS = ("는", "던", "시는", "하신", "사는", "계신", "였던")

_RESIDUAL = [_RRN, _MOBILE, _DIGIT_RUN]


def _looks_like_name(word: str) -> bool:
    if word in _NOT_NAMES or word[0] not in _SURNAMES:
        return False
    return not word.endswith(_VERB_ENDINGS)


def _overlaps(start: int, end: int, taken: list[tuple[int, int, str, str]]) -> bool:
    return any(start < e and s < end for s, e, _, _ in taken)


def _add(taken: list[tuple[int, int, str, str]], start: int, end: int, kind: str, text: str) -> None:
    if start < end and not _overlaps(start, end, taken):
        taken.append((start, end, kind, text[start:end]))


def _korean_phone_end(text: str, start: int, end: int) -> int:
    """Trim a spoken-digit phone run to at most 11 digits (drops trailing particles like 이)."""
    count = 0
    for i in range(start, end):
        if text[i] in _KOREAN_DIGITS:
            count += 1
            if count == 11:
                return i + 1
    return end


def _account_digits(s: str) -> int:
    return sum(c.isdigit() for c in s)


def _collect(text: str, names: list[str]) -> list[tuple[int, int, str, str]]:
    taken: list[tuple[int, int, str, str]] = []
    for m in _RRN.finditer(text):
        _add(taken, m.start(), m.end(), "rrn", text)
    for m in _KOREAN_PHONE.finditer(text):
        _add(taken, m.start(), _korean_phone_end(text, m.start(), m.end()), "phone", text)
    for pattern in (_MOBILE, _LANDLINE):
        for m in pattern.finditer(text):
            _add(taken, m.start(), m.end(), "phone", text)
    for m in _ACCOUNT.finditer(text):
        if _account_digits(m.group(0)) >= 10:
            _add(taken, m.start(), m.end(), "account", text)
    for m in _DIGIT_RUN.finditer(text):
        _add(taken, m.start(), m.end(), "phone", text)
    for pattern in _ADDRESS:
        for m in pattern.finditer(text):
            _add(taken, m.start(), m.end(), "address", text)
    found_names = [n for n in names if n]
    for m in _TITLE_NAME.finditer(text):
        if _looks_like_name(m.group(1)):
            found_names.append(m.group(1))
    for name in sorted(set(found_names), key=len, reverse=True):
        for m in re.finditer(re.escape(name), text):
            _add(taken, m.start(), m.end(), "name", text)
    taken.sort()
    return taken


def _next_numbers(known: dict[str, str]) -> dict[str, int]:
    counters = {kind: 0 for kind in LABELS}
    for placeholder in known.values():
        for kind, label in LABELS.items():
            m = re.fullmatch(rf"\[{label}(\d+)\]", placeholder)
            if m:
                counters[kind] = max(counters[kind], int(m.group(1)))
    return counters


def find_residual(text: str) -> list[str]:
    """Strings that still look like resident registration or phone numbers."""
    found: list[str] = []
    for pattern in _RESIDUAL:
        for m in pattern.finditer(text):
            if m.group(0) not in found:
                found.append(m.group(0))
    return found


def mask(
    text: str,
    source: str = "text",
    known: dict[str, str] | None = None,
    names: list[str] | None = None,
) -> MaskResult:
    """Replace personal data with numbered placeholders. `known` maps original to placeholder and is extended."""
    if source == "image":
        text = fix_ocr_digits(text)
    known = known if known is not None else {}
    counters = _next_numbers(known)
    spans: list[MaskSpan] = []
    parts: list[str] = []
    pos = 0
    for start, end, kind, original in _collect(text, names or []):
        placeholder = known.get(original)
        if placeholder is None:
            counters[kind] += 1
            placeholder = f"[{LABELS[kind]}{counters[kind]}]"
            known[original] = placeholder
        parts.append(text[pos:start])
        parts.append(placeholder)
        pos = end
        spans.append(MaskSpan(kind=kind, start=start, end=end, placeholder=placeholder))
    parts.append(text[pos:])
    masked = "".join(parts)
    return MaskResult(text=masked, spans=spans, residual=find_residual(masked))


def mask_fragments(fragments: list[str], source: str, known: dict[str, str], names: list[str]) -> list[str]:
    """Mask short text fragments (e.g. low-confidence OCR/STT spans) with the shared placeholder map.
    A fragment that still looks like personal data after masking is dropped."""
    out: list[str] = []
    for fragment in fragments:
        result = mask(fragment, source=source, known=known, names=names)
        if not result.residual:
            out.append(result.text)
    return out

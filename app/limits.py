"""Input validation for text and uploaded media. Pure functions only."""

from __future__ import annotations

import struct

from app.config import MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS, MAX_IMAGE_BYTES, MAX_TEXT_CHARS

IMAGE_FORMATS = ("jpeg", "png")
AUDIO_FORMATS = ("wav", "mp3", "webm", "ogg")


def check_text(text: str | None) -> str | None:
    """Korean error message for an empty or too long note, else None."""
    if not text or not text.strip():
        return "메모 내용을 입력해 주세요."
    if len(text) > MAX_TEXT_CHARS:
        return f"메모는 {MAX_TEXT_CHARS}자 이하로 입력해 주세요."
    return None


def sniff_media(head: bytes) -> str | None:
    """Detect jpeg/png/wav/mp3/webm/ogg from magic bytes."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if head.startswith(b"OggS"):
        return "ogg"
    return None


def wav_seconds(data: bytes) -> float | None:
    """Duration of a PCM WAV from its fmt and data chunks, or None if the header is unreadable."""
    pos = 12
    byte_rate = None
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        (size,) = struct.unpack_from("<I", data, pos + 4)
        body = pos + 8
        if chunk_id == b"fmt " and size >= 16 and body + 16 <= len(data):
            (byte_rate,) = struct.unpack_from("<I", data, body + 8)
        elif chunk_id == b"data":
            if not byte_rate:
                return None
            available = len(data) - body
            data_size = available if size in (0, 0xFFFFFFFF) or size > available else size
            return data_size / byte_rate
        pos = body + size + (size & 1)
    return None


def check_media(kind: str, data: bytes) -> tuple[str | None, str | None]:
    """Return (Korean error message or None, detected format or None)."""
    if kind not in ("image", "audio"):
        return "파일 종류는 image 또는 audio여야 합니다.", None
    if not data:
        return "파일이 비어 있습니다.", None
    fmt = sniff_media(data[:16])
    if kind == "image":
        if len(data) > MAX_IMAGE_BYTES:
            return f"사진은 {MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하만 올릴 수 있습니다.", fmt
        if fmt not in IMAGE_FORMATS:
            return "사진은 JPEG 또는 PNG 형식만 올릴 수 있습니다.", fmt
        return None, fmt
    if len(data) > MAX_AUDIO_BYTES:
        return f"음성은 {MAX_AUDIO_BYTES // (1024 * 1024)}MB 이하만 올릴 수 있습니다.", fmt
    if fmt not in AUDIO_FORMATS:
        return "음성은 WAV, MP3, WebM, OGG 형식만 올릴 수 있습니다.", fmt
    if fmt == "wav":
        seconds = wav_seconds(data)
        if seconds is None:
            return "WAV 파일의 머리글을 읽을 수 없습니다.", fmt
        if seconds > MAX_AUDIO_SECONDS:
            return f"음성은 {MAX_AUDIO_SECONDS // 60}분 이하만 올릴 수 있습니다.", fmt
    return None, fmt

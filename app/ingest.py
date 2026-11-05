"""Azure AI Services calls: Document Intelligence OCR and Speech fast transcription. Media never leaves this module."""

from __future__ import annotations

import json
import time

import httpx
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.identity.aio import DefaultAzureCredential

from app import config
from app.rules import load_schemes
from app.schemas import Transcript

TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
SPEECH_API_VERSION = "2025-10-15"
PHRASES_EXTRA = ["차상위", "기준 중위소득", "맞춤형급여", "소득인정액", "행정복지센터", "맞춤형복지팀"]
AUDIO_MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "webm": "audio/webm", "ogg": "audio/ogg"}


class IngestError(RuntimeError):
    pass


_credential: DefaultAzureCredential | None = None


def credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


async def check_token() -> None:
    await credential().get_token(TOKEN_SCOPE)


def _endpoint(settings: config.Settings) -> str:
    if not settings.enable_ai_services or not settings.azure_ai_endpoint:
        raise IngestError("사진·음성 인식 서비스가 설정되지 않았습니다.")
    return settings.azure_ai_endpoint


async def ocr_image(data: bytes, settings: config.Settings = config.SETTINGS) -> Transcript:
    endpoint = _endpoint(settings)
    started = time.monotonic()
    try:
        async with DocumentIntelligenceClient(endpoint=endpoint, credential=credential()) as client:
            poller = await client.begin_analyze_document(
                "prebuilt-read", AnalyzeDocumentRequest(bytes_source=data), locale="ko-KR"
            )
            result = await poller.result()
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"사진을 읽지 못했습니다: {type(exc).__name__}") from exc
    lines: list[str] = []
    uncertain: list[str] = []
    for page in result.pages or []:
        for line in page.lines or []:
            lines.append(line.content)
        for word in page.words or []:
            if word.confidence is not None and word.confidence < config.OCR_LOW_CONFIDENCE:
                uncertain.append(word.content)
    text = "\n".join(lines).strip() or (result.content or "").strip()
    if not text:
        raise IngestError("사진에서 글자를 찾지 못했습니다.")
    return Transcript(source="image", text=text, uncertain=uncertain, ms=int((time.monotonic() - started) * 1000))


async def transcribe_audio(data: bytes, fmt: str, settings: config.Settings = config.SETTINGS) -> Transcript:
    endpoint = _endpoint(settings)
    started = time.monotonic()
    phrases = [s.name for s in load_schemes()] + PHRASES_EXTRA
    definition = {
        "locales": ["ko-KR"],
        "diarization": {"enabled": True, "maxSpeakers": 2},
        "phraseList": {"phrases": phrases},
    }
    try:
        token = await credential().get_token(TOKEN_SCOPE)
        async with httpx.AsyncClient(timeout=90) as http:
            resp = await http.post(
                f"{endpoint}/speechtotext/transcriptions:transcribe",
                params={"api-version": SPEECH_API_VERSION},
                headers={"Authorization": f"Bearer {token.token}"},
                files={
                    "audio": (f"audio.{fmt}", data, AUDIO_MIME.get(fmt, "application/octet-stream")),
                    "definition": (None, json.dumps(definition, ensure_ascii=False), "application/json"),
                },
            )
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"녹음을 전사하지 못했습니다: {type(exc).__name__}") from exc
    if resp.status_code >= 400:
        raise IngestError(f"녹음을 전사하지 못했습니다(HTTP {resp.status_code}).")
    body = resp.json()
    duration = body.get("durationMilliseconds")
    if isinstance(duration, int) and duration > config.MAX_AUDIO_SECONDS * 1000:
        raise IngestError("녹음이 2분을 넘습니다.")
    phrases_out = body.get("phrases") or []
    speakers = {p.get("speaker") for p in phrases_out if p.get("speaker") is not None}
    label = {}
    for p in phrases_out:
        spk = p.get("speaker")
        if spk is not None and spk not in label:
            label[spk] = "담당자" if not label else "대상자"
    lines: list[str] = []
    uncertain: list[str] = []
    for p in phrases_out:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        spk = p.get("speaker")
        lines.append(f"{label[spk]}: {text}" if spk in label else text)
        conf = p.get("confidence")
        if isinstance(conf, (int, float)) and conf < config.OCR_LOW_CONFIDENCE:
            uncertain.append(text)
    if not lines:
        combined = " ".join(c.get("text", "") for c in body.get("combinedPhrases") or []).strip()
        if combined:
            lines.append(combined)
    if not lines:
        raise IngestError("녹음에서 말소리를 찾지 못했습니다.")
    return Transcript(
        source="audio",
        text="\n".join(lines),
        uncertain=uncertain,
        speakers=len(speakers) or None,
        duration_ms=duration if isinstance(duration, int) else None,
        ms=int((time.monotonic() - started) * 1000),
    )

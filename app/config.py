"""Application settings and fixed limits. Environment variables are read only here."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_TEXT_CHARS = 4000
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 120
MODEL_TIMEOUT_SECONDS = 45
MAX_ATTEMPTS = 2
LIVE_CONCURRENCY = 4
EVAL_CONCURRENCY = 2
EVAL_DEADLINE_SECONDS = 360
RUN_IDLE_TTL_SECONDS = 30 * 60
RUN_MAX_TTL_SECONDS = 45 * 60
RATE_LIMIT_RUNS_PER_MINUTE = 5
RATE_LIMIT_EVAL_PER_MINUTE = 1
HEARTBEAT_SECONDS = 15
OCR_LOW_CONFIDENCE = 0.8


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    copilot_model: str | None = field(default_factory=lambda: os.environ.get("COPILOT_MODEL") or None)
    reasoning_profiler: str | None = field(default_factory=lambda: os.environ.get("REASONING_PROFILER", "low") or None)
    reasoning_match: str | None = field(default_factory=lambda: os.environ.get("REASONING_MATCH", "low") or None)
    reasoning_documenter: str | None = field(default_factory=lambda: os.environ.get("REASONING_DOCUMENTER", "medium") or None)
    reasoning_normalizer: str | None = field(default_factory=lambda: os.environ.get("REASONING_NORMALIZER", "low") or None)
    azure_ai_endpoint: str | None = field(default_factory=lambda: (os.environ.get("AZURE_AI_ENDPOINT") or "").rstrip("/") or None)
    enable_ai_services: bool = field(default_factory=lambda: _flag("ENABLE_AI_SERVICES", False))
    appinsights_connection_string: str | None = field(
        default_factory=lambda: os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or None
    )
    copilot_base_directory: str = field(default_factory=lambda: os.environ.get("COPILOT_BASE_DIRECTORY", "/tmp/copilot-home"))
    disable_copilot: bool = field(default_factory=lambda: _flag("DISABLE_COPILOT", False))


SETTINGS = Settings()

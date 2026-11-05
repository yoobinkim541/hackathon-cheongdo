"""환경변수 단일 진입점과 제한값 상수. 다른 모듈은 os.environ을 읽지 않는다."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from app.schemas import Features

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_TEXT_CHARS = 4000
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_MS = 120_000
OCR_MIN_CONFIDENCE = 0.8
RUN_IDLE_TTL_S = 1800
RUN_HARD_TTL_S = 2700
MAX_CONCURRENT_RUNS = 4
RATE_LIMIT_PER_MIN = 5
EVAL_RATE_PER_MIN = 1
EVAL_CONCURRENCY = 2
EVAL_DEADLINE_S = 360
AGENT_TIMEOUT_S = 45
AGENT_MAX_ATTEMPTS = 2
SUBMIT_REJECT_LIMIT = 2
SSE_HEARTBEAT_S = 15
REPLAY_MAX_GAP_MS = 1500

FLAG_NAMES = (
    "ENABLE_AI_SERVICES",
    "ENABLE_IMAGE_INPUT",
    "ENABLE_AUDIO_INPUT",
    "STT_DIARIZATION",
    "ENABLE_BROWSER_RECORDING",
    "ENABLE_REAPPROVAL",
    "ENABLE_ASK",
    "ENABLE_SESSION_HOOKS",
    "ENABLE_CONTEXT_PROVIDER",
    "MATCH_PARALLEL",
)

_TRUE = {"1", "true", "yes", "on"}


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in _TRUE


class Settings(BaseModel):
    COPILOT_GITHUB_TOKEN: str | None = None
    AZURE_CLIENT_ID: str | None = None
    AZURE_AI_ENDPOINT: str | None = None
    APPLICATIONINSIGHTS_CONNECTION_STRING: str | None = None
    COPILOT_MODEL: str | None = None
    REASONING_PROFILER: str = "low"
    REASONING_MATCH: str = "low"
    REASONING_DOCUMENTER: str = "medium"

    ENABLE_AI_SERVICES: bool = False
    ENABLE_IMAGE_INPUT: bool = False
    ENABLE_AUDIO_INPUT: bool = False
    STT_DIARIZATION: bool = False
    ENABLE_BROWSER_RECORDING: bool = False
    ENABLE_REAPPROVAL: bool = False
    ENABLE_ASK: bool = False
    ENABLE_SESSION_HOOKS: bool = False
    ENABLE_CONTEXT_PROVIDER: bool = False
    MATCH_PARALLEL: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        values: dict[str, object] = {}
        for name in (
            "COPILOT_GITHUB_TOKEN",
            "AZURE_CLIENT_ID",
            "AZURE_AI_ENDPOINT",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "COPILOT_MODEL",
        ):
            if env.get(name):
                values[name] = env[name]
        for name in ("REASONING_PROFILER", "REASONING_MATCH", "REASONING_DOCUMENTER"):
            if env.get(name):
                values[name] = env[name]
        for name in FLAG_NAMES:
            values[name] = _flag(env, name)
        if not values["ENABLE_AI_SERVICES"]:
            values["ENABLE_IMAGE_INPUT"] = False
            values["ENABLE_AUDIO_INPUT"] = False
        if not values["ENABLE_AUDIO_INPUT"]:
            values["ENABLE_BROWSER_RECORDING"] = False
        return cls(**values)

    def features(self) -> Features:
        return Features(
            image_input=self.ENABLE_IMAGE_INPUT,
            audio_input=self.ENABLE_AUDIO_INPUT,
            browser_recording=self.ENABLE_BROWSER_RECORDING,
            ask=self.ENABLE_ASK,
            reapproval=self.ENABLE_REAPPROVAL,
        )

    def reasoning_for(self, step: str) -> str:
        if step == "documenter":
            return self.REASONING_DOCUMENTER
        if step.startswith("match_"):
            return self.REASONING_MATCH
        return self.REASONING_PROFILER


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.from_env()
    return _SETTINGS

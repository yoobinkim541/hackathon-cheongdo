"""In-memory run state, event log and registry. State mutation methods are synchronous."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app import config
from app.schemas import (
    AuditEntry,
    CaseProfile,
    CleanNote,
    DecisionRecord,
    DraftDocuments,
    EligibilityResult,
    FinalDocuments,
    MatchSubmission,
    Mode,
    RunStatus,
    Source,
    UiEvent,
    VerifiedResult,
)

TERMINAL = {"finalized", "drafted", "failed", "expired"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventLog:
    """Append-only event log with sequence numbers, read by SSE handlers."""

    def __init__(self, owner_id: str, mode: Mode) -> None:
        self.owner_id = owner_id
        self.mode = mode
        self.entries: list[dict[str, Any]] = []
        self.closed = False
        self._changed = asyncio.Event()
        self.trace_id: str | None = None

    def append(self, event: UiEvent) -> dict[str, Any]:
        entry = {
            "run_id": self.owner_id,
            "seq": len(self.entries) + 1,
            "ts": now_iso(),
            "type": event.type,
            "step": event.step,
            "mode": self.mode,
            "trace_id": self.trace_id,
            "data": event.data,
        }
        self.entries.append(entry)
        self._notify()
        return entry

    def close(self) -> None:
        self.closed = True
        self._notify()

    def _notify(self) -> None:
        changed, self._changed = self._changed, asyncio.Event()
        changed.set()

    async def wait_beyond(self, seq: int, timeout: float) -> None:
        if len(self.entries) > seq or self.closed:
            return
        try:
            await asyncio.wait_for(self._changed.wait(), timeout)
        except TimeoutError:
            pass


@dataclass
class RunState:
    id: str
    source: Source
    mode: Mode
    purpose: str = "live"
    case_id: str | None = None
    owner_sid: str = ""
    status: RunStatus = "running"
    created: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    raw_text: str | None = None
    media: bytes | None = None
    media_format: str | None = None
    known_names: list[str] = field(default_factory=list)
    transcript_text: str | None = None
    transcript_uncertain: list[str] = field(default_factory=list)
    masked_note: str | None = None
    pii_map: dict[str, str] = field(default_factory=dict)
    mask_spans: list[dict[str, Any]] = field(default_factory=list)
    clean_note: CleanNote | None = None
    profile: CaseProfile | None = None
    decisions: dict[str, DecisionRecord] = field(default_factory=dict)
    match_submissions: dict[str, MatchSubmission] = field(default_factory=dict)
    submit_rejections: dict[str, int] = field(default_factory=dict)
    draft: DraftDocuments | None = None
    verified: VerifiedResult | None = None
    final_documents: FinalDocuments | None = None
    pending_request_id: str | None = None
    approval_scheme_ids: list[str] = field(default_factory=list)
    approval_shown_at: float | None = None
    review: dict[str, Any] = field(default_factory=dict)
    sessions: dict[str, Any] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    audit: dict[str, list[AuditEntry]] = field(default_factory=dict)
    audit_complete: dict[str, bool] = field(default_factory=dict)
    timings: dict[str, int] = field(default_factory=dict)
    usage: dict[str, dict[str, int]] = field(default_factory=dict)
    error_code: str | None = None
    workflow: Any = None
    task: asyncio.Task | None = None
    log: EventLog = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.log is None:
            self.log = EventLog(self.id, self.mode)

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def record_decision(self, result: EligibilityResult, source: str, step: str) -> DecisionRecord:
        decision_id = f"d{len(self.decisions) + 1}"
        record = DecisionRecord(**result.model_dump(), decision_id=decision_id, source=source, step=step)
        self.decisions[decision_id] = record
        return record

    def decided_scheme_ids(self) -> set[str]:
        return {d.scheme_id for d in self.decisions.values()}

    def emit(self, event: UiEvent) -> None:
        self.touch()
        self.log.append(event)

    def set_status(self, status: RunStatus) -> None:
        self.status = status
        self.touch()


@dataclass
class EvalState:
    id: str
    owner_sid: str = ""
    created: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    done: bool = False
    log: EventLog = None  # type: ignore[assignment]
    task: asyncio.Task | None = None

    def __post_init__(self) -> None:
        if self.log is None:
            self.log = EventLog(self.id, "live")


class Registry:
    def __init__(self) -> None:
        self.runs: dict[str, RunState] = {}
        self.evals: dict[str, EvalState] = {}

    def create_run(self, **kwargs: Any) -> RunState:
        run = RunState(id=str(uuid.uuid4()), **kwargs)
        self.runs[run.id] = run
        return run

    def get_run(self, run_id: str) -> RunState | None:
        return self.runs.get(run_id)

    def create_eval(self, owner_sid: str = "") -> EvalState:
        ev = EvalState(id=str(uuid.uuid4()), owner_sid=owner_sid)
        self.evals[ev.id] = ev
        return ev

    def get_eval(self, eval_id: str) -> EvalState | None:
        return self.evals.get(eval_id)

    def remove_run(self, run_id: str) -> RunState | None:
        run = self.runs.pop(run_id, None)
        if run:
            run.log.close()
        return run

    def expired_runs(self) -> list[RunState]:
        now = time.monotonic()
        out = []
        for run in self.runs.values():
            idle = now - run.last_activity
            age = now - run.created
            active = run.status in {"running", "replaying", "resuming"}
            if age > config.RUN_MAX_TTL_SECONDS or (idle > config.RUN_IDLE_TTL_SECONDS and not active):
                out.append(run)
        return out

    def expired_evals(self) -> list[EvalState]:
        now = time.monotonic()
        return [e for e in self.evals.values() if now - e.created > config.RUN_MAX_TTL_SECONDS]

    def clear(self) -> None:
        self.runs.clear()
        self.evals.clear()


REGISTRY = Registry()

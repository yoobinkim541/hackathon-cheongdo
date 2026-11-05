"""Shared Copilot client, the six agents, the tool allowlist, permission handlers and the single agent-call wrapper."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from agent_framework.github import GitHubCopilotAgent
from copilot import CopilotClient
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject

from app import config, prompts
from app.events import map_update
from app.runs import RunState
from app.schemas import AgentCallResult, UiEvent
from app.tools import TOOLS

log = logging.getLogger("dongheng.agents")

TOOL_ALLOWLIST: dict[str, list[str]] = {
    "normalizer": ["record_clean_note"],
    "profiler": ["record_case_profile"],
    "match_living": ["search_schemes", "check_eligibility", "submit_matches"],
    "match_health": ["search_schemes", "check_eligibility", "submit_matches"],
    "match_care": ["search_schemes", "check_eligibility", "submit_matches"],
    "documenter": ["lookup_decision", "submit_draft"],
}
AGENT_INSTRUCTIONS = {
    "normalizer": prompts.NORMALIZER,
    "profiler": prompts.PROFILER,
    "match_living": prompts.MATCH,
    "match_health": prompts.MATCH,
    "match_care": prompts.MATCH,
    "documenter": prompts.DOCUMENTER,
}

Emit = Callable[[UiEvent], Awaitable[None]]


def make_permission_handler(step: str):
    allowed = set(TOOL_ALLOWLIST[step])

    async def on_permission_request(request, invocation):
        kind = getattr(request, "kind", None)
        name = getattr(request, "tool_name", None)
        if kind == "custom-tool" and name in allowed:
            return PermissionDecisionApproveOnce()
        log.warning("permission denied step=%s kind=%s tool=%s", step, kind, name)
        return PermissionDecisionReject(feedback="이 앱에서는 허용하지 않는 동작입니다.")

    return on_permission_request


class AgentHub:
    """Owns the shared CopilotClient and one GitHubCopilotAgent per step."""

    def __init__(self) -> None:
        self.client: CopilotClient | None = None
        self.agents: dict[str, GitHubCopilotAgent] = {}
        self.model: str | None = None
        self.reasoning_supported: set[str] = set()

    async def start(self, settings: config.Settings) -> None:
        self.client = CopilotClient(base_directory=settings.copilot_base_directory)
        await self.client.start()
        self.model = settings.copilot_model
        try:
            models = await self.client.list_models()
            info = next((m for m in models if m.id == self.model), None) if self.model else None
            if info is not None:
                efforts = getattr(info, "supported_reasoning_efforts", None) or []
                self.reasoning_supported = {str(e) for e in efforts}
        except Exception:  # model listing is informative only
            log.exception("list_models failed")
        reasoning = {
            "normalizer": settings.reasoning_normalizer,
            "profiler": settings.reasoning_profiler,
            "match_living": settings.reasoning_match,
            "match_health": settings.reasoning_match,
            "match_care": settings.reasoning_match,
            "documenter": settings.reasoning_documenter,
        }
        for step, tool_names in TOOL_ALLOWLIST.items():
            options = {
                "system_message": {"mode": "replace", "content": AGENT_INSTRUCTIONS[step]},
                "available_tools": [f"custom:{name}" for name in tool_names],
                "on_permission_request": make_permission_handler(step),
                "timeout": config.MODEL_TIMEOUT_SECONDS,
            }
            if self.model:
                options["model"] = self.model
            effort = reasoning.get(step)
            if effort and effort in self.reasoning_supported:
                options["reasoning_effort"] = effort
            self.agents[step] = GitHubCopilotAgent(
                instructions=None,
                client=self.client,
                name=step,
                tools=[TOOLS[name] for name in tool_names],
                default_options=options,
            )

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.stop()

    async def delete_session(self, service_session_id: str | None) -> None:
        if self.client is None or not service_session_id:
            return
        try:
            await self.client.delete_session(service_session_id)
        except Exception:
            log.info("delete_session failed for %s", service_session_id)


HUB = AgentHub()


def classify_error(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    text = f"{type(exc).__name__} {exc}".lower()
    if "429" in text or "rate" in text or "quota" in text or "too many" in text:
        return "rate_limit"
    return "other"


async def call_agent(
    step: str,
    prompt: str,
    run: RunState,
    *,
    emit: Emit,
    submitted: Callable[[], bool],
) -> AgentCallResult:
    """Run one agent step with timeout, retry, audit and UI event emission."""
    agent = HUB.agents[step]
    started = time.monotonic()
    error_code: str | None = None
    text = ""
    for attempt in range(1, config.MAX_ATTEMPTS + 1):
        run.attempts[step] = attempt
        audit = run.audit.setdefault(step, [])
        audit.clear()
        usage = run.usage.setdefault(step, {})
        session = run.sessions.get(step)
        if session is None:
            session = agent.create_session()
            run.sessions[step] = session
        message = prompt if attempt == 1 else prompt + "\n\n이전 시도에서 제출 도구가 호출되지 않았거나 실패했다. 반드시 지정된 도구를 호출해 제출해."
        try:
            async with asyncio.timeout(config.MODEL_TIMEOUT_SECONDS):
                stream = agent.run(
                    message,
                    stream=True,
                    session=session,
                    function_invocation_kwargs={"run_id": run.id, "step": step, "phase": "workflow", "attempt": attempt},
                )
                chunks: list[str] = []
                async for update in stream:
                    for event in map_update(update, step, audit, usage):
                        if event.type == "token":
                            chunks.append(event.data["text"])
                        await emit(event)
                text = "".join(chunks)
            error_code = None if submitted() else "tool_missing"
        except TimeoutError:
            error_code = "timeout"
        except Exception as exc:  # noqa: BLE001 - classified and surfaced as a step failure
            error_code = classify_error(exc)
            log.warning("agent step %s attempt %s failed: %s", step, attempt, exc)
        run.audit_complete[step] = bool(audit) and all(a.has_result for a in audit)
        if error_code is None:
            break
        if error_code in ("timeout", "other", "rate_limit"):
            await HUB.delete_session(getattr(session, "service_session_id", None))
            run.sessions.pop(step, None)
        if error_code == "rate_limit":
            break
        if attempt < config.MAX_ATTEMPTS:
            await emit(UiEvent(type="step_retry", step=step, data={"attempt": attempt + 1, "reason": error_code}))
    ms = int((time.monotonic() - started) * 1000)
    run.timings[step] = ms
    return AgentCallResult(ok=error_code is None, error_code=error_code, attempts=run.attempts[step], ms=ms, text=text)

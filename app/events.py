"""Conversion of MAF workflow events and agent stream updates into UI events."""

from __future__ import annotations

import json
from typing import Any

from app.schemas import AuditEntry, UiEvent

DECISION_KEY = '"decision_id"'


def _short(value: Any, limit: int = 300) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"value": _short(value)}
    return {}


def _usage_numbers(details: Any) -> tuple[int, int]:
    if not details:
        return 0, 0
    items = details.items() if isinstance(details, dict) else vars(details).items()
    inp = out = 0
    for key, val in items:
        if not isinstance(val, int):
            continue
        if "input" in key or "prompt" in key:
            inp += val
        elif "output" in key or "completion" in key:
            out += val
    return inp, out


def decision_id_in(result: Any) -> str | None:
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    if DECISION_KEY not in text:
        return None
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload.get("decision_id")
    except json.JSONDecodeError:
        pass
    start = text.find(DECISION_KEY)
    tail = text[start + len(DECISION_KEY):].split('"')
    return tail[1] if len(tail) > 1 else None


def map_update(update: Any, step: str, audit: list[AuditEntry], usage: dict[str, int]) -> list[UiEvent]:
    """Turn one AgentResponseUpdate into UI events and update the audit trail."""
    events: list[UiEvent] = []
    for content in getattr(update, "contents", None) or []:
        ctype = getattr(content, "type", None)
        if ctype == "text" and content.text:
            events.append(UiEvent(type="token", step=step, data={"text": content.text}))
        elif ctype == "function_call":
            audit.append(AuditEntry(tool=content.name or "", call_id=content.call_id))
            events.append(UiEvent(type="tool_call", step=step, data={"tool": content.name, "args": _args(content.arguments)}))
        elif ctype == "function_result":
            entry = next((a for a in reversed(audit) if a.call_id == content.call_id and not a.has_result), None)
            if entry is None:
                entry = next((a for a in reversed(audit) if not a.has_result), None)
            tool_name = entry.tool if entry else None
            if entry:
                entry.has_result = True
                entry.decision_id = decision_id_in(content.result)
            events.append(UiEvent(type="tool_result", step=step, data={"tool": tool_name, "result": _short(content.result)}))
        elif ctype == "usage":
            inp, out = _usage_numbers(getattr(content, "usage_details", None))
            if inp or out:
                usage["input"] = usage.get("input", 0) + inp
                usage["output"] = usage.get("output", 0) + out
                events.append(UiEvent(type="usage", step=step, data={"input": inp, "output": out}))
    return events


def map_workflow_event(ev: Any) -> list[UiEvent]:
    """Map a MAF WorkflowEvent into UI events. MAF payloads other than UiEvent are never forwarded."""
    etype = getattr(ev, "type", None)
    data = getattr(ev, "data", None)
    if etype in ("intermediate", "output") and isinstance(data, UiEvent):
        return [data]
    if etype == "executor_invoked":
        return [UiEvent(type="step_started", step=getattr(ev, "executor_id", None))]
    if etype == "executor_completed":
        return [UiEvent(type="step_completed", step=getattr(ev, "executor_id", None))]
    if etype == "executor_failed":
        return [UiEvent(type="step_failed", step=getattr(ev, "executor_id", None), data={"code": "other", "message": "단계 실행 중 오류가 발생했습니다."})]
    return []

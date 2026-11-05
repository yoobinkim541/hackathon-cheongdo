"""Azure Monitor + Microsoft Agent Framework instrumentation. Sensitive content is never recorded."""

from __future__ import annotations

import logging

from opentelemetry import trace

from app import config

log = logging.getLogger("dongheng.telemetry")
_configured = False


def setup(settings: config.Settings = config.SETTINGS) -> None:
    global _configured
    if _configured:
        return
    _configured = True
    if settings.appinsights_connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(
                connection_string=settings.appinsights_connection_string,
                logger_name="dongheng",
            )
        except Exception:  # noqa: BLE001 - telemetry must never stop the app
            log.exception("Azure Monitor setup failed")
    try:
        from agent_framework.observability import enable_instrumentation

        enable_instrumentation(enable_sensitive_data=False)
    except Exception:  # noqa: BLE001
        log.exception("MAF instrumentation setup failed")


def tracer():
    return trace.get_tracer("dongheng")


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None

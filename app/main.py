"""FastAPI routes, SSE, input checks, session binding, rate limits and security headers."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from app import config, limits, rules
from app.runs import REGISTRY, EventLog
from app.schemas import SECTION_IDS, ApprovalDecision
from app.service import SERVICE, load_cases, load_replay, sample_path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dongheng.api")

SID_COOKIE = "dh_sid"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "dongheng"
MAX_JSON_BYTES = 64 * 1024
MAX_UPLOAD_BYTES = config.MAX_AUDIO_BYTES + 64 * 1024

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
    "media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'self'; object-src 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=(), payment=()",
    "Strict-Transport-Security": "max-age=31536000",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    await SERVICE.startup()
    yield
    await SERVICE.shutdown()


app = FastAPI(title="동행노트", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


def error(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status, headers=headers)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0) -> int | None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return int(window - (now - q[0])) + 1
        q.append(now)
        return None


LIMITER = RateLimiter()


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    sid = request.cookies.get(SID_COOKIE)
    new_sid = None
    if not sid or len(sid) < 32:
        new_sid = sid = secrets.token_urlsafe(32)
    request.state.sid = sid
    if request.method == "POST" and request.url.path.startswith("/api/"):
        if request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
            response = error(403, "csrf_header_missing", "요청 헤더가 올바르지 않습니다.")
            return _decorate(request, response, new_sid)
        length = request.headers.get("content-length")
        limit = MAX_UPLOAD_BYTES if request.headers.get("content-type", "").startswith("multipart/") else MAX_JSON_BYTES
        if length and length.isdigit() and int(length) > limit:
            return _decorate(request, error(413, "payload_too_large", "요청 크기가 허용 한도를 넘습니다."), new_sid)
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001 - never leak stack traces
        log.exception("unhandled error")
        response = error(500, "internal", "서버 오류가 발생했습니다.")
    return _decorate(request, response, new_sid)


def _decorate(request: Request, response: Response, new_sid: str | None) -> Response:
    for key, value in SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    if request.url.path.startswith("/api/") or request.url.path in ("/readyz", "/healthz"):
        response.headers["Cache-Control"] = "no-store"
    if new_sid:
        secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(SID_COOKIE, new_sid, httponly=True, secure=secure, samesite="strict", max_age=3600, path="/")
    return response


async def read_json(request: Request) -> dict[str, Any] | None:
    body = await request.body()
    if len(body) > MAX_JSON_BYTES:
        return None
    try:
        data = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


# ---------- health ----------

@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/readyz")
async def readyz():
    r = SERVICE.readiness
    body = {
        "process_ok": r.process_ok,
        "data_ok": r.data_ok,
        "copilot_started": r.copilot_started,
        "copilot_authenticated": r.copilot_authenticated,
        "copilot_model": r.copilot_model,
        "copilot_ready": r.copilot_ready,
        "ai_services_enabled": r.ai_services_enabled,
        "ai_services_token_ok": r.ai_services_token_ok,
        "checked_at": r.checked_at,
    }
    return JSONResponse(body, status_code=200 if r.process_ok and r.data_ok else 503)


# ---------- catalog ----------

@app.get("/api/cases")
async def list_cases():
    out = []
    for case in load_cases().values():
        path = sample_path(case)
        out.append({
            "id": case.id, "title": case.title, "household": case.household, "input_type": case.input_type,
            "media_url": f"/samples/{path.name}" if path else None,
            "replay_available": load_replay(case.id) is not None,
        })
    return out


@app.get("/api/schemes")
async def list_schemes():
    return [s.model_dump() for s in rules.load_schemes()]


@app.get("/samples/{name}")
async def sample_file(name: str):
    allowed = {p.name: p for c in load_cases().values() if (p := sample_path(c))}
    path = allowed.get(name)
    if path is None:
        return error(404, "not_found", "파일이 없습니다.")
    return FileResponse(path)


# ---------- runs ----------

class RunRequest(BaseModel):
    case_id: str | None = None
    note: str | None = None
    mode: str = Field("live", pattern="^(live|replay)$")


@app.post("/api/runs", status_code=201)
async def create_run(request: Request):
    retry = LIMITER.check(f"runs:{client_ip(request)}", config.RATE_LIMIT_RUNS_PER_MINUTE)
    if retry:
        return error(429, "rate_limited", "요청이 많습니다. 잠시 뒤 다시 시도하세요.", {"Retry-After": str(retry)})
    sid = request.state.sid
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        if not SERVICE.readiness.ai_services_token_ok:
            return error(400, "media_invalid", "지금은 사진·음성 인식을 쓸 수 없습니다. 텍스트로 입력해 주세요.")
        form = await request.form()
        kind = form.get("kind")
        upload = form.get("file")
        if kind not in ("image", "audio") or upload is None or not hasattr(upload, "read"):
            return error(400, "media_invalid", "사진 또는 음성 파일을 올려 주세요.")
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        message, fmt = limits.check_media(kind, data)
        if message:
            return error(400, "media_invalid", message)
        run = SERVICE.create_run(source=kind, sid=sid, media=data, media_format=fmt)
        SERVICE.start(run)
        return {"run_id": run.id, "mode": run.mode}
    payload = await read_json(request)
    if payload is None:
        return error(400, "input_invalid", "요청 형식이 올바르지 않습니다.")
    try:
        body = RunRequest(**payload)
    except ValidationError:
        return error(400, "input_invalid", "요청 형식이 올바르지 않습니다.")
    if body.case_id:
        if body.case_id not in load_cases():
            return error(404, "run_not_found", "데모 사례가 없습니다.")
        if body.mode == "replay" and load_replay(body.case_id) is None:
            return error(409, "state_conflict", "저장된 실행이 없습니다.")
        run = SERVICE.start_case(body.case_id, sid, mode=body.mode)
        return {"run_id": run.id, "mode": run.mode}
    message = limits.check_text(body.note)
    if message:
        return error(400, "input_invalid", message)
    if not SERVICE.readiness.copilot_ready:
        return error(409, "state_conflict", "지금은 AI 연결이 준비되지 않았습니다. 데모 사례의 저장된 실행을 이용해 주세요.")
    run = SERVICE.create_run(source="text", sid=sid, text=body.note)
    SERVICE.start(run)
    return {"run_id": run.id, "mode": run.mode}


def owned_run(request: Request, run_id: str):
    run = REGISTRY.get_run(run_id)
    if run is None:
        return None, error(404, "run_not_found", "실행을 찾을 수 없거나 만료되었습니다.")
    if not secrets.compare_digest(run.owner_sid, request.state.sid):
        return None, error(403, "run_forbidden", "이 실행에 접근할 수 없습니다.")
    return run, None


@app.get("/api/runs/{run_id}")
async def get_run(request: Request, run_id: str):
    run, err = owned_run(request, run_id)
    if err:
        return err
    return {"run_id": run.id, "status": run.status, "mode": run.mode, "case_id": run.case_id,
            "pending_request_id": run.pending_request_id}


@app.get("/api/runs/{run_id}/events")
async def run_events(request: Request, run_id: str):
    run, err = owned_run(request, run_id)
    if err:
        return err
    return sse_response(request, run.log)


class ApprovalBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    approved: bool
    edited_sections: dict[str, str] = Field(default_factory=dict)
    scheme_ids: list[str] | None = Field(None, max_length=20)


@app.post("/api/runs/{run_id}/approval", status_code=202)
async def approval(request: Request, run_id: str):
    run, err = owned_run(request, run_id)
    if err:
        return err
    payload = await read_json(request)
    try:
        body = ApprovalBody(**(payload or {}))
    except ValidationError:
        return error(400, "input_invalid", "요청 형식이 올바르지 않습니다.")
    for key, text in body.edited_sections.items():
        if key not in SECTION_IDS:
            return error(400, "input_invalid", "알 수 없는 문서 구획입니다.")
        message = limits.check_text(text) if text else None
        if message:
            return error(400, "input_invalid", message)
    decision = ApprovalDecision(approved=body.approved, edited_sections=body.edited_sections, scheme_ids=body.scheme_ids)
    code = SERVICE.respond(run, body.request_id, decision)
    if code == "state_conflict":
        return error(409, "state_conflict", "이미 처리했거나 승인 대기 중이 아닌 요청입니다.")
    if code == "input_invalid":
        return error(400, "input_invalid", "검증을 통과한 제도만 포함할 수 있습니다.")
    return {"status": run.status}


# ---------- evaluation ----------

@app.post("/api/eval", status_code=201)
async def start_eval(request: Request):
    retry = LIMITER.check("eval:global", config.RATE_LIMIT_EVAL_PER_MINUTE)
    if retry or SERVICE.eval_running:
        return error(429, "rate_limited", "평가는 동시에 한 번, 분당 한 번만 실행할 수 있습니다.", {"Retry-After": str(retry or 30)})
    ev = SERVICE.start_eval(request.state.sid)
    return {"eval_id": ev.id}


@app.get("/api/eval/{eval_id}/events")
async def eval_events(request: Request, eval_id: str):
    ev = REGISTRY.get_eval(eval_id)
    if ev is None:
        return error(404, "run_not_found", "평가를 찾을 수 없거나 만료되었습니다.")
    if not secrets.compare_digest(ev.owner_sid, request.state.sid):
        return error(403, "run_forbidden", "이 평가에 접근할 수 없습니다.")
    return sse_response(request, ev.log)


# ---------- SSE ----------

def sse_response(request: Request, event_log: EventLog) -> StreamingResponse:
    last = request.headers.get("last-event-id", "0")
    start = int(last) if last.isdigit() else 0

    async def stream():
        seq = start
        idle = 0.0
        while True:
            if await request.is_disconnected():
                return
            while seq < len(event_log.entries):
                entry = event_log.entries[seq]
                seq += 1
                yield f"id: {entry['seq']}\nevent: {entry['type']}\ndata: {json.dumps(entry, ensure_ascii=False, default=str)}\n\n"
                if entry["type"] == "done":
                    return
            if event_log.closed:
                return
            before = time.monotonic()
            await event_log.wait_beyond(seq, timeout=config.HEARTBEAT_SECONDS)
            idle = idle + (time.monotonic() - before) if seq >= len(event_log.entries) else 0.0
            if idle >= config.HEARTBEAT_SECONDS:
                idle = 0.0
                yield ": hb\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ---------- static ----------

@app.get("/")
async def index():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import create_agent

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with create_agent() as agent:
        app.state.agent = agent
        yield


app = FastAPI(title="Cheongdo Hackathon", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """SSE 스트리밍 응답: data: {"text": "..."} / {"error": "..."} / {"done": true}"""

    async def events():
        try:
            async for update in app.state.agent.run(req.message, stream=True):
                if update.text:
                    yield f"data: {json.dumps({'text': update.text}, ensure_ascii=False)}\n\n"
        except Exception:
            log.exception("agent run failed")
            yield f"data: {json.dumps({'error': '응답 생성 중 오류가 발생했습니다.'}, ensure_ascii=False)}\n\n"
        yield 'data: {"done": true}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")

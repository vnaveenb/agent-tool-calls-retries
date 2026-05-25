from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .config import get_config, reload_config
from .agent import ReActAgent
from .orchestrator import Orchestrator
from .tools import list_tools
from .tools.base import tool_def_to_litellm_schema

# Configure logging so agent logs appear in uvicorn output
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(title="Agent with Tool Calls + Retries", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# Serve static UI
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ── Rate limiter (in-memory, per-IP) ─────────────────────────

_RATE_LIMIT_RPM = 10  # max requests per minute per IP
_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    window = now - 60  # 1-minute window
    # Clean old entries
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window]
    if len(_rate_store[client_ip]) >= _RATE_LIMIT_RPM:
        return False
    _rate_store[client_ip].append(now)
    return True


# ── Request/Response models ───────────────────────────────────

_MAX_TASK_LENGTH = 2000


class RunRequest(BaseModel):
    task: str

    @field_validator("task")
    @classmethod
    def validate_task_length(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Task cannot be empty.")
        if len(v) > _MAX_TASK_LENGTH:
            raise ValueError(f"Task too long ({len(v)} chars). Maximum is {_MAX_TASK_LENGTH}.")
        return v


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    cfg = get_config()
    return {
        "status": "ok",
        "model": cfg.llm.model,
        "max_steps": cfg.agent.max_steps,
        "tools_available": len(list_tools()),
    }


@app.post("/run")
async def run_task(req: RunRequest, request: Request):
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(429, "Rate limit exceeded. Maximum 10 requests per minute.")

    cfg = get_config()
    if cfg.agents.use_orchestrator:
        orchestrator = Orchestrator()
        result = await orchestrator.run(req.task)
    else:
        # Legacy single-agent mode
        agent = ReActAgent()
        result = await agent.run(req.task)

    return asdict(result)


@app.post("/stream")
async def stream_task(req: RunRequest, request: Request):
    """SSE endpoint — streams progress events as the agent works.

    Event types sent as ``data: {json}\\n\\n``:
      - ``{"type": "phase", "phase": str, "label": str}``
      - ``{"type": "step",  "agent": str, "step": {...}}``
      - ``{"type": "retry", "agent": str, "attempt": int, "error": str}``
      - ``{"type": "done",  "result": {...}}``  — final payload
      - ``{"type": "error", "message": str}``
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(429, "Rate limit exceeded. Maximum 10 requests per minute.")

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def produce() -> None:
        def on_event(event: dict) -> None:
            queue.put_nowait(event)

        try:
            cfg = get_config()
            if cfg.agents.use_orchestrator:
                orchestrator = Orchestrator()
                result = await orchestrator.run(req.task, on_event=on_event)
            else:
                agent = ReActAgent()
                result = await agent.run(req.task, on_event=on_event)
            queue.put_nowait({"type": "done", "result": asdict(result)})
        except Exception as exc:
            logger.exception("[stream] agent error")
            queue.put_nowait({"type": "error", "message": str(exc)})

    async def generate():
        producer = asyncio.create_task(produce())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Keep-alive comment — prevents nginx/browser timeout during long thinking
                    yield ": keepalive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"

                if event["type"] in ("done", "error"):
                    break
        finally:
            producer.cancel()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx response buffering
        },
    )


@app.get("/trace/{run_id}")
def get_trace(run_id: str):
    cfg = get_config()
    trace_path = Path(cfg.agent.traces_dir) / f"{run_id}.json"

    if not trace_path.exists():
        raise HTTPException(404, f"Trace not found: {run_id}")

    with open(trace_path) as f:
        return json.load(f)


@app.get("/tools")
def get_tools():
    tools = list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in tools
    ]


@app.post("/reload-config")
def reload():
    cfg = reload_config()
    return {
        "status": "reloaded",
        "model": cfg.llm.model,
        "max_steps": cfg.agent.max_steps,
    }


@app.get("/download/{filename:path}")
def download_file(filename: str):
    """Download a file generated by the agent from the data directory."""
    cfg = get_config()
    sandbox = Path(cfg.tools.read_file.sandbox_dir).resolve()
    target = (sandbox / filename).resolve()

    # Sandbox check
    if not str(target).startswith(str(sandbox)):
        raise HTTPException(403, "Access denied.")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"File not found: {filename}")

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(_static_dir / "index.html"))

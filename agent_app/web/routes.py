"""REST API + WebSocket 路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

from ..config import APP_ROOT, load_settings
from ..nature_skills import list_available_skills
from ..orchestrator import Orchestrator, WorkflowResult
from ..memory import MemoryManager
from ..rag import PaperRAG

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

_settings = load_settings()
DATA_DIR = APP_ROOT / "data"
KNOWLEDGE_DIR = APP_ROOT.parent / "knowledge_base"

_rag = PaperRAG(
    knowledge_dir=KNOWLEDGE_DIR,
    index_path=DATA_DIR / "rag_index.pkl",
    embedding_api_key=_settings.embedding_api_key,
)
_rag.load_index()
if _rag.embedding_api_key and _rag.chunks:
    try:
        emb_stats = _rag.build_embedding_index()
        logger.info("[RAG] Embedding 索引: %s 维, %s 片段", emb_stats.get('dim', '?'), emb_stats.get('chunks', 0))
    except Exception as e:
        logger.info("[RAG] Embedding 索引暂不可用: %s", e)

_init_memory = None
try:
    from ..memory.redis_backends import _redis_client
    _redis_client().ping()
    _init_memory = MemoryManager(use_redis=True)
except Exception:
    _init_memory = MemoryManager(use_redis=False)

_orch = Orchestrator(_settings, rag=_rag, memory_manager=_init_memory)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "rag_ready": _rag.is_ready,
    })


@router.post("/api/solve")
async def solve(data: dict):
    """启动协作分析任务，返回 task_id 供 WebSocket 连接。"""
    question = data.get("question", "").strip()
    strategy = data.get("strategy", "sequential")
    top_k = data.get("top_k", 6)

    if not question:
        return {"error": "问题不能为空"}

    task_id = uuid.uuid4().hex[:12]

    asyncio.create_task(_run_solve(task_id, question, strategy, top_k))
    return {"task_id": task_id, "status": "started"}


async def _run_solve(task_id: str, question: str, strategy: str, top_k: int):
    """后台运行协作任务，结果通过 WebSocket 推送。"""
    ws = _active_tasks.get(task_id)
    if not ws:
        return

    try:
        await ws.send_json({"type": "start", "task_id": task_id, "strategy": strategy})

        if strategy in ("review", "parallel"):
            if strategy == "review":
                result = _orch.solve_with_review(question, top_k=top_k)
            else:
                result = _orch.solve_parallel(question, top_k=top_k)
            for agent, content in [
                ("modeling", result.modeling.content),
                ("programming", result.programming.content),
                ("writing", result.writing.content),
                ("synthesis", result.synthesis),
            ]:
                await ws.send_json({"type": "phase", "agent": agent, "status": "completed", "result": content})
        else:
            result = _orch.solve_stream(
                question,
                top_k=top_k,
                on_modeling_token=lambda t: _sync_send_token(ws, "modeling", t, 0.0, 0.25),
                on_programming_token=lambda t: _sync_send_token(ws, "programming", t, 0.25, 0.5),
                on_writing_token=lambda t: _sync_send_token(ws, "writing", t, 0.5, 0.75),
                on_synthesis_token=lambda t: _sync_send_token(ws, "synthesis", t, 0.75, 1.0),
            )
            for a in ["modeling", "programming", "writing", "synthesis"]:
                await ws.send_json({"type": "phase", "agent": a, "status": "completed"})

        await ws.send_json({
            "type": "done",
            "result": {
                "modeling": result.modeling.content,
                "programming": result.programming.content,
                "writing": result.writing.content,
                "synthesis": result.synthesis,
            },
        })
    except Exception as exc:
        if ws:
            await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        _active_tasks.pop(task_id, None)


def _sync_send_token(ws, agent: str, token: str, progress_start: float, progress_end: float):
    """同步回调 → 追加到队列，WebSocket 协程负责发送。"""
    if ws:
        _token_queue.append((ws, agent, token, progress_start, progress_end))


_token_queue: list = []
_active_tasks: dict[str, WebSocket] = {}


async def _token_drainer():
    """后台协程：每 50ms 批量发送 token 到 WebSocket。"""
    while True:
        if _token_queue:
            batch = _token_queue[:]
            _token_queue.clear()
            for ws, agent, token, ps, pe in batch:
                try:
                    await ws.send_json({
                        "type": "token", "agent": agent, "content": token,
                        "progress_start": ps, "progress_end": pe,
                    })
                except Exception:
                    pass
        await asyncio.sleep(0.05)


@router.websocket("/ws/solve/{task_id}")
async def ws_solve(websocket: WebSocket, task_id: str):
    await websocket.accept()
    _active_tasks[task_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _active_tasks.pop(task_id, None)


@router.get("/api/rag/query")
async def rag_query(q: str = "", top_k: int = 6):
    if not q.strip():
        return {"chunks": []}
    chunks = _rag.query(q, top_k=top_k)
    return {"chunks": [{"source": c.source, "content": c.content[:300]} for c in chunks]}


@router.post("/api/rag/rebuild")
async def rag_rebuild():
    stats = _rag.build_index()
    return {"status": "ok", **stats}


@router.get("/api/skills")
async def list_skills():
    avail = list_available_skills()
    return {
        "rules": avail["rules"],
        "viz_templates": avail["viz_templates"],
        "tools": avail["tools"],
    }

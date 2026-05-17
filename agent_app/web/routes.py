"""REST API + WebSocket 路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from asyncio import Lock
from pathlib import Path

import tempfile

from fastapi import APIRouter, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
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
    async with _active_tasks_lock:
        ws = _active_tasks.get(task_id)
    if not ws:
        return

    try:
        await ws.send_json({"type": "start", "task_id": task_id, "strategy": strategy})

        if strategy in ("review", "parallel"):
            run_fn = _orch.solve_with_review if strategy == "review" else _orch.solve_parallel
            result = await asyncio.wait_for(
                asyncio.to_thread(run_fn, question, top_k=top_k),
                timeout=SOLVE_TASK_TIMEOUT,
            )
            for agent, content in [
                ("modeling", result.modeling.content),
                ("programming", result.programming.content),
                ("writing", result.writing.content),
                ("synthesis", result.synthesis),
            ]:
                await ws.send_json({"type": "phase", "agent": agent, "status": "completed", "result": content})
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _orch.solve_stream,
                    question,
                    top_k=top_k,
                    on_modeling_token=lambda t: _sync_send_token(ws, "modeling", t, 0.0, 0.25),
                    on_programming_token=lambda t: _sync_send_token(ws, "programming", t, 0.25, 0.5),
                    on_writing_token=lambda t: _sync_send_token(ws, "writing", t, 0.5, 0.75),
                    on_synthesis_token=lambda t: _sync_send_token(ws, "synthesis", t, 0.75, 1.0),
                ),
                timeout=SOLVE_TASK_TIMEOUT,
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
    except asyncio.TimeoutError:
        if ws:
            await ws.send_json({"type": "error", "message": f"任务超时（{SOLVE_TASK_TIMEOUT}s），请简化问题或减少评审轮次"})
    except Exception as exc:
        if ws:
            await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        async with _active_tasks_lock:
            _active_tasks.pop(task_id, None)


def _sync_send_token(ws, agent: str, token: str, progress_start: float, progress_end: float):
    """同步回调 → 追加到队列，WebSocket 协程负责发送。"""
    if ws:
        _token_queue.append((ws, agent, token, progress_start, progress_end))


_token_queue: list = []
_active_tasks: dict[str, WebSocket] = {}
_active_tasks_lock = Lock()
SOLVE_TASK_TIMEOUT = 600  # 10-minute global timeout per task


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
    async with _active_tasks_lock:
        _active_tasks[task_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with _active_tasks_lock:
            _active_tasks.pop(task_id, None)


@router.get("/api/health")
async def health():
    return {"status": "ok", "rag_ready": _rag.is_ready, "active_tasks": len(_active_tasks)}


@router.get("/api/status")
async def status():
    mem_stats = _orch.memory.stats() if _orch.memory else {}
    return {
        "rag_ready": _rag.is_ready,
        "rag_chunks": len(_rag.chunks),
        "active_tasks": len(_active_tasks),
        "memory": mem_stats,
    }


@router.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 文件，提取文本作为题目内容。

    使用 PyMuPDF (fitz) 提取文本，返回前 8000 字符。
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "仅支持 PDF 文件"}, status_code=400)

    try:
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:  # 20MB 限制
            return JSONResponse({"error": "文件过大（最大 20MB）"}, status_code=400)

        # 写入临时文件供 PyMuPDF 读取
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        import fitz  # PyMuPDF
        doc = fitz.open(tmp_path)
        text_parts = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                text_parts.append(text.strip())
        doc.close()

        # 清理临时文件
        Path(tmp_path).unlink(missing_ok=True)

        full_text = "\n\n".join(text_parts)
        if not full_text.strip():
            return JSONResponse({"error": "PDF 无可提取文本（可能是扫描件图片）"}, status_code=400)

        # 限制提取长度
        extracted = full_text[:8000]
        page_count = len(text_parts)

        return {
            "filename": file.filename,
            "pages": page_count,
            "text": extracted,
            "text_preview": extracted[:300] + ("..." if len(extracted) > 300 else ""),
            "truncated": len(full_text) > 8000,
            "full_length": len(full_text),
        }
    except ImportError:
        return JSONResponse({"error": "PyMuPDF 未安装，无法解析 PDF"}, status_code=500)
    except Exception as exc:
        logger.exception("PDF 上传处理失败")
        return JSONResponse({"error": f"PDF 解析失败: {exc}"}, status_code=500)


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

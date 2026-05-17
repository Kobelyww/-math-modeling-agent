"""REST API + WebSocket 路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from asyncio import Lock
from pathlib import Path

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
    """后台运行协作任务，全部使用流式输出推送 token。"""
    async with _active_tasks_lock:
        ws = _active_tasks.get(task_id)
    if not ws:
        return

    # 流式回调：token 推送到 WebSocket
    on_m = (lambda t: _sync_send_token(ws, "modeling", t, 0.0, 0.25)) if ws else None
    on_p = (lambda t: _sync_send_token(ws, "programming", t, 0.25, 0.5)) if ws else None
    on_w = (lambda t: _sync_send_token(ws, "writing", t, 0.5, 0.75)) if ws else None
    on_s = (lambda t: _sync_send_token(ws, "synthesis", t, 0.75, 1.0)) if ws else None

    try:
        await ws.send_json({"type": "start", "task_id": task_id, "strategy": strategy})

        if strategy == "review":
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _orch.solve_with_review_stream,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        elif strategy == "parallel":
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _orch.solve_parallel_stream,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _orch.solve_stream,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
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


def _md_table_from_cells(cells: list, row_count: int, col_count: int) -> str:
    """将表格 cell 列表转为 Markdown 表格字符串。"""
    matrix = [["" for _ in range(col_count)] for _ in range(row_count)]
    for cell in cells:
        r = min(cell["row"], row_count - 1)
        c = min(cell["col"], col_count - 1)
        matrix[r][c] = str(cell.get("text", "")).replace("\n", " ").strip()

    lines = []
    for ri, row in enumerate(matrix):
        lines.append("| " + " | ".join(row) + " |")
        if ri == 0:
            lines.append("| " + " | ".join(["---"] * col_count) + " |")
    return "\n".join(lines)


@router.post("/api/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 文件，提取文本、表格、图片描述作为题目内容。

    使用 PyMuPDF 提取：文字 + 表格（转 Markdown）+ 嵌入图片（可选 VL 描述）。
    返回前 12000 字符。
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "仅支持 PDF 文件"}, status_code=400)

    try:
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            return JSONResponse({"error": "文件过大（最大 20MB）"}, status_code=400)
        if len(content) < 100:
            return JSONResponse({"error": "文件过小或损坏"}, status_code=400)

        import fitz
        doc = fitz.open(stream=content, filetype="pdf")

        page_parts: list[str] = []
        table_count = 0
        image_count = 0

        for pi, page in enumerate(doc):
            page_lines: list[str] = []
            page_lines.append(f"── 第 {pi + 1} 页 ──")

            # 1. 提取文本
            text = page.get_text().strip()
            if text:
                page_lines.append(text)

            # 2. 提取表格
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for t in tabs.tables:
                    cells = []
                    if hasattr(t, "cells"):
                        for cell in t.cells:
                            cells.append({
                                "row": getattr(cell, "row", 0) if not isinstance(cell, dict) else cell.get("row", 0),
                                "col": getattr(cell, "col", 0) if not isinstance(cell, dict) else cell.get("col", 0),
                                "text": getattr(cell, "text", "") if not isinstance(cell, dict) else cell.get("text", ""),
                            })
                    rc = getattr(t, "row_count", 0)
                    cc = getattr(t, "col_count", 0)
                    if cells and rc > 0 and cc > 0:
                        page_lines.append(f"\n[表格 {table_count + 1}]")
                        page_lines.append(_md_table_from_cells(cells, rc, cc))
                        table_count += 1

            # 3. 检测嵌入图片
            imgs = page.get_images(full=True)
            if imgs:
                page_lines.append(f"\n[本页含 {len(imgs)} 张嵌入图片]")
                image_count += len(imgs)

            page_parts.append("\n".join(page_lines))

        total_pages = doc.page_count
        doc.close()

        full_text = "\n\n".join(page_parts)
        # 检查是否有实质性内容（排除每页的纯页头）
        has_content = any(
            p.split("\n", 1)[1].strip() if "\n" in p else False
            for p in page_parts
        )
        if not has_content:
            # 内容全空的 PDF，尝试用图片 OCR 兜底
            return JSONResponse(
                {"error": "PDF 无可提取文本，可能是扫描件。请确认 PDF 包含文字或等待 OCR 功能支持。"},
                status_code=400,
            )

        # 图片描述：异步用 VL 模型（如果有 API key）
        image_descriptions: list[str] = []
        vl_api_key = _settings.embedding_api_key
        if image_count > 0 and vl_api_key:
            try:
                import base64 as _b64
                # 重新打开提取图片
                doc2 = fitz.open(stream=content, filetype="pdf")
                img_descs = []
                seen = 0
                for page in doc2:
                    for img_tuple in page.get_images(full=True):
                        if seen >= 8:
                            break
                        xref = img_tuple[0]
                        try:
                            base_image = doc2.extract_image(xref)
                            if base_image and base_image.get("image"):
                                img_bytes = base_image["image"]
                                if len(img_bytes) < 2048:
                                    continue
                                b64 = _b64.b64encode(img_bytes).decode()
                                from dashscope import MultiModalConversation
                                resp = MultiModalConversation.call(
                                    model="qwen-vl-plus",
                                    api_key=vl_api_key,
                                    messages=[{
                                        "role": "user",
                                        "content": [
                                            {"image": f"data:image/png;base64,{b64}"},
                                            {"text": "请简要描述这张图片的内容（中文，100字以内）。如果是数据表格或图表，说明关键数据和趋势。"},
                                        ],
                                    }],
                                )
                                if resp.status_code == 200:
                                    out = resp.output.get("choices", [{}])[0].get("message", {}).get("content", "")
                                    if isinstance(out, list):
                                        out = " ".join(
                                            i.get("text", "") if isinstance(i, dict) else str(i) for i in out
                                        )
                                    if out.strip():
                                        img_descs.append(f"[图片 {len(img_descs) + 1} 描述] {out.strip()}")
                                seen += 1
                        except Exception:
                            continue
                doc2.close()
                image_descriptions = img_descs
            except (ImportError, Exception):
                pass

        # 组装最终文本：正文 + 图片描述
        final_parts = [full_text]
        if image_descriptions:
            final_parts.append("\n\n── 图片内容描述 ──")
            final_parts.extend(image_descriptions)

        combined = "\n\n".join(final_parts)
        extracted = combined[:12000]

        return {
            "filename": file.filename,
            "pages": total_pages,
            "text": extracted,
            "text_preview": extracted[:300] + ("..." if len(extracted) > 300 else ""),
            "truncated": len(combined) > 12000,
            "full_length": len(combined),
            "table_count": table_count,
            "image_count": image_count,
            "image_described": len(image_descriptions),
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

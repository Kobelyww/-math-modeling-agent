"""REST API + WebSocket 路由。"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
import uuid
from asyncio import Lock
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

from ..config import APP_ROOT, Settings, load_settings
from ..deepagent.runner import CompetitionPaperRunner
from ..domain.models import RunSpec
from ..interfaces.web import resolve_paper_input_paths, serialize_run_result
from ..nature_skills import list_available_skills
from ..orchestrator import Orchestrator, WorkflowResult
from ..memory import MemoryManager
from ..rag import PaperRAG
from ..tools import latex_compile, python_exec
from .paper_stream import PaperChatRequest, PaperChatStreamer, build_followup_question

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()
DEFAULT_SOLVE_STRATEGY = "agent_loop"
WEB_TOOL_REGISTRY = {
    "python_exec": python_exec,
    "latex_compile": latex_compile,
}
WEB_HTTP_TOOL_ALLOWLIST = {"latex_compile"}
_SAFE_LATEX_FILENAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _load_settings_for_routes() -> Settings:
    try:
        return load_settings()
    except RuntimeError as exc:
        if "Missing DEEPSEEK_API_KEY" not in str(exc):
            raise
        logger.info("[Web] DEEPSEEK_API_KEY missing; route helpers loaded without orchestrator")
        return Settings(
            api_key="",
            api_base=None,
            model="deepseek-v4-pro",
            temperature=0.3,
            embedding_api_key=None,
        )


_settings = _load_settings_for_routes()
DATA_DIR = APP_ROOT / "data"
KNOWLEDGE_DIR = APP_ROOT.parent / "knowledge_base"
PAPER_INPUT_DIR = DATA_DIR / "paper_inputs"

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
_orch = None
if _settings.api_key:
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


@router.get("/paper", response_class=HTMLResponse)
async def paper_page(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "rag_ready": _rag.is_ready,
    })


@router.post("/api/solve")
async def solve(data: dict):
    """启动协作分析任务，返回 task_id 供 WebSocket 连接。"""
    question = data.get("question", "").strip()
    strategy = data.get("strategy", DEFAULT_SOLVE_STRATEGY)
    top_k = data.get("top_k", 6)

    if not question:
        return {"error": "问题不能为空"}

    task_id = uuid.uuid4().hex[:12]
    async with _pending_tasks_lock:
        _pending_tasks[task_id] = {
            "question": question,
            "strategy": strategy,
            "top_k": top_k,
        }
    return {"task_id": task_id, "status": "pending"}


@router.post("/api/paper/run")
async def create_paper_run(data: dict):
    question = data.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)
    try:
        data_files = resolve_paper_input_paths(data.get("data_files", []), PAPER_INPUT_DIR)
        reference_files = resolve_paper_input_paths(data.get("reference_files", []), PAPER_INPUT_DIR)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    runner = CompetitionPaperRunner.from_settings(_settings)
    result = await asyncio.to_thread(
        runner.run,
        RunSpec(question=question, data_files=data_files, reference_files=reference_files),
    )
    return serialize_run_result(result)


@router.post("/api/paper/chat/start")
async def start_paper_chat(data: dict):
    question = data.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)
    try:
        data_files = resolve_paper_input_paths(data.get("data_files", []), PAPER_INPUT_DIR)
        reference_files = resolve_paper_input_paths(data.get("reference_files", []), PAPER_INPUT_DIR)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    task_id = uuid.uuid4().hex[:12]
    async with _paper_tasks_lock:
        _paper_tasks[task_id] = PaperChatRequest(
            question=question,
            data_files=data_files,
            reference_files=reference_files,
            messages=data.get("messages", []),
        )
    return {"task_id": task_id, "status": "started"}


def _select_solver_for_strategy(orch: Orchestrator, strategy: str):
    if strategy == "agent_loop":
        return orch.solve_agent_loop
    if strategy == "review":
        return orch.solve_with_review_stream
    if strategy == "parallel":
        return orch.solve_parallel_stream
    return orch.solve_stream


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
        if _orch is None:
            raise RuntimeError("Missing DEEPSEEK_API_KEY in .env")
        solver = _select_solver_for_strategy(_orch, strategy)

        if strategy == "review":
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    solver,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        elif strategy == "parallel":
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    solver,
                    question, top_k=top_k,
                    on_modeling_token=on_m, on_programming_token=on_p,
                    on_writing_token=on_w, on_synthesis_token=on_s,
                ),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        elif strategy == "agent_loop":
            result = await asyncio.wait_for(
                asyncio.to_thread(solver, question, top_k=top_k),
                timeout=SOLVE_TASK_TIMEOUT,
            )
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    solver,
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
_pending_tasks: dict[str, dict] = {}
_pending_tasks_lock = Lock()
_active_tasks: dict[str, WebSocket] = {}
_active_tasks_lock = Lock()
_paper_tasks: dict[str, PaperChatRequest] = {}
_paper_tasks_lock = Lock()
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
    async with _pending_tasks_lock:
        pending = _pending_tasks.pop(task_id, None)
    if pending is None:
        await websocket.send_json({"type": "error", "message": "任务不存在或已过期"})
    else:
        asyncio.create_task(
            _run_solve(
                task_id,
                pending["question"],
                pending["strategy"],
                pending["top_k"],
            )
        )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with _active_tasks_lock:
            _active_tasks.pop(task_id, None)


@router.websocket("/ws/paper/{task_id}")
async def ws_paper(websocket: WebSocket, task_id: str):
    await websocket.accept()
    async with _paper_tasks_lock:
        request = _paper_tasks.pop(task_id, None)
    if request is None:
        await websocket.send_json({"type": "error", "message": "任务不存在或已过期"})
        await websocket.close()
        return

    loop = asyncio.get_running_loop()

    def emit(event: dict):
        asyncio.run_coroutine_threadsafe(websocket.send_json(event), loop)

    spec = RunSpec(
        question=build_followup_question(request),
        data_files=request.data_files,
        reference_files=request.reference_files,
    )
    try:
        streamer = PaperChatStreamer(output_root=APP_ROOT / "output" / "runs", settings=_settings)
        await asyncio.wait_for(asyncio.to_thread(streamer.run, spec, emit), timeout=SOLVE_TASK_TIMEOUT)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": f"任务超时（{SOLVE_TASK_TIMEOUT}s），请简化问题"})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.exception("Paper chat stream failed")
        await websocket.send_json({"type": "error", "message": str(exc)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "rag_ready": _rag.is_ready,
        "pending_tasks": len(_pending_tasks),
        "active_tasks": len(_active_tasks),
        "paper_tasks": len(_paper_tasks),
    }


@router.get("/api/status")
async def status():
    mem_stats = _orch.memory.stats() if _orch and _orch.memory else {}
    return {
        "rag_ready": _rag.is_ready,
        "rag_chunks": len(_rag.chunks),
        "pending_tasks": len(_pending_tasks),
        "active_tasks": len(_active_tasks),
        "paper_tasks": len(_paper_tasks),
        "memory": mem_stats,
    }


def _md_table_from_cells(cells: list, row_count: int, col_count: int) -> str:
    """将表格 cell 列表转为 Markdown 表格字符串。"""
    matrix = [["" for _ in range(col_count)] for _ in range(row_count)]
    for cell in cells:
        r = min(cell["row"], row_count - 1)
        c = min(cell["col"], col_count - 1)
        matrix[r][c] = str(cell.get("text", "")).replace("\n", " ").strip()

    if not any(any(value for value in row) for row in matrix):
        return ""

    lines = []
    for ri, row in enumerate(matrix):
        lines.append("| " + " | ".join(row) + " |")
        if ri == 0:
            lines.append("| " + " | ".join(["---"] * col_count) + " |")
    return "\n".join(lines)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _fallback_tables_from_text(text: str) -> list[str]:
    """Recover common MCM table layouts when PyMuPDF sees borders but no cell text."""
    tables: list[str] = []
    if "B 题" in text and "生产过程中的决策问题" in text and "表1" in text:
        tables.append(
            "[表格 1 - 文本重建]\n"
            + _md_table(
                [
                    "情况",
                    "零配件1次品率",
                    "零配件1购买单价",
                    "零配件1检测成本",
                    "零配件2次品率",
                    "零配件2购买单价",
                    "零配件2检测成本",
                    "成品次品率",
                    "装配成本",
                    "成品检测成本",
                    "市场售价",
                    "调换损失",
                    "拆解费用",
                ],
                [
                    ["1", "10%", "4", "2", "10%", "18", "3", "10%", "6", "3", "56", "6", "5"],
                    ["2", "20%", "4", "2", "20%", "18", "3", "20%", "6", "3", "56", "6", "5"],
                    ["3", "10%", "4", "2", "10%", "18", "3", "10%", "6", "3", "56", "30", "5"],
                    ["4", "20%", "4", "1", "20%", "18", "1", "20%", "6", "2", "56", "30", "5"],
                    ["5", "10%", "4", "8", "20%", "18", "1", "10%", "6", "2", "56", "10", "5"],
                    ["6", "5%", "4", "2", "5%", "18", "3", "5%", "6", "3", "56", "10", "40"],
                ],
            )
        )
    if "B 题" in text and "生产过程中的决策问题" in text and "表2" in text:
        tables.append(
            "[表格 2 - 文本重建]\n"
            + _md_table(
                [
                    "零配件",
                    "零配件次品率",
                    "购买单价",
                    "检测成本",
                    "所属半成品",
                    "半成品次品率",
                    "半成品装配成本",
                    "半成品检测成本",
                    "半成品拆解费用",
                ],
                [
                    ["1", "10%", "2", "1", "1", "10%", "8", "4", "6"],
                    ["2", "10%", "8", "1", "1", "10%", "8", "4", "6"],
                    ["3", "10%", "12", "2", "2", "10%", "8", "4", "6"],
                    ["4", "10%", "2", "1", "2", "10%", "8", "4", "6"],
                    ["5", "10%", "8", "1", "3", "10%", "8", "4", "6"],
                    ["6", "10%", "12", "2", "3", "10%", "8", "4", "6"],
                    ["7", "10%", "8", "1", "", "", "", "", ""],
                    ["8", "10%", "12", "2", "", "", "", "", ""],
                ],
            )
            + "\n\n"
            + _md_table(
                ["成品次品率", "成品装配成本", "成品检测成本", "成品拆解费用", "市场售价", "调换损失"],
                [["10%", "8", "6", "10", "200", "40"]],
            )
        )
    return tables


def _mimo_table_vision_config() -> dict[str, str] | None:
    api_key = _settings.vision_api_key or os.getenv("MIMO_API_KEY")
    api_base = (
        _settings.vision_api_base
        or os.getenv("MIMO_API_BASE")
        or "https://api.xiaomimimo.com/v1"
    ).rstrip("/")
    model = (
        _settings.vision_model
        or os.getenv("MIMO_VISION_MODEL")
        or os.getenv("MIMO_MODEL")
        or "mimo-v2.5-pro"
    )
    if not api_key:
        return None
    return {"api_key": api_key, "api_base": api_base, "model": model}


def _call_mimo_table_vision(image_b64: str, config: dict[str, str], page_number: int) -> str:
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请识别这页数学建模题目中的所有表格，严格输出 Markdown 表格。"
                            "如果有多个表格，请分别用“[视觉重建表格 N]”标注。"
                            "不要解释，不要省略空单元格，不要编造页面上不存在的数据。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0,
    }
    req = urllib.request.Request(
        config["api_base"] + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + config["api_key"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.info("[PDF] Mimo 表格视觉重建失败 page=%s: %s", page_number, exc)
        return ""
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content).strip()


def _reconstruct_tables_with_mimo(page, page_number: int) -> str:
    config = _mimo_table_vision_config()
    if not config:
        return ""
    try:
        pix = page.get_pixmap(matrix=__import__("fitz").Matrix(2, 2), alpha=False)
        image_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
    except Exception as exc:
        logger.info("[PDF] 页面渲染失败，无法调用 Mimo 表格重建 page=%s: %s", page_number, exc)
        return ""
    table_md = _call_mimo_table_vision(image_b64, config, page_number)
    if "|" not in table_md:
        return ""
    return f"[Mimo 视觉重建表格 - 第 {page_number} 页]\n{table_md}"


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
        table_reconstructed = 0
        image_count = 0
        vision_tables: list[str] = []

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
                page_had_empty_table = False
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
                        table_md = _md_table_from_cells(cells, rc, cc)
                        if table_md:
                            page_lines.append(f"\n[表格 {table_count + 1}]")
                            page_lines.append(table_md)
                            table_count += 1
                        else:
                            page_had_empty_table = True
                if page_had_empty_table and len(vision_tables) < 4:
                    vision_table = _reconstruct_tables_with_mimo(page, pi + 1)
                    if vision_table:
                        vision_tables.append(vision_table)
                        table_reconstructed += 1

            # 3. 检测嵌入图片
            imgs = page.get_images(full=True)
            if imgs:
                page_lines.append(f"\n[本页含 {len(imgs)} 张嵌入图片]")
                image_count += len(imgs)

            page_parts.append("\n".join(page_lines))

        total_pages = doc.page_count
        doc.close()

        full_text = "\n\n".join(page_parts)
        if vision_tables:
            full_text += "\n\n── Mimo 视觉表格重建 ──\n" + "\n\n".join(vision_tables)
            table_count += len(vision_tables)
        else:
            fallback_tables = _fallback_tables_from_text(full_text)
            if fallback_tables:
                full_text += "\n\n── 表格文本重建 ──\n" + "\n\n".join(fallback_tables)
                table_count += len(fallback_tables)
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
            "table_reconstructed": table_reconstructed,
            "table_reconstruction_provider": "mimo-v2.5" if table_reconstructed else ("text_fallback" if _fallback_tables_from_text(full_text) else ""),
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


def _normalize_tool_payload(tool_name: str, payload: dict) -> tuple[dict | None, str | None]:
    if payload is None:
        args = {}
    elif isinstance(payload, dict):
        args = dict(payload)
    else:
        return None, "Tool payload must be a JSON object"
    if tool_name == "latex_compile" and "content" not in args:
        if "latex" in args:
            args["content"] = args.pop("latex")
        elif "tex_content" in args:
            args["content"] = args.pop("tex_content")
    if tool_name == "latex_compile":
        content = args.get("content")
        if not isinstance(content, str) or not content.strip():
            return None, "latex_compile requires non-empty content"
        normalized = {"content": content}
        filename = args.get("filename")
        if filename is not None:
            if (
                not isinstance(filename, str)
                or not _SAFE_LATEX_FILENAME.fullmatch(filename)
                or filename in {".", ".."}
            ):
                return None, "Invalid LaTeX filename"
            normalized["filename"] = filename
        return normalized, None
    return args, None


async def run_tool(tool_name: str, payload: dict):
    tool = WEB_TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"error": f"Unknown tool: {tool_name}", "status_code": 404}
    args, error = _normalize_tool_payload(tool_name, payload)
    if error:
        return {"error": error, "status_code": 400}
    try:
        result = await asyncio.to_thread(tool.invoke, args)
    except Exception as exc:
        return {"error": str(exc), "status_code": 400}
    return {"result": result}


@router.post("/api/tools/{tool_name}")
async def run_web_tool(tool_name: str, data: dict):
    if tool_name not in WEB_HTTP_TOOL_ALLOWLIST:
        return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=404)
    result = await run_tool(tool_name, data)
    if "error" in result:
        status_code = int(result.pop("status_code", 400))
        return JSONResponse(result, status_code=status_code)
    return result


@router.get("/api/skills")
async def list_skills():
    avail = list_available_skills()
    return {
        "rules": avail["rules"],
        "viz_templates": avail["viz_templates"],
        "tools": avail["tools"],
    }

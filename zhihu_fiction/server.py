"""zhihu_fiction Web 服务器 — FastAPI + SSE 流式推送."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_ROOT, load_settings
from .orchestrator import create_orchestrator, run_coordinator as _orig_run_coordinator
from .pipeline import Pipeline, RUN_DIR
from .skills_store import SkillsStore

app = FastAPI(title="Zhihu Fiction Studio", version="1.0")
OUTPUT_DIR = APP_ROOT / "output"

settings = load_settings()
skills_store = SkillsStore()

# ---- 全局运行状态 ----
_run_events: dict[str, asyncio.Queue] = {}
_run_progress: dict[str, dict] = {}
_active_lock = threading.Lock()
_active_run_id: str | None = None

_scheduler_pipeline: Pipeline | None = None


def _create_pipeline() -> Pipeline:
    coordinator, reviewer, llm = create_orchestrator(settings, skills_store=skills_store)
    return Pipeline(
        coordinator=coordinator, reviewer=reviewer, llm=llm,
        publisher=None,  # type: ignore[arg-type]
        quality_threshold=6.0, max_rewrites=2,
    )


# ============================================================
# Helpers
# ============================================================

def _read_runs(limit: int = 50) -> list[dict]:
    runs_file = RUN_DIR / "runs.jsonl"
    if not runs_file.exists():
        return []
    runs: list[dict] = []
    with open(runs_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    runs.reverse()
    return runs[:limit]


def _list_story_dirs() -> list[dict]:
    if not OUTPUT_DIR.exists():
        return []
    stories: list[dict] = []
    for d in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir() and not d.name.startswith("."):
            story_file = d / "小说正文.md"
            if story_file.exists():
                content = story_file.read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                excerpt = next(
                    (l for l in lines if l.strip() and not l.startswith("#") and not l.startswith(">")),
                    ""
                )[:200]
                stories.append({
                    "name": d.name,
                    "path": str(story_file.relative_to(APP_ROOT)),
                    "excerpt": excerpt,
                    "created_at": datetime.fromtimestamp(story_file.stat().st_mtime).isoformat(),
                })
    return stories


def _patch_for_progress(pipeline: Pipeline, run_id: str):
    """Monkey-patch pipeline components to emit progress events."""
    q = _run_events.get(run_id)
    if q is None:
        return

    async def _emit(stage: str, status: str, message: str, progress: int, **extra):
        await q.put({
            "type": "stage_update",
            "data": {"run_id": run_id, "stage": stage, "status": status,
                     "message": message, "progress": progress, **extra},
        })

    _orig_scraper = pipeline._scraper
    def _scraper_wrapper():
        asyncio.run(_emit("scrape", "running", "正在抓取知乎热榜...", 10))
        try:
            items = _orig_scraper()
            asyncio.run(_emit("scrape", "completed", f"抓取到 {len(items)} 条热榜", 20, items=len(items)))
            return items
        except Exception as e:
            asyncio.run(_emit("scrape", "failed", str(e), -1))
            raise
    pipeline._scraper = _scraper_wrapper

    _orig_selector = pipeline._selector
    def _selector_wrapper(hot_items, llm):
        asyncio.run(_emit("select_topic", "running", "正在分析选题...", 25))
        try:
            result = _orig_selector(hot_items, llm)
            asyncio.run(_emit("select_topic", "completed", f"选定: {result['topic']}", 30,
                              selected=result['topic'], genre=result.get('genre', '')))
            return result
        except Exception as e:
            asyncio.run(_emit("select_topic", "failed", str(e), -1))
            raise
    pipeline._selector = _selector_wrapper

    # Patch orchestrator.run_coordinator
    import zhihu_fiction.orchestrator as orch_mod
    _orig_coord = orch_mod.run_coordinator

    def _make_stream_cb():
        def _cb(event: dict):
            asyncio.run(q.put({
                "type": "agent_event",
                "data": {"run_id": run_id, **event},
            }))
        return _cb

    def _coord_wrapper(*args, **kwargs):
        asyncio.run(_emit("create", "running", "正在创作 (DeepAgent 协调中)...", 35))
        kwargs["stream_callback"] = _make_stream_cb()
        try:
            result = _orig_coord(*args, **kwargs)
            word_count = len(result.final_story)
            asyncio.run(_emit("create", "completed", f"创作完成，{word_count} 字", 80, words=word_count))
            return result
        except Exception as e:
            asyncio.run(_emit("create", "failed", str(e), -1))
            raise
    orch_mod.run_coordinator = _coord_wrapper


def _unpatch_pipeline(pipeline: Pipeline):
    import zhihu_fiction.orchestrator as orch_mod
    orch_mod.run_coordinator = _orig_run_coordinator


async def _execute_in_background(run_id: str, pipeline: Pipeline, topic: str | None, genre: str | None):
    global _active_run_id
    q = _run_events.setdefault(run_id, asyncio.Queue())
    try:
        await q.put({"type": "stage_update", "data": {
            "run_id": run_id, "stage": "start", "status": "running",
            "message": "流水线启动中...", "progress": 0,
        }})

        _patch_for_progress(pipeline, run_id)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: pipeline.run(topic=topic, genre=genre))

        await q.put({"type": "complete", "data": {
            "run_id": run_id, "status": "completed",
            "message": "运行完成", "progress": 100,
            "topic": result.topic, "genre": result.genre,
            "stages": {
                name: {"status": s.status, "duration_s": s.duration_s, **s.extra}
                for name, s in result.stages.items()
            },
            "total_duration_s": result.total_duration_s,
            "published_url": result.published_url,
        }})
    except Exception as exc:
        await q.put({"type": "complete", "data": {
            "run_id": run_id, "status": "failed",
            "message": str(exc), "progress": 0, "error": str(exc),
        }})
    finally:
        _unpatch_pipeline(pipeline)
        _run_progress[run_id] = {"status": "done"}
        with _active_lock:
            if _active_run_id == run_id:
                _active_run_id = None


# ============================================================
# Routes — Static
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    static_file = APP_ROOT / "static" / "index.html"
    if not static_file.exists():
        return HTMLResponse("<h2>index.html not found. Create static/index.html first.</h2>", status_code=404)
    return HTMLResponse(static_file.read_text(encoding="utf-8"))


# ============================================================
# Routes — Pipeline Run
# ============================================================

@app.post("/api/run")
async def trigger_run(req: Request):
    global _active_run_id
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    topic = (body.get("topic") or "").strip() or None
    genre = (body.get("genre") or "").strip() or None

    with _active_lock:
        if _active_run_id:
            raise HTTPException(409, "已有运行正在执行，请等待完成")
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        _active_run_id = run_id

    pipeline = _create_pipeline()
    _run_events[run_id] = asyncio.Queue()
    _run_progress[run_id] = {"status": "starting"}

    asyncio.create_task(_execute_in_background(run_id, pipeline, topic, genre))
    return {"run_id": run_id, "status": "started"}


@app.get("/api/stream/{run_id}")
async def stream_run(run_id: str):
    q = _run_events.get(run_id)
    if q is None:
        raise HTTPException(404, "运行未找到")

    async def generate():
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=15)
            except asyncio.TimeoutError:
                yield "event: heartbeat\ndata: \n\n"
                continue
            if event["type"] == "stage_update":
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: stage_update\ndata: {payload}\n\n"
            elif event["type"] == "agent_event":
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: agent_event\ndata: {payload}\n\n"
            elif event["type"] == "complete":
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: complete\ndata: {payload}\n\n"
                break

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ============================================================
# Routes — History
# ============================================================

@app.get("/api/runs")
async def list_runs(limit: int = Query(50, ge=1, le=500)):
    return _read_runs(limit)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    for run in _read_runs(500):
        if run.get("run_id") == run_id:
            return run
    raise HTTPException(404, "运行未找到")


# ============================================================
# Routes — Stories
# ============================================================

@app.get("/api/stories")
async def list_stories():
    return _list_story_dirs()


@app.get("/api/stories/{story_path:path}")
async def get_story(story_path: str):
    full_path = APP_ROOT / story_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "故事未找到")
    return {"path": story_path, "content": full_path.read_text(encoding="utf-8")}


# ============================================================
# Routes — Skills
# ============================================================

@app.get("/api/skills/genres")
async def list_genres():
    return skills_store.list_genres()


@app.get("/api/skills/{genre}")
async def get_skill(genre: str):
    content = skills_store.get_skill(genre)
    if content is None:
        raise HTTPException(404, f"未找到流派 '{genre}' 的技能卡")
    return {"genre": genre, "content": content}


# ============================================================
# Routes — Scheduler
# ============================================================

@app.get("/api/scheduler")
async def scheduler_status():
    global _scheduler_pipeline
    if _scheduler_pipeline is None:
        return {"active": False}
    status = _scheduler_pipeline.schedule_status()
    return status or {"active": False}


@app.post("/api/scheduler/start")
async def start_scheduler(req: Request):
    global _scheduler_pipeline
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    interval = body.get("interval", 360)
    _scheduler_pipeline = _create_pipeline()
    _scheduler_pipeline.run_scheduled(interval_minutes=interval)
    return {"status": "started", "interval": interval}


@app.post("/api/scheduler/stop")
async def stop_scheduler():
    global _scheduler_pipeline
    if _scheduler_pipeline:
        _scheduler_pipeline.stop_scheduled()
    return {"status": "stopped"}

"""Pipeline API routes."""
from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from ..request_parsing import json_body, stripped_or_none
from ..sse import queue_streaming_response
from ..services.pipeline_runtime import execute_pipeline_in_background, read_runs

router = APIRouter()


@router.post("/api/run")
async def trigger_run(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await json_body(req)
    topic = stripped_or_none(body, "topic")
    genre = stripped_or_none(body, "genre")
    chapters = body.get("chapters", 1)

    with state.active_lock:
        if state.active_run_id:
            raise HTTPException(409, "已有运行正在执行，请等待完成")
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        state.active_run_id = run_id

    state.run_events[run_id] = asyncio.Queue()
    state.run_progress[run_id] = {"status": "starting"}

    asyncio.create_task(
        execute_pipeline_in_background(state, run_id, deps.create_pipeline, topic, genre, chapters)
    )
    return {"run_id": run_id, "status": "started"}


@router.get("/api/stream/{run_id}")
async def stream_run(req: Request, run_id: str):
    state = req.app.state.runtime
    queue = state.run_events.get(run_id)
    if queue is None:
        raise HTTPException(404, "运行未找到")

    return queue_streaming_response(queue, event_types=("stage_update", "agent_event"))


@router.post("/api/run/continue")
async def continue_chapter(req: Request):
    deps = req.app.state.dependencies
    body = await json_body(req)
    topic = body.get("topic", "")
    genre = body.get("genre", "")
    existing_story = body.get("existing_story", "")
    chapter_count = body.get("chapter_count", 1)

    pipeline = deps.create_pipeline()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: pipeline.continue_chapter(topic, genre, existing_story, chapter_count),
    )
    return {"status": "ok", "path": str(result.published_url)}


@router.get("/api/runs")
async def list_runs(limit: int = Query(50, ge=1, le=500)):
    return read_runs(limit)


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    for run in read_runs(500):
        if run.get("run_id") == run_id:
            return run
    raise HTTPException(404, "运行未找到")


@router.get("/api/skills/genres")
async def list_genres(req: Request):
    deps = req.app.state.dependencies
    return deps.skills_store.list_genres()


@router.get("/api/skills/{genre}")
async def get_skill(req: Request, genre: str):
    deps = req.app.state.dependencies
    content = deps.skills_store.get_skill(genre)
    if content is None:
        raise HTTPException(404, f"未找到流派 '{genre}' 的技能卡")
    return {"genre": genre, "content": content}


@router.get("/api/scheduler")
async def scheduler_status(req: Request):
    deps = req.app.state.dependencies
    if deps.scheduler_pipeline is None:
        return {"active": False}
    status = deps.scheduler_pipeline.schedule_status()
    return status or {"active": False}


@router.post("/api/scheduler/start")
async def start_scheduler(req: Request):
    deps = req.app.state.dependencies
    body = await json_body(req)
    interval = body.get("interval", 360)
    deps.scheduler_pipeline = deps.create_pipeline()
    deps.scheduler_pipeline.run_scheduled(interval_minutes=interval)
    return {"status": "started", "interval": interval}


@router.post("/api/scheduler/stop")
async def stop_scheduler(req: Request):
    deps = req.app.state.dependencies
    if deps.scheduler_pipeline:
        deps.scheduler_pipeline.stop_scheduled()
    return {"status": "stopped"}

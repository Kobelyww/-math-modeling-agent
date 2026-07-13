"""Runtime service for fiction pipeline API."""
from __future__ import annotations

import asyncio

from ...fiction.pipeline import Pipeline, RUN_DIR
from ...storage.pipeline_storage import PipelineStorage


def read_runs(limit: int = 50) -> list[dict]:
    return PipelineStorage(RUN_DIR).read_runs(limit)


async def execute_pipeline_in_background(
    state,
    run_id: str,
    pipeline_or_factory,
    topic: str | None,
    genre: str | None,
    chapters: int = 1,
) -> None:
    q = state.run_events.setdefault(run_id, asyncio.Queue())
    loop = asyncio.get_event_loop()

    def emit_sync(stage: str, status: str, message: str, progress: int, **extra):
        asyncio.run_coroutine_threadsafe(q.put({
            "type": "stage_update",
            "data": {
                "run_id": run_id,
                "stage": stage,
                "status": status,
                "message": message,
                "progress": progress,
                **extra,
            },
        }), loop)

    def make_stream_callback():
        def callback(event: dict):
            asyncio.run_coroutine_threadsafe(q.put({
                "type": "agent_event",
                "data": {"run_id": run_id, **event},
            }), loop)

        return callback

    try:
        await q.put({"type": "stage_update", "data": {
            "run_id": run_id,
            "stage": "start",
            "status": "running",
            "message": "流水线启动中...",
            "progress": 0,
        }})

        pipeline = pipeline_or_factory() if not isinstance(pipeline_or_factory, Pipeline) else pipeline_or_factory
        result = await loop.run_in_executor(
            None,
            lambda: pipeline.run(
                topic=topic,
                genre=genre,
                chapters=chapters,
                stream_callback=make_stream_callback(),
                on_progress=emit_sync,
            ),
        )

        await q.put({"type": "complete", "data": {
            "run_id": run_id,
            "status": "completed",
            "message": "运行完成",
            "progress": 100,
            "topic": result.topic,
            "genre": result.genre,
            "stages": {
                name: {"status": stage.status, "duration_s": stage.duration_s, **stage.extra}
                for name, stage in result.stages.items()
            },
            "total_duration_s": result.total_duration_s,
            "published_url": result.published_url,
        }})
    except Exception as exc:
        await q.put({"type": "complete", "data": {
            "run_id": run_id,
            "status": "failed",
            "message": str(exc),
            "progress": 0,
            "error": str(exc),
        }})
    finally:
        state.run_progress[run_id] = {"status": "done"}
        with state.active_lock:
            if state.active_run_id == run_id:
                state.active_run_id = None

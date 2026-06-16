"""Worker entrypoint for durable short-drama video jobs."""
from __future__ import annotations

import asyncio
import logging
import sys
import time

from ..state import AppState
from .drama_video_queue import create_video_queue

logger = logging.getLogger("zhihu_fiction.video_worker")


def poll_once(
    queue=None,
    *,
    dependencies=None,
    state: AppState | None = None,
    executor=None,
    retry_executor=None,
    refresh_executor=None,
):
    """Pop one queued video job id.

    When dependencies are provided, the worker replays the persisted job payload
    and dispatches the matching execution path. Without dependencies, this keeps
    the legacy dequeue-only behavior used by lightweight smoke checks.
    """

    queue = queue or create_video_queue()
    job_id = queue.dequeue()
    if job_id is None:
        return None
    if dependencies is None:
        return job_id
    return replay_job(
        dependencies,
        state or AppState(),
        job_id,
        executor=executor,
        retry_executor=retry_executor,
        refresh_executor=refresh_executor,
    )


def replay_job(
    dependencies,
    state: AppState,
    job_id: str,
    *,
    executor=None,
    retry_executor=None,
    refresh_executor=None,
) -> dict:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        raise RuntimeError("workspace repository is not configured")

    job = repo.get_drama_video_job(job_id)
    if job is None:
        logger.warning("Dequeued missing drama video job %s", job_id)
        return {"job_id": job_id, "status": "missing"}
    if job.status != "queued":
        return {"job_id": job_id, "status": "skipped", "reason": job.status}

    if job.kind == "generate_video":
        payload = job.payload or {}
        run = repo.get_drama_video_run(job.run_id)
        story_path = str(payload.get("story_path") or getattr(run, "story_path", "") or "")
        shot_limit = int(payload.get("shot_limit") or getattr(run, "shot_limit", 1) or 1)
        stage_drafts = dict(payload.get("stage_drafts") or getattr(run, "stage_drafts", {}) or {})
        project_id = str(payload.get("project_id") or getattr(run, "project_id", "") or "")
        (executor or _execute_generate_video)(
            dependencies,
            state,
            job.run_id,
            story_path,
            shot_limit,
            stage_drafts,
            project_id,
        )
        return {"job_id": job_id, "status": "dispatched", "kind": job.kind}

    if job.kind == "retry_shot":
        shot_id = job.shot_id or str((job.payload or {}).get("shot_id") or "")
        (retry_executor or _execute_retry_shot)(
            dependencies,
            state,
            job.id,
            job.run_id,
            shot_id,
        )
        return {"job_id": job_id, "status": "dispatched", "kind": job.kind}

    if job.kind == "refresh_status":
        result = (refresh_executor or _execute_refresh_status)(
            dependencies,
            job.run_id,
            job.id,
        )
        status = result.get("status", "completed") if isinstance(result, dict) else "completed"
        return {"job_id": job_id, "status": status, "kind": job.kind}

    raise RuntimeError(f"Unsupported drama video job kind: {job.kind}")


def run_forever(interval_seconds: float = 2.0, *, dependencies=None, state: AppState | None = None) -> None:
    queue = create_video_queue()
    state = state or AppState()
    while True:
        result = poll_once(queue, dependencies=dependencies, state=state)
        if result:
            logger.info("Processed drama video job %s", result)
        time.sleep(interval_seconds)


def _execute_generate_video(
    dependencies,
    state: AppState,
    run_id: str,
    story_path: str,
    shot_limit: int,
    stage_drafts: dict[str, str],
    project_id: str = "",
):
    from . import drama_video_execution

    return asyncio.run(
        drama_video_execution.execute_video_run_in_background(
            dependencies,
            state,
            run_id,
            story_path,
            shot_limit,
            stage_drafts=stage_drafts,
            project_id=project_id,
        )
    )


def _execute_retry_shot(
    dependencies,
    state: AppState,
    retry_job_id: str,
    run_id: str,
    shot_id: str,
):
    from . import drama_video_execution

    return asyncio.run(
        drama_video_execution.execute_video_retry_job(
            dependencies,
            state,
            retry_job_id,
            run_id,
            shot_id,
        )
    )


def _execute_refresh_status(dependencies, run_id: str, job_id: str):
    from . import drama_video_execution

    return drama_video_execution.refresh_video_run_jobs(
        dependencies,
        run_id,
        job_id_factory=lambda prefix: job_id,
    )


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(arg in {"-h", "--help"} for arg in argv):
        print(
            "Usage: python -m zhihu_fiction.app.services.drama_video_worker\n\n"
            "Consumes short-drama video jobs from ZH_VIDEO_QUEUE_BACKEND and "
            "replays persisted job payloads from the workspace repository."
        )
        return
    logging.basicConfig(level=logging.INFO)
    from ..dependencies import AppDependencies

    run_forever(dependencies=AppDependencies(), state=AppState())


if __name__ == "__main__":
    main()

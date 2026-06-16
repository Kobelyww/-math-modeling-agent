"""Unified production task center routes."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from ...workspace.models import DramaVideoJob, DramaVideoRun, StoryTask, utc_now_iso

router = APIRouter()


@router.get("/api/tasks")
async def list_production_tasks(
    req: Request,
    status: str | None = Query(None),
):
    repo = req.app.state.dependencies.workspace_repo
    tasks = [
        *_normalize_video_jobs(repo.list_drama_video_jobs()),
        *_normalize_video_runs(repo.list_drama_video_runs()),
        *_normalize_story_tasks(repo.list_tasks()),
    ]

    if status:
        tasks = [task for task in tasks if task["status"] == status]

    tasks.sort(key=_task_sort_key, reverse=True)
    summary = dict(Counter(task["status"] for task in tasks))
    return {"summary": summary, "tasks": tasks}


@router.post("/api/tasks/{task_id}/retry")
async def retry_production_task(req: Request, task_id: str):
    deps = req.app.state.dependencies
    repo = deps.workspace_repo

    if repo.get_task(task_id) is not None:
        try:
            task = deps.workspace_queue.retry(task_id)
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        deps.workspace_queue.kick()
        return _normalize_story_tasks([task])[0]

    job = repo.get_drama_video_job(task_id)
    if job is None:
        raise _not_found("task")
    raise _conflict("Video jobs must be retried from their run and shot context")


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_production_task(req: Request, task_id: str):
    deps = req.app.state.dependencies
    repo = deps.workspace_repo

    if repo.get_task(task_id) is not None:
        try:
            task = deps.workspace_queue.cancel(task_id)
        except KeyError as exc:
            raise _not_found("task") from exc
        except ValueError as exc:
            raise _conflict(str(exc)) from exc
        return _normalize_story_tasks([task])[0]

    job = repo.get_drama_video_job(task_id)
    if job is None:
        raise _not_found("task")
    if job.status != "queued":
        raise _conflict("Only queued video jobs can be canceled")
    canceled = repo.update_drama_video_job(
        task_id,
        {
            "status": "canceled",
            "updated_at": utc_now_iso(),
        },
    )
    return _normalize_video_jobs([canceled])[0]


def _normalize_story_tasks(records: list[StoryTask]) -> list[dict]:
    return [
        {
            "id": task.id,
            "kind": "story_task",
            "source": "story",
            "status": task.status,
            "title": task.topic,
            "created_at": task.created_at,
            "updated_at": task.finished_at or task.started_at or task.created_at,
            "error": task.error,
            "run_id": task.run_id,
            "topic_card_id": task.topic_card_id,
            "genre": task.genre,
            "platform": task.platform,
            "priority": task.priority,
            "retry_count": task.retry_count,
            "failed_stage": task.failed_stage,
        }
        for task in records
    ]


def _normalize_video_runs(records: list[DramaVideoRun]) -> list[dict]:
    return [
        {
            "id": run.id,
            "kind": "video_run",
            "source": "video",
            "status": run.status,
            "title": _story_title(run.story_path),
            "created_at": run.created_at,
            "updated_at": run.updated_at or run.created_at,
            "error": run.error,
            "story_path": run.story_path,
            "shot_limit": run.shot_limit,
            "submitted_count": run.submitted_count,
            "jobs_path": run.jobs_path,
            "package_dir": run.package_dir,
        }
        for run in records
    ]


def _normalize_video_jobs(records: list[DramaVideoJob]) -> list[dict]:
    return [
        {
            "id": job.id,
            "kind": "video_job",
            "source": "video",
            "status": job.status,
            "title": _video_job_title(job),
            "created_at": job.created_at,
            "updated_at": job.updated_at or job.created_at,
            "error": job.error,
            "run_id": job.run_id,
            "shot_id": job.shot_id,
            "job_kind": job.kind,
            "payload": job.payload,
            "result": job.result,
        }
        for job in records
    ]


def _story_title(story_path: str) -> str:
    name = Path(story_path).name
    return name or story_path or "短剧视频任务"


def _video_job_title(job: DramaVideoJob) -> str:
    label = {
        "generate_video": "生成视频",
        "refresh_status": "刷新视频状态",
        "retry_shot": "重试镜头",
    }.get(job.kind, job.kind)
    if job.shot_id:
        return f"{label} · {job.shot_id}"
    return label


def _task_sort_key(task: dict) -> tuple[str, int, str]:
    priority = {
        "video_job": 3,
        "video_run": 2,
        "story_task": 1,
    }.get(task.get("kind", ""), 0)
    timestamp = task.get("updated_at") or task.get("created_at") or ""
    return (timestamp, priority, task.get("id", ""))


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{name} not found")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=409, detail=message)

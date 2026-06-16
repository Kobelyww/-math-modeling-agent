"""Recovery helpers for persisted short-drama video jobs."""
from __future__ import annotations

import json
from pathlib import Path

from ...workspace.models import DramaVideoJob, new_id, utc_now_iso


RECOVERABLE_STATUSES = {"queued", "running"}
PROVIDER_REPLACED_MESSAGE = "video job recovery queued provider status refresh after service restart"
STALE_JOB_MESSAGE = "video job was interrupted because the service restarted"
UNSUBMITTED_MESSAGE = "video job was interrupted before provider submission"


def drama_video_recovery_summary(repo) -> dict:
    sessions = repo.list_drama_sessions()
    jobs = repo.list_drama_video_jobs()
    awaiting = [
        session.to_dict()
        for session in sessions
        if session.status == "awaiting_confirmation"
    ]
    generating = [
        session.to_dict()
        for session in sessions
        if session.status == "generating"
    ]
    running_jobs = [
        job.to_dict()
        for job in jobs
        if job.status in RECOVERABLE_STATUSES
    ]
    failed_jobs = [
        job.to_dict()
        for job in jobs
        if job.status == "failed"
    ]
    return {
        "awaiting_confirmation_sessions": awaiting,
        "generating_sessions": generating,
        "running_jobs": running_jobs,
        "failed_jobs": failed_jobs,
        "needs_attention_count": (
            len(awaiting) + len(generating) + len(running_jobs) + len(failed_jobs)
        ),
    }


def mark_stale_video_jobs(repo) -> dict[str, int]:
    """Mark persisted in-flight video jobs failed after a service restart.

    Current video execution uses in-process background tasks. Once the process
    restarts, a queued/running job no longer has a live worker attached, so the
    safest recovery is to fail it explicitly and let the user retry.
    """

    failed = 0
    now = utc_now_iso()
    for job in repo.list_drama_video_jobs():
        if job.status not in RECOVERABLE_STATUSES:
            continue
        repo.update_drama_video_job(
            job.id,
            {
                "status": "failed",
                "error": STALE_JOB_MESSAGE,
                "updated_at": now,
            },
        )
        failed += 1
    return {"failed": failed}


def _jobs_path_has_provider_tasks(jobs_path: str) -> bool:
    if not jobs_path:
        return False
    path = Path(jobs_path)
    if not path.exists():
        return False
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("provider_job_id"):
                    return True
    except OSError:
        return False
    return False


def recover_video_jobs_after_restart(repo) -> dict[str, int]:
    """Recover persisted video work after a process restart.

    Runs that already submitted provider jobs can continue through a queued
    refresh job. Runs that never reached provider submission cannot be resumed
    by the current local worker and are marked failed with an explicit reason.
    """

    refresh_queued = 0
    failed = 0
    now = utc_now_iso()
    recovered_run_ids: set[str] = set()
    for run in repo.list_drama_video_runs():
        if run.status not in RECOVERABLE_STATUSES:
            continue
        recovered_run_ids.add(run.id)
        if _jobs_path_has_provider_tasks(run.jobs_path):
            existing_refresh = [
                job for job in repo.list_drama_video_jobs(run.id)
                if job.kind == "refresh_status" and job.status in RECOVERABLE_STATUSES
            ]
            if not existing_refresh:
                repo.save_drama_video_job(DramaVideoJob(
                    id=new_id("video_refresh"),
                    kind="refresh_status",
                    run_id=run.id,
                    status="queued",
                    payload={"run_id": run.id, "jobs_path": run.jobs_path},
                    created_at=now,
                    updated_at=now,
                ))
                refresh_queued += 1
            for job in repo.list_drama_video_jobs(run.id):
                if job.kind == "refresh_status" or job.status not in RECOVERABLE_STATUSES:
                    continue
                repo.update_drama_video_job(
                    job.id,
                    {
                        "status": "canceled",
                        "error": PROVIDER_REPLACED_MESSAGE,
                        "updated_at": now,
                    },
                )
            continue

        repo.update_drama_video_run(
            run.id,
            {
                "status": "failed",
                "error": UNSUBMITTED_MESSAGE,
                "updated_at": now,
            },
        )
        for job in repo.list_drama_video_jobs(run.id):
            if job.status in RECOVERABLE_STATUSES:
                repo.update_drama_video_job(
                    job.id,
                    {
                        "status": "failed",
                        "error": UNSUBMITTED_MESSAGE,
                        "updated_at": now,
                    },
                )
        failed += 1

    for job in repo.list_drama_video_jobs():
        if job.status not in RECOVERABLE_STATUSES:
            continue
        if job.run_id in recovered_run_ids or repo.get_drama_video_run(job.run_id) is not None:
            continue
        repo.update_drama_video_job(
            job.id,
            {
                "status": "failed",
                "error": STALE_JOB_MESSAGE,
                "updated_at": now,
            },
        )
        failed += 1
    return {"refresh_queued": refresh_queued, "failed": failed}

"""Unified short-drama video job query helpers."""
from __future__ import annotations

from fastapi import HTTPException


def list_drama_video_jobs(dependencies, run_id: str | None = None) -> dict:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        raise HTTPException(500, "workspace repository is not configured")

    jobs = repo.list_drama_video_jobs(run_id)
    summary: dict[str, int] = {}
    for job in jobs:
        summary[job.status] = summary.get(job.status, 0) + 1

    return {
        "run_id": run_id or "",
        "summary": summary,
        "state_summary": {"raw": summary, "normalized": dict(summary), "total": len(jobs)},
        "jobs": [job.to_dict() for job in jobs],
    }

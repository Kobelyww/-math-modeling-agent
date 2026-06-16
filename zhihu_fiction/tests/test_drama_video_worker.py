"""Tests for durable short-drama video worker replay."""
from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

from zhihu_fiction.app.services import drama_video_worker
from zhihu_fiction.app.state import AppState
from zhihu_fiction.workspace.models import DramaVideoJob, DramaVideoRun
from zhihu_fiction.workspace.repositories import WorkspaceRepository


class _Queue:
    def __init__(self, *job_ids: str):
        self.job_ids = list(job_ids)

    def dequeue(self):
        if not self.job_ids:
            return None
        return self.job_ids.pop(0)


def test_poll_once_keeps_legacy_dequeue_only_behavior():
    assert drama_video_worker.poll_once(_Queue("job_1")) == "job_1"


def test_poll_once_replays_generate_video_job(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(id="video_1", story_path="故事/小说正文.md"))
    repo.save_drama_video_job(
        DramaVideoJob(
            id="video_1",
            kind="generate_video",
            run_id="video_1",
            status="queued",
            payload={
                "story_path": "故事/小说正文.md",
                "shot_limit": 2,
                "stage_drafts": {"script": "确认剧本"},
                "project_id": "project_1",
            },
        )
    )
    calls = []

    def execute(dependencies, state, run_id, story_path, shot_limit, stage_drafts, project_id):
        calls.append((dependencies, state, run_id, story_path, shot_limit, stage_drafts, project_id))
        return {"status": "scheduled"}

    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()

    result = drama_video_worker.poll_once(
        _Queue("video_1"),
        dependencies=deps,
        state=state,
        executor=execute,
    )

    assert result == {"job_id": "video_1", "status": "dispatched", "kind": "generate_video"}
    assert calls == [(deps, state, "video_1", "故事/小说正文.md", 2, {"script": "确认剧本"}, "project_1")]


def test_poll_once_skips_canceled_video_job(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(
        DramaVideoJob(
            id="video_1",
            kind="generate_video",
            run_id="video_1",
            status="canceled",
        )
    )

    result = drama_video_worker.poll_once(
        _Queue("video_1"),
        dependencies=SimpleNamespace(workspace_repo=repo),
        state=AppState(),
        executor=lambda *args, **kwargs: None,
    )

    assert result == {"job_id": "video_1", "status": "skipped", "reason": "canceled"}


def test_poll_once_replays_retry_shot_job(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(
        DramaVideoJob(
            id="retry_1",
            kind="retry_shot",
            run_id="video_1",
            status="queued",
            shot_id="shot_1",
            payload={"shot_id": "shot_1"},
        )
    )
    calls = []

    def retry_executor(dependencies, state, retry_job_id, run_id, shot_id):
        calls.append((retry_job_id, run_id, shot_id))
        return {"status": "scheduled"}

    result = drama_video_worker.poll_once(
        _Queue("retry_1"),
        dependencies=SimpleNamespace(workspace_repo=repo),
        state=AppState(),
        retry_executor=retry_executor,
    )

    assert result == {"job_id": "retry_1", "status": "dispatched", "kind": "retry_shot"}
    assert calls == [("retry_1", "video_1", "shot_1")]


def test_poll_once_replays_refresh_status_job(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(
        DramaVideoJob(
            id="refresh_1",
            kind="refresh_status",
            run_id="video_1",
            status="queued",
            payload={"run_id": "video_1"},
        )
    )
    calls = []

    def refresh_executor(dependencies, run_id, job_id):
        calls.append((run_id, job_id))
        return {"status": "completed"}

    result = drama_video_worker.poll_once(
        _Queue("refresh_1"),
        dependencies=SimpleNamespace(workspace_repo=repo),
        state=AppState(),
        refresh_executor=refresh_executor,
    )

    assert result == {"job_id": "refresh_1", "status": "completed", "kind": "refresh_status"}
    assert calls == [("video_1", "refresh_1")]


def test_worker_module_help_exits_without_starting_loop():
    result = subprocess.run(
        [sys.executable, "-m", "zhihu_fiction.app.services.drama_video_worker", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout

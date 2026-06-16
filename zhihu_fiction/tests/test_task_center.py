"""Tests for the unified production task center API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.workspace.models import DramaVideoJob, DramaVideoRun, StoryTask
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_task_center_lists_story_and_video_work(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_task(
        StoryTask(
            id="story_task_1",
            topic_card_id="card_1",
            topic="山西异味事件",
            genre="现实悬疑",
            status="queued",
            priority=3,
        )
    )
    repo.save_drama_video_run(
        DramaVideoRun(
            id="video_run_1",
            story_path="故事/小说正文.md",
            status="running",
            submitted_count=1,
        )
    )
    repo.save_drama_video_job(
        DramaVideoJob(
            id="video_job_1",
            kind="generate_video",
            run_id="video_run_1",
            status="running",
            shot_id="shot_1",
        )
    )
    repo.save_drama_video_job(
        DramaVideoJob(
            id="video_retry_1",
            kind="retry_shot",
            run_id="video_run_1",
            status="queued",
            shot_id="shot_1",
        )
    )
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/tasks")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {"queued": 2, "running": 2}
    assert [item["id"] for item in data["tasks"]] == [
        "video_retry_1",
        "video_job_1",
        "video_run_1",
        "story_task_1",
    ]
    assert data["tasks"][0]["kind"] == "video_job"
    assert data["tasks"][-1]["kind"] == "story_task"


def test_task_center_filters_by_status(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_task(
        StoryTask(
            id="story_failed",
            topic_card_id="card_1",
            topic="失败故事",
            genre="悬疑",
            status="failed",
            error="模型超时",
        )
    )
    repo.save_task(
        StoryTask(
            id="story_queued",
            topic_card_id="card_2",
            topic="排队故事",
            genre="现实",
            status="queued",
        )
    )
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/tasks", params={"status": "failed"})

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {"failed": 1}
    assert [item["id"] for item in data["tasks"]] == ["story_failed"]
    assert data["tasks"][0]["error"] == "模型超时"


class _RecordingQueue:
    def __init__(self, repo):
        self.repo = repo
        self.kick_count = 0

    def retry(self, task_id: str):
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "failed":
            raise ValueError("Only failed tasks can be retried")
        return self.repo.update_task(
            task_id,
            {"status": "queued", "retry_count": task.retry_count + 1, "error": ""},
        )

    def cancel(self, task_id: str):
        task = self.repo.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.status != "queued":
            raise ValueError("Only queued tasks can be canceled")
        return self.repo.update_task(task_id, {"status": "canceled"})

    def kick(self):
        self.kick_count += 1


def test_task_center_retries_failed_story_task(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    queue = _RecordingQueue(repo)
    repo.save_task(
        StoryTask(
            id="story_failed",
            topic_card_id="card_1",
            topic="失败故事",
            genre="悬疑",
            status="failed",
            error="模型超时",
        )
    )
    deps = AppDependencies(workspace_repo=repo)
    deps.workspace_queue = queue
    client = TestClient(create_app(dependencies=deps))

    response = client.post("/api/tasks/story_failed/retry")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "story_failed"
    assert data["kind"] == "story_task"
    assert data["status"] == "queued"
    assert data["retry_count"] == 1
    assert queue.kick_count == 1


def test_task_center_cancels_queued_video_job(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(
        DramaVideoRun(
            id="video_run_1",
            story_path="故事/小说正文.md",
            status="queued",
        )
    )
    repo.save_drama_video_job(
        DramaVideoJob(
            id="video_job_1",
            kind="generate_video",
            run_id="video_run_1",
            status="queued",
        )
    )
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post("/api/tasks/video_job_1/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "video_job_1"
    assert data["kind"] == "video_job"
    assert data["status"] == "canceled"
    assert repo.get_drama_video_job("video_job_1").status == "canceled"

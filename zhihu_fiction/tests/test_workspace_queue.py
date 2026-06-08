"""Tests for single-worker workspace queue orchestration."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from zhihu_fiction.workspace.models import StoryTask
from zhihu_fiction.workspace.queue import WorkspaceQueue
from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.services import WorkspaceService


@dataclass
class FakeStage:
    status: str = "ok"
    duration_s: float = 0.1
    extra: dict | None = None


@dataclass
class FakeResult:
    run_id: str
    topic: str
    genre: str
    published_url: str
    stages: dict
    error: str = ""


class FakePipeline:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def run(
        self,
        topic=None,
        genre=None,
        chapters=1,
        stream_callback=None,
        on_progress=None,
    ):
        self.calls.append(
            {
                "topic": topic,
                "genre": genre,
                "chapters": chapters,
                "stream_callback": stream_callback,
                "on_progress": on_progress,
            }
        )
        if self.fail:
            raise RuntimeError("pipeline failed")
        return FakeResult(
            run_id="run_1",
            topic=topic,
            genre=genre,
            published_url="output/story.md",
            stages={"review": FakeStage(extra={"score": 7.5})},
        )


def _task(task_id, priority=0):
    return StoryTask(
        id=task_id,
        topic_card_id=f"card_{task_id}",
        topic=f"主题 {task_id}",
        genre="悬疑",
        priority=priority,
        created_at=f"2026-06-08T12:00:0{priority}",
    )


def _queue(tmp_path, pipeline):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    return repo, WorkspaceQueue(repo, service, lambda: pipeline)


def test_run_next_processes_one_queued_task(tmp_path):
    pipeline = FakePipeline()
    repo, queue = _queue(tmp_path, pipeline)
    task = repo.save_task(_task("task_1"))

    assert queue.run_next() is True

    updated = repo.get_task(task.id)
    assert updated.status == "needs_review"
    assert updated.run_id == "run_1"
    draft = repo.get_review_draft(task.id)
    assert draft.review_result["score"] == 7.5
    assert pipeline.calls == [
        {
            "topic": "主题 task_1",
            "genre": "悬疑",
            "chapters": 1,
            "stream_callback": None,
            "on_progress": None,
        }
    ]


def test_run_next_returns_false_when_no_queued_task(tmp_path):
    pipeline = FakePipeline()
    _, queue = _queue(tmp_path, pipeline)

    assert queue.run_next() is False
    assert pipeline.calls == []


def test_kick_starts_background_worker_until_idle(tmp_path):
    pipeline = FakePipeline()
    repo, queue = _queue(tmp_path, pipeline)
    first = repo.save_task(_task("task_1"))
    second = repo.save_task(_task("task_2"))

    assert queue.kick() is True
    assert queue.wait_until_idle()

    assert repo.get_task(first.id).status == "needs_review"
    assert repo.get_task(second.id).status == "needs_review"


def test_failed_pipeline_marks_task_failed(tmp_path):
    pipeline = FakePipeline(fail=True)
    repo, queue = _queue(tmp_path, pipeline)
    task = repo.save_task(_task("task_1"))

    assert queue.run_next() is True

    updated = repo.get_task(task.id)
    assert updated.status == "failed"
    assert "pipeline failed" in updated.error


def test_retry_failed_task_returns_to_queued(tmp_path):
    pipeline = FakePipeline()
    repo, queue = _queue(tmp_path, pipeline)
    task = repo.save_task(
        StoryTask(
            id="task_1",
            topic_card_id="card_1",
            topic="主题 task_1",
            genre="悬疑",
            status="failed",
            error="pipeline failed",
            failed_stage="pipeline",
            retry_count=1,
            started_at="2026-06-08T12:00:00",
            finished_at="2026-06-08T12:00:01",
        )
    )

    retried = queue.retry(task.id)

    assert retried.status == "queued"
    assert retried.retry_count == 2
    assert retried.error == ""
    assert retried.failed_stage == ""
    assert retried.started_at == ""
    assert retried.finished_at == ""


def test_cancel_only_cancels_queued_task(tmp_path):
    pipeline = FakePipeline()
    repo, queue = _queue(tmp_path, pipeline)
    queued = repo.save_task(_task("task_1"))
    running = repo.save_task(_task("task_2"))
    repo.update_task(running.id, {"status": "running"})

    canceled = queue.cancel(queued.id)

    assert canceled.status == "canceled"
    assert canceled.finished_at
    with pytest.raises(ValueError):
        queue.cancel(running.id)


def test_startup_repair_marks_running_failed(tmp_path):
    pipeline = FakePipeline()
    repo, queue = _queue(tmp_path, pipeline)
    task = repo.save_task(_task("task_1"))
    repo.update_task(task.id, {"status": "running"})

    repaired = queue.repair_stale_running()

    updated = repo.get_task(task.id)
    assert repaired == 1
    assert updated.status == "failed"
    assert "server restarted" in updated.error

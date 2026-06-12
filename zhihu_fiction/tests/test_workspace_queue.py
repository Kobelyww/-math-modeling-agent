"""Tests for single-worker workspace queue orchestration."""
from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest

from zhihu_fiction.workspace.models import StoryTask
from zhihu_fiction.workspace import queue as queue_module
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


class ReturningErrorPipeline(FakePipeline):
    def run(self, *args, **kwargs):
        self.calls.append(
            {
                "topic": kwargs.get("topic"),
                "genre": kwargs.get("genre"),
                "chapters": kwargs.get("chapters", 1),
                "stream_callback": kwargs.get("stream_callback"),
                "on_progress": kwargs.get("on_progress"),
            }
        )
        return FakeResult(
            run_id="run_error",
            topic=kwargs.get("topic"),
            genre=kwargs.get("genre"),
            published_url="",
            stages={"scrape": FakeStage(status="failed", extra={"error": "boom"})},
            error="scrape failed: boom",
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


def test_two_queue_instances_do_not_claim_same_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_task(_task("task_1"))
    first_pipeline = FakePipeline()
    second_pipeline = FakePipeline()
    first_queue = WorkspaceQueue(repo, WorkspaceService(repo), lambda: first_pipeline)
    second_queue = WorkspaceQueue(repo, WorkspaceService(repo), lambda: second_pipeline)
    start_barrier = threading.Barrier(2)
    claim_barrier = threading.Barrier(2)
    original_update_task = repo.update_task

    def racing_update_task(task_id, changes):
        if changes.get("status") == "running":
            try:
                claim_barrier.wait(timeout=1.0)
            except threading.BrokenBarrierError:
                pass
        return original_update_task(task_id, changes)

    repo.update_task = racing_update_task
    results: list[bool] = []
    errors: list[Exception] = []
    results_lock = threading.Lock()

    def run(queue):
        try:
            start_barrier.wait(timeout=1.0)
            result = queue.run_next()
            with results_lock:
                results.append(result)
        except Exception as exc:
            with results_lock:
                errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(first_queue,)),
        threading.Thread(target=run, args=(second_queue,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(results) == [False, True]
    assert len(first_pipeline.calls) + len(second_pipeline.calls) == 1


def test_cancel_cannot_win_against_claim_in_progress(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    task = repo.save_task(_task("task_1"))
    claim_update_started = threading.Event()
    release_claim_update = threading.Event()
    cancel_read_queued = threading.Event()
    cancel_done = threading.Event()
    pipeline_started = threading.Event()
    release_pipeline = threading.Event()

    class BlockingPipeline(FakePipeline):
        def run(self, *args, **kwargs):
            result = super().run(*args, **kwargs)
            pipeline_started.set()
            if not release_pipeline.wait(timeout=2.0):
                raise AssertionError("pipeline was not released")
            return result

    pipeline = BlockingPipeline()
    first_queue = WorkspaceQueue(repo, WorkspaceService(repo), lambda: pipeline)
    second_queue = WorkspaceQueue(repo, WorkspaceService(repo), lambda: FakePipeline())
    original_update_task = repo.update_task
    original_get_task = repo.get_task

    def paused_update_task(task_id, changes):
        if task_id == task.id and changes.get("status") == "running":
            claim_update_started.set()
            if not release_claim_update.wait(timeout=2.0):
                raise AssertionError("claim update was not released")
        return original_update_task(task_id, changes)

    def observed_get_task(task_id):
        current = original_get_task(task_id)
        if (
            threading.current_thread().name == "cancel-thread"
            and current is not None
            and current.status == "queued"
        ):
            cancel_read_queued.set()
        return current

    repo.update_task = paused_update_task
    repo.get_task = observed_get_task
    run_results: list[bool] = []
    cancel_results: list[tuple[str, str]] = []
    errors: list[Exception] = []
    results_lock = threading.Lock()

    def run_next():
        try:
            result = first_queue.run_next()
            with results_lock:
                run_results.append(result)
        except Exception as exc:
            with results_lock:
                errors.append(exc)

    def cancel_task():
        try:
            canceled = second_queue.cancel(task.id)
            with results_lock:
                cancel_results.append(("success", canceled.status))
        except ValueError as exc:
            with results_lock:
                cancel_results.append(("value_error", str(exc)))
        except Exception as exc:
            with results_lock:
                errors.append(exc)
        finally:
            cancel_done.set()

    run_thread = threading.Thread(target=run_next, name="run-next-thread")
    run_thread.start()
    assert claim_update_started.wait(timeout=1.0)

    cancel_thread = threading.Thread(target=cancel_task, name="cancel-thread")
    cancel_thread.start()
    cancel_read_queued_during_claim = cancel_read_queued.wait(timeout=1.0)

    release_claim_update.set()
    assert pipeline_started.wait(timeout=1.0)
    assert cancel_done.wait(timeout=1.0)
    release_pipeline.set()
    run_thread.join(timeout=2.0)
    cancel_thread.join(timeout=2.0)

    assert not run_thread.is_alive()
    assert not cancel_thread.is_alive()
    assert errors == []
    assert run_results == [True]
    assert len(cancel_results) == 1
    assert cancel_results[0][0] == "value_error"
    assert not cancel_read_queued_during_claim
    assert len(pipeline.calls) == 1
    assert repo.get_task(task.id).status == "needs_review"


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


def test_returned_pipeline_error_marks_task_failed_without_draft(tmp_path):
    pipeline = ReturningErrorPipeline()
    repo, queue = _queue(tmp_path, pipeline)
    task = repo.save_task(_task("task_1"))

    assert queue.run_next() is True

    updated = repo.get_task(task.id)
    assert updated.status == "failed"
    assert updated.error == "scrape failed: boom"
    assert updated.failed_stage == "scrape"
    assert updated.run_id == "run_error"
    assert repo.get_review_draft(task.id) is None


def test_read_story_body_resolves_app_root_relative_paths(tmp_path, monkeypatch):
    app_root = tmp_path / "app"
    story_path = app_root / "output" / "story.md"
    story_path.parent.mkdir(parents=True)
    story_path.write_text("app-root story body", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(queue_module, "APP_ROOT", app_root, raising=False)
    pipeline = FakePipeline()
    repo, queue = _queue(tmp_path / "workspace", pipeline)
    task = repo.save_task(_task("task_1"))

    assert queue.run_next() is True

    draft = repo.get_review_draft(task.id)
    assert draft.body == "app-root story body"


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

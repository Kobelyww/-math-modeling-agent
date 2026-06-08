"""Single-worker queue for workspace story tasks."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

from .models import StoryTask, utc_now_iso
from .repositories import WorkspaceRepository
from .services import WorkspaceService


class WorkspaceQueue:
    """Run queued story tasks one at a time."""

    def __init__(
        self,
        repo: WorkspaceRepository,
        service: WorkspaceService,
        pipeline_factory: Callable[[], Any],
    ) -> None:
        self.repo = repo
        self.service = service
        self.pipeline_factory = pipeline_factory
        self._lock = threading.Lock()
        self._worker_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None

    def repair_stale_running(self) -> int:
        with self._lock:
            running_tasks = self.repo.list_running_tasks()
            for task in running_tasks:
                self.repo.update_task(
                    task.id,
                    {
                        "status": "failed",
                        "error": (
                            "Task marked failed because server restarted while "
                            "it was running."
                        ),
                        "failed_stage": "startup_repair",
                        "finished_at": utc_now_iso(),
                    },
                )
            return len(running_tasks)

    def run_next(self) -> bool:
        with self._lock:
            if self.repo.list_running_tasks():
                return False

            queued_tasks = self.repo.list_queued_tasks()
            if not queued_tasks:
                return False

            task = self.repo.update_task(
                queued_tasks[0].id,
                {
                    "status": "running",
                    "started_at": utc_now_iso(),
                    "error": "",
                    "failed_stage": "",
                },
            )

        self._run_claimed_task(task)
        return True

    def run_until_idle(self) -> int:
        processed = 0
        while self.run_next():
            processed += 1
        return processed

    def kick(self) -> bool:
        with self._worker_lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return False

            self._worker_thread = threading.Thread(
                target=self.run_until_idle,
                daemon=True,
            )
            self._worker_thread.start()
            return True

    def wait_until_idle(self, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._worker_lock:
                thread = self._worker_thread
            if thread is None or not thread.is_alive():
                return True
            time.sleep(0.01)
        return False

    def retry(self, task_id: str) -> StoryTask:
        with self._lock:
            task = self.repo.get_task(task_id)
            if task is None:
                raise KeyError(task_id)
            if task.status != "failed":
                raise ValueError("Only failed tasks can be retried")

            return self.repo.update_task(
                task_id,
                {
                    "status": "queued",
                    "retry_count": task.retry_count + 1,
                    "error": "",
                    "failed_stage": "",
                    "started_at": "",
                    "finished_at": "",
                },
            )

    def cancel(self, task_id: str) -> StoryTask:
        with self._lock:
            task = self.repo.get_task(task_id)
            if task is None:
                raise KeyError(task_id)
            if task.status != "queued":
                raise ValueError("Only queued tasks can be canceled")

            return self.repo.update_task(
                task_id,
                {
                    "status": "canceled",
                    "finished_at": utc_now_iso(),
                },
            )

    def _run_claimed_task(self, task: StoryTask) -> None:
        try:
            pipeline = self.pipeline_factory()
            result = pipeline.run(
                topic=task.topic,
                genre=task.genre,
                chapters=task.chapters,
            )
            review_stage = result.stages.get("review")
            review_result = getattr(review_stage, "extra", None) or {}
            body = _read_story_body(result.published_url)

            self.service.create_review_draft_from_result(
                task,
                result.published_url,
                body,
                review_result,
            )
            self.repo.update_task(
                task.id,
                {
                    "status": "needs_review",
                    "run_id": result.run_id,
                    "finished_at": utc_now_iso(),
                },
            )
        except Exception as exc:
            self.repo.update_task(
                task.id,
                {
                    "status": "failed",
                    "error": str(exc),
                    "failed_stage": "pipeline",
                    "finished_at": utc_now_iso(),
                },
            )


def _read_story_body(story_path: str | Path) -> str:
    path = Path(story_path)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""

"""Queue abstraction for short-drama video background jobs."""
from __future__ import annotations

import os
from collections.abc import Callable
import json
from typing import Any


class InMemoryVideoQueue:
    """In-process queue facade used by local development and tests."""

    def __init__(self) -> None:
        self.enqueued_job_ids: list[str] = []

    def enqueue(self, job_id: str, submit: Callable[[], object]) -> object:
        self.enqueued_job_ids.append(job_id)
        return submit()

    def dequeue(self) -> str | None:
        return None


class RedisVideoQueue:
    """Redis-backed video queue for worker-based production execution."""

    backend = "redis"

    def __init__(
        self,
        url: str,
        queue_name: str = "zhihu-fiction:video-jobs",
        redis_client: Any = None,
    ) -> None:
        self.url = url
        self.queue_name = queue_name
        if redis_client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError(
                    "Install redis to use ZH_VIDEO_QUEUE_BACKEND=redis"
                ) from exc
            redis_client = redis.Redis.from_url(url)
        self.redis_client = redis_client
        self.enqueued_job_ids: list[str] = []

    def enqueue(self, job_id: str, submit: Callable[[], object]) -> object:
        self.enqueued_job_ids.append(job_id)
        payload = json.dumps({"job_id": job_id}, ensure_ascii=False)
        self.redis_client.rpush(self.queue_name, payload)
        return {"status": "queued", "job_id": job_id}

    def dequeue(self) -> str | None:
        item = self.redis_client.lpop(self.queue_name)
        if item is None:
            return None
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        data = json.loads(item)
        return str(data["job_id"])


def create_video_queue(redis_client: Any = None) -> InMemoryVideoQueue | RedisVideoQueue:
    backend = os.getenv("ZH_VIDEO_QUEUE_BACKEND", "memory").strip().lower()
    if backend in {"", "memory", "local"}:
        return InMemoryVideoQueue()
    if backend == "redis":
        return RedisVideoQueue(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            queue_name=os.getenv("ZH_REDIS_VIDEO_QUEUE_NAME", "zhihu-fiction:video-jobs"),
            redis_client=redis_client,
        )
    raise RuntimeError(f"Unsupported video queue backend: {backend}")

"""Optional queue backends for production workflow execution."""
from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol


class QueueBackendError(RuntimeError):
    """Raised when a queue backend cannot enqueue or dequeue work."""


class QueueBackend(Protocol):
    backend: str

    def enqueue(self, job_id: str, payload: dict[str, Any]) -> None:
        ...

    def dequeue(self) -> tuple[str, dict[str, Any]] | None:
        ...


@dataclass
class LocalQueueBackend:
    """In-process queue used for development and tests."""

    backend: str = "local"
    _items: deque[tuple[str, dict[str, Any]]] = field(default_factory=deque)

    def enqueue(self, job_id: str, payload: dict[str, Any]) -> None:
        self._items.append((job_id, dict(payload)))

    def dequeue(self) -> tuple[str, dict[str, Any]] | None:
        if not self._items:
            return None
        return self._items.popleft()


class RedisQueueBackend:
    """Redis list-backed queue for production workers."""

    backend = "redis"

    def __init__(
        self,
        url: str,
        queue_name: str = "zhihu-fiction:jobs",
        redis_client: Any = None,
    ) -> None:
        self.url = url
        self.queue_name = queue_name
        if redis_client is None:
            try:
                import redis
            except ImportError as exc:  # pragma: no cover - dependency optional.
                raise QueueBackendError("Install redis to use ZH_QUEUE_BACKEND=redis") from exc
            redis_client = redis.Redis.from_url(url)
        self.redis_client = redis_client

    def enqueue(self, job_id: str, payload: dict[str, Any]) -> None:
        item = json.dumps({"job_id": job_id, "payload": payload}, ensure_ascii=False)
        try:
            self.redis_client.rpush(self.queue_name, item)
        except AttributeError:
            # Allows config-only tests with a lightweight stub object.
            pass
        except Exception as exc:  # pragma: no cover - depends on Redis runtime.
            raise QueueBackendError(f"Failed to enqueue Redis job: {exc}") from exc

    def dequeue(self) -> tuple[str, dict[str, Any]] | None:
        try:
            item = self.redis_client.lpop(self.queue_name)
        except AttributeError:
            return None
        except Exception as exc:  # pragma: no cover - depends on Redis runtime.
            raise QueueBackendError(f"Failed to dequeue Redis job: {exc}") from exc
        if item is None:
            return None
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        data = json.loads(item)
        return str(data["job_id"]), dict(data.get("payload") or {})


def create_queue_backend(redis_client: Any = None) -> QueueBackend:
    backend = (os.getenv("ZH_QUEUE_BACKEND") or "local").strip().lower()
    if backend in {"", "local", "memory"}:
        return LocalQueueBackend()
    if backend == "redis":
        url = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        queue_name = os.getenv("ZH_REDIS_QUEUE_NAME", "zhihu-fiction:jobs")
        return RedisQueueBackend(url, queue_name=queue_name, redis_client=redis_client)
    raise QueueBackendError(f"Unsupported queue backend: {backend}")

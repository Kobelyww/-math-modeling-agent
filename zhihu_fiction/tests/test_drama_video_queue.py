"""Tests for short-drama video queue abstraction."""
from __future__ import annotations

import pytest

from zhihu_fiction.app.services.drama_video_queue import InMemoryVideoQueue, create_video_queue


def test_in_memory_video_queue_records_submitted_jobs():
    queue = InMemoryVideoQueue()

    result = queue.enqueue("job_1", lambda: "done")

    assert result == "done"
    assert queue.enqueued_job_ids == ["job_1"]


def test_in_memory_video_queue_dequeue_returns_none():
    queue = InMemoryVideoQueue()

    assert queue.dequeue() is None


def test_create_video_queue_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("ZH_VIDEO_QUEUE_BACKEND", raising=False)

    queue = create_video_queue()

    assert isinstance(queue, InMemoryVideoQueue)


def test_create_video_queue_rejects_unsupported_backend(monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_QUEUE_BACKEND", "unknown")

    with pytest.raises(RuntimeError, match="Unsupported video queue backend"):
        create_video_queue()


class FakeRedis:
    def __init__(self):
        self.items = []

    def rpush(self, name, value):
        self.items.append((name, value))

    def lpop(self, name):
        for index, (queue_name, value) in enumerate(self.items):
            if queue_name == name:
                self.items.pop(index)
                return value
        return None


def test_create_video_queue_returns_redis_adapter(monkeypatch):
    from zhihu_fiction.app.services.drama_video_queue import RedisVideoQueue

    fake = FakeRedis()
    monkeypatch.setenv("ZH_VIDEO_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    queue = create_video_queue(redis_client=fake)
    result = queue.enqueue("video_1", lambda: "local result")

    assert isinstance(queue, RedisVideoQueue)
    assert result == {"status": "queued", "job_id": "video_1"}
    assert queue.dequeue() == "video_1"

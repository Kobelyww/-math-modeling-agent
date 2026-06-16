"""Tests for short-drama video generation providers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from zhihu_fiction.drama.models import DramaShot
from zhihu_fiction.drama.video import (
    BailianVideoProvider,
    DramaVideoError,
    VideoJob,
    VideoJobStore,
    create_video_provider,
    load_bailian_video_config,
)


def make_shot() -> DramaShot:
    return DramaShot(
        id="ep01_sc01_sh01",
        episode_index=1,
        scene_index=1,
        shot_index=1,
        duration_seconds=6,
        location_id="living_room",
        character_ids=["heroine"],
        action="女主推门而入，盯着桌上的离婚协议。",
        dialogue="这一次，我不会再签字。",
        emotion="克制但坚定",
        camera="medium close-up, slow push in",
        visual_prompt="modern Chinese living room, cinematic lighting, tense mood",
        negative_prompt="low quality, blurry, distorted face",
        consistency_refs=["character.heroine", "location.living_room"],
    )


def test_load_bailian_video_config_uses_embedding_api_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-key")

    config = load_bailian_video_config()

    assert config.api_key == "embedding-key"
    assert config.model
    assert "dashscope" in config.submit_url


def test_load_bailian_video_config_prefers_dashscope_key(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setenv("BAILIAN_API_KEY", "bailian-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-key")

    config = load_bailian_video_config()

    assert config.api_key == "dashscope-key"


def test_load_bailian_video_config_requires_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    with pytest.raises(DramaVideoError, match="DASHSCOPE_API_KEY"):
        load_bailian_video_config()


def test_bailian_provider_submits_text_to_video_task():
    requests = []

    class StubResponse:
        status_code = 200
        text = '{"output":{"task_id":"task-123","task_status":"PENDING"},"request_id":"req-1"}'

        def json(self):
            return json.loads(self.text)

    class StubHttp:
        def post(self, url, headers=None, json=None, timeout=None):
            requests.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": timeout,
                }
            )
            return StubResponse()

    provider = BailianVideoProvider(api_key="test-key", http_client=StubHttp())

    job = provider.submit_shot(make_shot())

    assert job.provider == "bailian"
    assert job.provider_job_id == "task-123"
    assert job.status == "PENDING"
    assert job.shot_id == "ep01_sc01_sh01"
    assert requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert requests[0]["headers"]["X-DashScope-Async"] == "enable"
    assert requests[0]["json"]["model"] == provider.config.model
    assert requests[0]["json"]["input"]["prompt"].startswith("modern Chinese living room")
    assert requests[0]["json"]["parameters"]["duration"] == 6


def test_bailian_provider_reads_task_status():
    class StubResponse:
        status_code = 200
        text = (
            '{"output":{"task_id":"task-123","task_status":"SUCCEEDED",'
            '"video_url":"https://example.com/video.mp4"},"request_id":"req-2"}'
        )

        def json(self):
            return json.loads(self.text)

    class StubHttp:
        def get(self, url, headers=None, timeout=None):
            assert url.endswith("/task-123")
            assert headers["Authorization"] == "Bearer test-key"
            return StubResponse()

    provider = BailianVideoProvider(api_key="test-key", http_client=StubHttp())

    job = provider.get_job("task-123", shot_id="ep01_sc01_sh01")

    assert job.status == "SUCCEEDED"
    assert job.video_url == "https://example.com/video.mp4"


def test_bailian_provider_reads_result_url_from_results_list():
    provider = BailianVideoProvider(api_key="test-key", http_client=object())

    job = provider._job_from_response(
        data={
            "output": {
                "task_id": "task-123",
                "task_status": "SUCCEEDED",
                "results": [{"url": "https://example.com/result.mp4"}],
            }
        },
        shot_id="ep01_sc01_sh01",
    )

    assert job.video_url == "https://example.com/result.mp4"


def test_video_job_store_appends_jsonl(tmp_path):
    store = VideoJobStore(tmp_path / "video_jobs.jsonl")
    provider = BailianVideoProvider(api_key="test-key", http_client=object())
    job = provider._job_from_response(
        data={"output": {"task_id": "task-123", "task_status": "PENDING"}},
        shot_id="ep01_sc01_sh01",
    )

    store.append(job)

    rows = [
        json.loads(line)
        for line in (tmp_path / "video_jobs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows == [
        {
            "provider": "bailian",
            "provider_job_id": "task-123",
            "shot_id": "ep01_sc01_sh01",
            "status": "PENDING",
            "video_url": "",
            "error": "",
            "raw_response": {"output": {"task_id": "task-123", "task_status": "PENDING"}},
        }
    ]


def test_video_job_store_lists_and_replaces_jobs(tmp_path):
    store = VideoJobStore(tmp_path / "video_jobs.jsonl")
    pending = VideoJob(
        provider="bailian",
        provider_job_id="task-123",
        shot_id="shot_1",
        status="PENDING",
    )
    succeeded = VideoJob(
        provider="bailian",
        provider_job_id="task-123",
        shot_id="shot_1",
        status="SUCCEEDED",
        video_url="https://example.com/video.mp4",
    )
    store.append(pending)
    (tmp_path / "video_jobs.jsonl").write_text(
        (tmp_path / "video_jobs.jsonl").read_text(encoding="utf-8") + "{bad json\n",
        encoding="utf-8",
    )

    assert store.list() == [pending]

    store.replace_all([succeeded])

    assert store.list() == [succeeded]


def test_create_video_provider_defaults_to_bailian(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "test-key")

    provider = create_video_provider()

    assert isinstance(provider, BailianVideoProvider)
    assert provider.provider_name == "bailian"


def test_create_video_provider_rejects_unknown_provider():
    with pytest.raises(DramaVideoError, match="Unsupported video provider"):
        create_video_provider("unknown")

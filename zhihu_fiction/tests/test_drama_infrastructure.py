"""Tests for optional production infrastructure adapters."""
from __future__ import annotations

import json
from types import SimpleNamespace

from zhihu_fiction.app.services.infrastructure import infrastructure_status
from zhihu_fiction.drama.assets import AssetRecord, LocalAssetStore, create_asset_store
from zhihu_fiction.workspace.queue_backends import LocalQueueBackend, create_queue_backend


def test_local_asset_store_writes_and_reads_bytes(tmp_path):
    store = LocalAssetStore(tmp_path / "assets", public_base_url="/assets")

    record = store.put_bytes(
        key="drama/run_1/package.json",
        data=json.dumps({"run_id": "run_1"}).encode("utf-8"),
        content_type="application/json",
        metadata={"kind": "package"},
    )

    assert record == AssetRecord(
        key="drama/run_1/package.json",
        uri="local://drama/run_1/package.json",
        public_url="/assets/drama/run_1/package.json",
        content_type="application/json",
        size=19,
        metadata={"kind": "package"},
    )
    assert store.read_bytes("drama/run_1/package.json") == b'{"run_id": "run_1"}'


def test_create_asset_store_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.delenv("ZH_ASSET_BACKEND", raising=False)
    monkeypatch.setenv("ZH_ASSET_ROOT", str(tmp_path / "configured-assets"))

    store = create_asset_store()

    record = store.put_text("drama/run_1/readme.md", "# package", content_type="text/markdown")
    assert record.uri == "local://drama/run_1/readme.md"
    assert (tmp_path / "configured-assets" / "drama" / "run_1" / "readme.md").read_text(
        encoding="utf-8"
    ) == "# package"


def test_create_asset_store_can_build_minio_without_network(monkeypatch):
    monkeypatch.setenv("ZH_ASSET_BACKEND", "minio")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "secret")
    monkeypatch.setenv("MINIO_BUCKET", "zhihu-fiction")

    store = create_asset_store(client=object())

    assert store.backend == "minio"
    assert store.bucket == "zhihu-fiction"


def test_queue_backend_defaults_to_local(monkeypatch):
    monkeypatch.delenv("ZH_QUEUE_BACKEND", raising=False)

    backend = create_queue_backend()
    backend.enqueue("job-1", {"type": "drama"})

    assert isinstance(backend, LocalQueueBackend)
    assert backend.dequeue() == ("job-1", {"type": "drama"})


def test_queue_backend_returns_redis_adapter_without_connection(monkeypatch):
    monkeypatch.setenv("ZH_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    backend = create_queue_backend(redis_client=object())

    assert backend.backend == "redis"
    assert backend.url == "redis://localhost:6379/0"


def test_infrastructure_status_reports_configured_backends(monkeypatch):
    monkeypatch.setenv("ZH_ASSET_BACKEND", " minio ")
    monkeypatch.setenv("ZH_VIDEO_PROVIDER", "bailian")
    monkeypatch.setenv("BAILIAN_VIDEO_MODEL", "wanx2.1-t2v-plus")
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "0.2")
    dependencies = SimpleNamespace(
        workspace_repo=SimpleNamespace(backend="sqlite"),
        queue_backend=SimpleNamespace(backend="redis"),
    )

    status = infrastructure_status(dependencies)

    assert status["workspace_backend"] == "sqlite"
    assert status["queue_backend"] == "redis"
    assert status["asset_backend"] == "minio"
    assert status["video_provider"] == "bailian"
    assert status["creative_model"] == "deepseek-v4-pro"
    assert status["video_model"] == "wanx2.1-t2v-plus"
    assert status["cost_guardrail"]["billable_stage"] == "video"
    assert status["cost_guardrail"]["estimate"]["currency"] == "CNY"
    assert status["cost_guardrail"]["estimate"]["unit_price_cny"] == 0.2
    assert status["cost_guardrail"]["estimate"]["estimated_total_cny"] == 0.2

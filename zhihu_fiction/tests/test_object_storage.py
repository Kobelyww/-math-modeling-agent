"""Tests for generated video object storage."""
from __future__ import annotations

import pytest

from zhihu_fiction.app.services.object_storage import LocalObjectStorage, create_object_storage


def test_local_object_storage_puts_and_reads_text(tmp_path):
    storage = LocalObjectStorage(tmp_path / "objects")

    uri = storage.put_text("packages/video_1/manifest.json", '{"ok": true}')

    assert uri == "local://packages/video_1/manifest.json"
    assert storage.read_text(uri) == '{"ok": true}'


def test_local_object_storage_rejects_parent_traversal(tmp_path):
    storage = LocalObjectStorage(tmp_path / "objects")

    with pytest.raises(ValueError, match="Invalid object key"):
        storage.put_text("../escape.txt", "nope")


def test_create_object_storage_defaults_to_local(monkeypatch, tmp_path):
    monkeypatch.delenv("ZH_OBJECT_STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("ZH_OBJECT_STORAGE_ROOT", str(tmp_path / "objects"))

    storage = create_object_storage()

    assert isinstance(storage, LocalObjectStorage)


def test_create_object_storage_can_build_minio_without_network(monkeypatch):
    class FakeMinio:
        def __init__(self):
            self.calls = []

        def put_object(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    fake = FakeMinio()
    monkeypatch.setenv("ZH_OBJECT_STORAGE_BACKEND", "minio")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "secret")
    monkeypatch.setenv("MINIO_BUCKET", "zhihu-fiction")

    storage = create_object_storage(client=fake)

    uri = storage.put_text("packages/video_1/manifest.json", '{"ok": true}')
    assert uri == "minio://zhihu-fiction/packages/video_1/manifest.json"
    assert fake.calls[0][0][0] == "zhihu-fiction"
    assert fake.calls[0][0][1] == "packages/video_1/manifest.json"

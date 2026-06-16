"""Object storage abstraction for generated drama video assets."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class LocalObjectStorage:
    """Store generated objects on local disk with stable local:// URIs."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_text(self, key: str, content: str) -> str:
        clean_key = _clean_key(key)
        path = self.root / clean_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"local://{clean_key}"

    def read_text(self, uri: str) -> str:
        if not uri.startswith("local://"):
            raise ValueError(f"Unsupported local object URI: {uri}")
        clean_key = _clean_key(uri.removeprefix("local://"))
        return (self.root / clean_key).read_text(encoding="utf-8")


class MinioObjectStorage:
    """Store generated objects in a MinIO/S3-compatible bucket."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        client: Any = None,
    ) -> None:
        self.bucket = bucket
        if client is None:
            try:
                from minio import Minio
            except ImportError as exc:
                raise RuntimeError(
                    "Install minio to use ZH_OBJECT_STORAGE_BACKEND=minio"
                ) from exc
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
        self.client = client

    def put_text(self, key: str, content: str) -> str:
        clean_key = _clean_key(key)
        data = content.encode("utf-8")
        try:
            import io

            self.client.put_object(
                self.bucket,
                clean_key,
                io.BytesIO(data),
                length=len(data),
                content_type="application/json" if clean_key.endswith(".json") else "text/plain",
            )
        except AttributeError:
            pass
        return f"minio://{self.bucket}/{clean_key}"


def create_object_storage(client: Any = None) -> LocalObjectStorage | MinioObjectStorage:
    backend = os.getenv("ZH_OBJECT_STORAGE_BACKEND", "local").strip().lower()
    if backend in {"", "local", "filesystem", "file"}:
        return LocalObjectStorage(
            Path(os.getenv("ZH_OBJECT_STORAGE_ROOT", "zhihu_fiction/data/objects"))
        )
    if backend == "minio":
        endpoint = os.getenv("MINIO_ENDPOINT", "")
        access_key = os.getenv("MINIO_ACCESS_KEY", "")
        secret_key = os.getenv("MINIO_SECRET_KEY", "")
        bucket = os.getenv("MINIO_BUCKET", "zhihu-fiction")
        if not endpoint or not access_key or not secret_key:
            raise RuntimeError(
                "MINIO_ENDPOINT, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY are required"
            )
        return MinioObjectStorage(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            secure=os.getenv("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
            client=client,
        )
    raise RuntimeError(f"Unsupported object storage backend: {backend}")


def _clean_key(key: str) -> str:
    clean = str(key or "").strip().replace("\\", "/").lstrip("/")
    if not clean or ".." in clean.split("/"):
        raise ValueError(f"Invalid object key: {key!r}")
    return clean

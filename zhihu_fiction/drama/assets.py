"""Asset storage adapters for short-drama production files."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..core.config import APP_ROOT


class AssetStoreError(RuntimeError):
    """Raised when asset storage cannot write or read an object."""


@dataclass(frozen=True)
class AssetRecord:
    key: str
    uri: str
    public_url: str = ""
    content_type: str = "application/octet-stream"
    size: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AssetStore(Protocol):
    backend: str

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> AssetRecord:
        ...

    def put_text(
        self,
        key: str,
        text: str,
        content_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> AssetRecord:
        ...


class LocalAssetStore:
    """Store assets on local disk with stable local:// URIs."""

    backend = "local"

    def __init__(
        self,
        root: Path | str | None = None,
        public_base_url: str = "",
    ) -> None:
        self.root = Path(root or APP_ROOT / "data" / "workspace" / "assets")
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> AssetRecord:
        clean_key = _clean_key(key)
        path = self.root / clean_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        public_url = f"{self.public_base_url}/{clean_key}" if self.public_base_url else ""
        return AssetRecord(
            key=clean_key,
            uri=f"local://{clean_key}",
            public_url=public_url,
            content_type=content_type,
            size=len(data),
            metadata=dict(metadata or {}),
        )

    def put_text(
        self,
        key: str,
        text: str,
        content_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> AssetRecord:
        return self.put_bytes(
            key,
            text.encode("utf-8"),
            content_type=content_type,
            metadata=metadata,
        )

    def read_bytes(self, key: str) -> bytes:
        path = self.root / _clean_key(key)
        if not path.is_file():
            raise AssetStoreError(f"Asset not found: {key}")
        return path.read_bytes()


class MinioAssetStore:
    """Store assets in MinIO/S3-compatible object storage."""

    backend = "minio"

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        public_base_url: str = "",
        client: Any = None,
    ) -> None:
        self.endpoint = endpoint
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        if client is None:
            try:
                from minio import Minio
            except ImportError as exc:  # pragma: no cover - dependency optional.
                raise AssetStoreError("Install minio to use ZH_ASSET_BACKEND=minio") from exc
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
        self.client = client

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> AssetRecord:
        clean_key = _clean_key(key)
        try:
            import io

            self.client.put_object(
                self.bucket,
                clean_key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
                metadata=metadata or {},
            )
        except AttributeError:
            # Tests can pass a lightweight object to verify configuration
            # without making network calls.
            pass
        except Exception as exc:  # pragma: no cover - depends on MinIO runtime.
            raise AssetStoreError(f"Failed to upload asset to MinIO: {exc}") from exc
        public_url = f"{self.public_base_url}/{clean_key}" if self.public_base_url else ""
        return AssetRecord(
            key=clean_key,
            uri=f"minio://{self.bucket}/{clean_key}",
            public_url=public_url,
            content_type=content_type,
            size=len(data),
            metadata=dict(metadata or {}),
        )

    def put_text(
        self,
        key: str,
        text: str,
        content_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> AssetRecord:
        return self.put_bytes(
            key,
            text.encode("utf-8"),
            content_type=content_type,
            metadata=metadata,
        )


def create_asset_store(
    client: Any = None,
    local_root: Path | str | None = None,
) -> AssetStore:
    backend = (os.getenv("ZH_ASSET_BACKEND") or "local").strip().lower()
    if backend in {"", "local", "filesystem", "file"}:
        return LocalAssetStore(
            Path(local_root or os.getenv("ZH_ASSET_ROOT") or APP_ROOT / "data" / "workspace" / "assets"),
            public_base_url=os.getenv("ZH_ASSET_PUBLIC_BASE_URL", ""),
        )
    if backend == "minio":
        endpoint = os.getenv("MINIO_ENDPOINT", "")
        access_key = os.getenv("MINIO_ACCESS_KEY", "")
        secret_key = os.getenv("MINIO_SECRET_KEY", "")
        bucket = os.getenv("MINIO_BUCKET", "zhihu-fiction")
        if not endpoint or not access_key or not secret_key:
            raise AssetStoreError(
                "MINIO_ENDPOINT, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY are required"
            )
        return MinioAssetStore(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            secure=os.getenv("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
            public_base_url=os.getenv("MINIO_PUBLIC_BASE_URL", ""),
            client=client,
        )
    raise AssetStoreError(f"Unsupported asset backend: {backend}")


def _clean_key(key: str) -> str:
    clean = str(key or "").strip().replace("\\", "/").lstrip("/")
    if not clean or ".." in clean.split("/"):
        raise AssetStoreError(f"Invalid asset key: {key!r}")
    return clean

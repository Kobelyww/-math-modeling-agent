"""Compatibility exports for object storage adapters."""

from __future__ import annotations

from zhihu_fiction.app.services.object_storage import (
    LocalObjectStorage,
    MinioObjectStorage,
    create_object_storage,
)

__all__ = ["LocalObjectStorage", "MinioObjectStorage", "create_object_storage"]

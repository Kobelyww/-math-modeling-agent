"""Compatibility exports for Bailian/DashScope video generation."""

from __future__ import annotations

from zhihu_fiction.drama.video import (
    BailianVideoConfig,
    BailianVideoProvider,
    DramaVideoError,
    VideoJob,
    VideoJobStore,
    VideoProvider,
    create_video_provider,
    load_bailian_video_config,
)

__all__ = [
    "BailianVideoConfig",
    "BailianVideoProvider",
    "DramaVideoError",
    "VideoJob",
    "VideoJobStore",
    "VideoProvider",
    "create_video_provider",
    "load_bailian_video_config",
]

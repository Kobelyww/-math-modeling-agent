"""Compatibility aliases for Web runtime service modules."""

from __future__ import annotations

import importlib
import sys

__all__ = [
    "drama_video_deepagent_flow",
    "drama_video_execution",
    "drama_video_jobs",
    "drama_video_queue",
    "drama_video_recovery",
    "drama_video_runtime",
    "drama_video_sessions",
    "drama_video_stage_generation",
    "drama_video_worker",
    "infrastructure",
    "object_storage",
    "pipeline_runtime",
    "story_library",
]

for _name in __all__:
    _module = importlib.import_module(f"zhihu_fiction.app.services.{_name}")
    globals()[_name] = _module
    sys.modules[f"{__name__}.{_name}"] = _module

del importlib, sys, _name, _module

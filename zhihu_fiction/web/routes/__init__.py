"""Compatibility aliases for FastAPI route modules."""

from __future__ import annotations

import importlib
import sys

__all__ = [
    "costs",
    "drama_video",
    "health",
    "ip_memory",
    "pipeline",
    "projects",
    "static",
    "stories",
    "tasks",
]

for _name in __all__:
    _module = importlib.import_module(f"zhihu_fiction.app.routes.{_name}")
    globals()[_name] = _module
    sys.modules[f"{__name__}.{_name}"] = _module

del importlib, sys, _name, _module

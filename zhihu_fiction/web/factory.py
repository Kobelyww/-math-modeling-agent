"""Compatibility exports for the FastAPI app factory."""

from __future__ import annotations

from zhihu_fiction.app.factory import TimingMiddleware, create_app, global_exception_handler

__all__ = ["TimingMiddleware", "create_app", "global_exception_handler"]

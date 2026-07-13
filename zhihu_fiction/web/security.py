"""Compatibility exports for Web security helpers."""

from __future__ import annotations

from zhihu_fiction.app.security import ApiTokenMiddleware, install_security

__all__ = ["ApiTokenMiddleware", "install_security"]

"""Compatibility exports for Web request parsing helpers."""

from __future__ import annotations

from zhihu_fiction.app.request_parsing import json_body, require_stripped, stripped_or_none

__all__ = ["json_body", "require_stripped", "stripped_or_none"]

"""Compatibility helpers for the legacy ``zhihu_fiction.server`` module."""
from __future__ import annotations

import sys
from pathlib import Path


def server_attr(name: str, default=None):
    server_mod = sys.modules.get("zhihu_fiction.server")
    if server_mod is None:
        return default
    return getattr(server_mod, name, default)


def runtime_server_attr(name: str, default=None):
    value = server_attr(name, default)
    if getattr(value, "_runtime_delegate", False):
        return default
    return value


def server_path_attr(name: str, default) -> Path:
    return Path(server_attr(name, default))

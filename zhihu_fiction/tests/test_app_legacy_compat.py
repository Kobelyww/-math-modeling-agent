"""Tests for legacy server compatibility helpers."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from zhihu_fiction.app.legacy_compat import runtime_server_attr, server_attr, server_path_attr


def test_server_attr_returns_default_without_legacy_server(monkeypatch):
    monkeypatch.delitem(sys.modules, "zhihu_fiction.server", raising=False)

    assert server_attr("APP_ROOT", "default-root") == "default-root"


def test_server_attr_reads_legacy_server_override(monkeypatch, tmp_path):
    fake_server = SimpleNamespace(APP_ROOT=tmp_path)
    monkeypatch.setitem(sys.modules, "zhihu_fiction.server", fake_server)

    assert server_attr("APP_ROOT", "default-root") == tmp_path
    assert server_path_attr("APP_ROOT", "default-root") == Path(tmp_path)


def test_runtime_server_attr_ignores_runtime_delegate(monkeypatch):
    def delegate():
        return "delegate"

    delegate._runtime_delegate = True
    override = lambda: "override"
    fake_server = SimpleNamespace(delegate=delegate, override=override)
    monkeypatch.setitem(sys.modules, "zhihu_fiction.server", fake_server)

    assert runtime_server_attr("delegate", "default") == "default"
    assert runtime_server_attr("override", "default") is override

"""Tests for story file library services."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from zhihu_fiction.app.services.story_library import (
    extract_web_story_body,
    list_story_dirs,
    safe_story_file,
    story_result_from_file,
)


@pytest.fixture
def story_roots(monkeypatch, tmp_path):
    app_root = tmp_path / "app"
    output_dir = app_root / "output"
    output_dir.mkdir(parents=True)
    monkeypatch.setitem(
        sys.modules,
        "zhihu_fiction.server",
        SimpleNamespace(APP_ROOT=app_root, OUTPUT_DIR=output_dir),
    )
    return app_root, output_dir


def test_list_story_dirs_returns_story_metadata(story_roots):
    app_root, output_dir = story_roots
    story_dir = output_dir / "城市异味事件"
    story_dir.mkdir()
    story_file = story_dir / "小说正文.md"
    story_file.write_text("# 城市异味事件\n\n> 题材：现实悬疑\n\n第一段正文。", encoding="utf-8")

    stories = list_story_dirs()

    assert stories == [
        {
            "name": "城市异味事件",
            "path": str(story_file.relative_to(app_root)),
            "excerpt": "第一段正文。",
            "created_at": stories[0]["created_at"],
        }
    ]


def test_story_result_from_file_extracts_topic_genre_and_body(story_roots):
    _, output_dir = story_roots
    story_dir = output_dir / "城市异味事件"
    story_dir.mkdir()
    story_file = story_dir / "小说正文.md"
    story_file.write_text(
        "# 山西运城异味事件\n\n> 题材：现实悬疑\n\n正文内容\n\n# 发布方案\n\n发布建议",
        encoding="utf-8",
    )

    result = story_result_from_file(story_file)

    assert result.topic == "山西运城异味事件"
    assert result.genre == "现实悬疑"
    assert result.final_story == "正文内容"
    assert result.synthesis == "发布建议"


def test_extract_web_story_body_falls_back_to_markdown_sections():
    story, synthesis = extract_web_story_body(
        "# 标题\n\n> 题材：悬疑\n\n正文第一段\n\n# 发布方案\n\n发布建议"
    )

    assert story == "正文第一段"
    assert synthesis == "发布建议"


def test_safe_story_file_rejects_path_traversal(story_roots):
    with pytest.raises(HTTPException) as exc_info:
        safe_story_file("../secret.md")

    assert exc_info.value.status_code == 400

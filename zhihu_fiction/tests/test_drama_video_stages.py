"""Tests for short-drama stage definitions and request parsing."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from zhihu_fiction.app.drama_video_stages import (
    DEEPAGENT_STAGES,
    STAGE_LABELS,
    assert_previous_stages_confirmed,
    next_unconfirmed_stage,
    parse_shot_limit,
    parse_stage_drafts,
)


def test_parse_shot_limit_clamps_invalid_and_large_values():
    assert parse_shot_limit(None) == 1
    assert parse_shot_limit("bad") == 1
    assert parse_shot_limit(0) == 1
    assert parse_shot_limit(99) == 20


def test_parse_stage_drafts_keeps_known_text_stages_only():
    drafts = parse_stage_drafts({
        "script": "  剧本  ",
        "video": "不应进入创作上下文",
        "unknown": "忽略",
        "style": 123,
    })

    assert drafts == {"script": "剧本", "video": "不应进入创作上下文"}


def test_next_unconfirmed_stage_follows_deepagent_order():
    spec = {"confirmed_stages": ["script", "style"]}

    assert DEEPAGENT_STAGES[0] == "script"
    assert STAGE_LABELS["storyboard"] == "分镜"
    assert next_unconfirmed_stage(spec) == "plot"
    assert next_unconfirmed_stage({"confirmed_stages": list(DEEPAGENT_STAGES)}) is None


def test_assert_previous_stages_confirmed_rejects_out_of_order_stage():
    with pytest.raises(HTTPException) as exc_info:
        assert_previous_stages_confirmed({"confirmed_stages": []}, "style")

    assert exc_info.value.status_code == 409
    assert "请先确认剧本" in exc_info.value.detail

"""Tests for structured short-drama stage assets."""
from __future__ import annotations

from zhihu_fiction.drama.stage_assets import (
    estimate_video_cost,
    normalize_stage_asset,
    validate_stage_asset,
)


def test_normalize_storyboard_extracts_numbered_shots():
    text = """
1. 场景：林家客厅
人物：林夏
动作：她推门而入，盯着桌上的离婚协议。
对白：这一次，我不会再签字。
镜头：中近景，缓慢推进
时长：6秒

2. 场景：客厅门口
人物：继母
动作：继母伸手抢录音笔。
对白：你敢！
镜头：手持跟拍
时长：5秒
"""

    asset = normalize_stage_asset("storyboard", text)

    assert asset["stage"] == "storyboard"
    assert asset["raw"] == text.strip()
    assert asset["shots"] == [
        {
            "index": 1,
            "scene": "林家客厅",
            "characters": ["林夏"],
            "action": "她推门而入，盯着桌上的离婚协议。",
            "dialogue": "这一次，我不会再签字。",
            "camera": "中近景，缓慢推进",
            "duration_seconds": 6,
        },
        {
            "index": 2,
            "scene": "客厅门口",
            "characters": ["继母"],
            "action": "继母伸手抢录音笔。",
            "dialogue": "你敢！",
            "camera": "手持跟拍",
            "duration_seconds": 5,
        },
    ]


def test_normalize_non_storyboard_keeps_sections():
    asset = normalize_stage_asset(
        "style",
        "视觉基调：现代都市冷色\n镜头语言：中近景压迫感\n负面约束：避免夸张滤镜",
    )

    assert asset["stage"] == "style"
    assert asset["sections"] == {
        "视觉基调": "现代都市冷色",
        "镜头语言": "中近景压迫感",
        "负面约束": "避免夸张滤镜",
    }


def test_estimate_video_cost_uses_guardrails():
    estimate = estimate_video_cost(shot_count=7, seconds_per_shot=6, unit_price_cny=0.8)

    assert estimate == {
        "currency": "CNY",
        "shot_count": 7,
        "seconds_per_shot": 6,
        "estimated_seconds": 42,
        "unit_price_cny": 0.8,
        "estimated_total_cny": 5.6,
    }


def test_validate_stage_asset_rejects_placeholder_script():
    result = validate_stage_asset("script", "script confirmed")

    assert result["valid"] is False
    assert result["stage"] == "script"
    assert "内容过短" in result["errors"]
    assert "缺少剧本结构" in result["errors"]


def test_validate_stage_asset_accepts_production_storyboard():
    text = """
1. 场景：陆家小院 夜晚
人物：陆沉舟、小满
动作：小满突然剧烈咳嗽，陆沉舟抱起孩子冲向院门。
对白：陆沉舟：打120！不要等！
镜头：手持中近景快速推进，压迫感强
时长：6秒
视频生成Prompt：竖屏短剧，夜晚小院，淡黄色雾气，焦急奔跑，真实纪实风格
"""

    result = validate_stage_asset("storyboard", text)

    assert result["valid"] is True
    assert result["score"] >= 0.8
    assert result["summary"]["shot_count"] == 1

"""Tests for short-drama DeepAgent stage generation helpers."""
from __future__ import annotations

from dataclasses import dataclass

from zhihu_fiction.app.services.drama_video_stage_generation import (
    build_stage_prompt,
    deepseek_v4pro_settings,
    format_stage_context,
)


@dataclass
class FakeSettings:
    model: str = "deepseek-chat"
    api_key: str = "key"


@dataclass
class FakeResult:
    topic: str = "测试主题"
    genre: str = "悬疑"
    synthesis: str = "发布方案"
    final_story: str = "小说正文"


def test_deepseek_v4pro_settings_replaces_model_without_losing_fields():
    settings = deepseek_v4pro_settings(FakeSettings())

    assert settings.model == "deepseek-v4-pro"
    assert settings.api_key == "key"


def test_format_stage_context_uses_confirmed_text_stages_only():
    context = format_stage_context({
        "script": "确认剧本",
        "style": "确认风格",
        "video": "视频阶段不进入前序创作上下文",
    })

    assert "【剧本已确认稿】\n确认剧本" in context
    assert "【风格设计已确认稿】\n确认风格" in context
    assert "视频阶段不进入前序创作上下文" not in context


def test_build_stage_prompt_contains_stage_instruction_and_story():
    prompt = build_stage_prompt(FakeResult(), "storyboard", {"script": "确认剧本"})

    assert "当前要创作的生产阶段：分镜" in prompt
    assert "生成分镜方案" in prompt
    assert "【剧本已确认稿】" in prompt
    assert "小说正文" in prompt

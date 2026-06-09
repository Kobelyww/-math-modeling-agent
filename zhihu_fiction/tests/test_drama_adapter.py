"""Tests for LLM-based novel-to-drama adaptation."""
from __future__ import annotations

import json

import pytest

from zhihu_fiction.drama.adapter import DramaAdapter, DramaAdapterError, extract_json_object


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeLLM received more calls than expected")
        return FakeResponse(self.responses.pop(0))


def valid_project_payload() -> dict:
    shots = [
        {
            "id": f"ep01_sc01_sh{i:02d}",
            "episode_index": 1,
            "scene_index": 1,
            "shot_index": i,
            "duration_seconds": 6,
            "location_id": "living_room",
            "character_ids": ["heroine"],
            "action": f"女主完成第 {i} 个关键动作。",
            "dialogue": "我不会再退让。",
            "emotion": "克制但坚定",
            "camera": "medium close-up, slow push in",
            "visual_prompt": "modern Chinese living room, cinematic lighting",
            "negative_prompt": "low quality, blurry, distorted face",
            "consistency_refs": ["character.heroine", "location.living_room"],
        }
        for i in range(1, 7)
    ]
    return {
        "title": "重生后我不再忍让",
        "source_title": "测试主题",
        "genre": "复仇",
        "logline": "被背叛的女主重生后用真相反击。",
        "audience": "喜欢复仇爽感和家庭冲突的短剧观众",
        "episode_count": 1,
        "characters": [
            {
                "id": "heroine",
                "name": "林夏",
                "role": "女主",
                "age_range": "25-30",
                "appearance": "黑色长发，冷静克制，眼神坚定",
                "costume": "白色衬衫和深色长裤",
                "personality": "隐忍、聪明、行动果断",
                "motivation": "查清背叛真相并夺回人生",
                "consistency_prompt": "林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            }
        ],
        "locations": [
            {
                "id": "living_room",
                "name": "林家客厅",
                "visual_style": "现代中式家庭客厅，压抑而整洁",
                "time_period": "现代",
                "lighting": "夜晚室内暖光，局部阴影",
                "consistency_prompt": "modern Chinese family living room, warm indoor light, tense mood",
            }
        ],
        "episodes": [
            {
                "index": 1,
                "title": "重生醒来",
                "hook": "女主在被害当天醒来，发现时间倒流。",
                "synopsis": "林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                "cliffhanger": "她拿出录音笔，继母脸色骤变。",
                "shots": shots,
            }
        ],
        "adaptation_notes": ["保留原小说的复仇主线，压缩支线。"],
        "risk_notes": ["避免过度暴力和违法细节。"],
    }


def test_extract_json_object_from_markdown_fence():
    text = '说明\n```json\n{"a": 1, "b": {"c": 2}}\n```\n结束'
    assert extract_json_object(text) == '{"a": 1, "b": {"c": 2}}'


def test_adapter_parses_valid_llm_json():
    blueprint = {"episode_count": 1, "notes": ["保留复仇主线"]}
    payload = valid_project_payload()
    llm = FakeLLM([
        json.dumps(blueprint, ensure_ascii=False),
        json.dumps(payload, ensure_ascii=False),
    ])

    project = DramaAdapter(llm).adapt(
        source_title="测试主题",
        genre="复仇",
        story="女主被陷害后重生，决定反击。",
        synthesis="发布方案",
    )

    assert project.title == "重生后我不再忍让"
    assert project.episode_count == 1
    assert project.total_shots == 6
    assert len(llm.prompts) == 2
    assert "测试主题" in llm.prompts[0]
    assert "保留复仇主线" in llm.prompts[1]


def test_adapter_rejects_empty_story():
    llm = FakeLLM([])

    with pytest.raises(DramaAdapterError, match="story is empty"):
        DramaAdapter(llm).adapt(
            source_title="测试主题",
            genre="复仇",
            story="",
            synthesis="",
        )


def test_adapter_preserves_raw_output_for_invalid_json():
    llm = FakeLLM([
        '{"episode_count": 1}',
        "这不是 JSON",
    ])

    with pytest.raises(DramaAdapterError) as exc_info:
        DramaAdapter(llm).adapt(
            source_title="测试主题",
            genre="复仇",
            story="女主被陷害后重生。",
            synthesis="发布方案",
        )

    assert "Could not parse drama project JSON" in str(exc_info.value)
    assert exc_info.value.raw_output == "这不是 JSON"


def test_adapter_wraps_validation_errors_with_raw_output():
    payload = valid_project_payload()
    payload["episode_count"] = 11
    llm = FakeLLM([
        '{"episode_count": 11}',
        json.dumps(payload, ensure_ascii=False),
    ])

    with pytest.raises(DramaAdapterError) as exc_info:
        DramaAdapter(llm).adapt(
            source_title="测试主题",
            genre="复仇",
            story="女主被陷害后重生。",
            synthesis="发布方案",
        )

    assert "episode_count" in str(exc_info.value)
    assert "episode_count" in exc_info.value.raw_output

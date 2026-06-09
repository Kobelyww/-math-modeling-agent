"""Tests for short-drama domain models."""
from __future__ import annotations

import pytest

from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
    DramaValidationError,
)


def _shots(count: int = 6) -> list[DramaShot]:
    return [
        DramaShot(
            id=f"ep01_sc01_sh{i:02d}",
            episode_index=1,
            scene_index=1,
            shot_index=i,
            duration_seconds=6,
            location_id="living_room",
            character_ids=["heroine"],
            action=f"女主完成第 {i} 个关键动作。",
            dialogue="我不会再退让。",
            emotion="克制但坚定",
            camera="medium close-up, slow push in",
            visual_prompt="modern Chinese living room, cinematic lighting, medium close-up",
            negative_prompt="low quality, blurry, distorted face",
            consistency_refs=["character.heroine", "location.living_room"],
        )
        for i in range(1, count + 1)
    ]


def make_project(**overrides) -> DramaProject:
    project = DramaProject(
        title="重生后我不再忍让",
        source_title="测试主题",
        genre="复仇",
        logline="被背叛的女主重生后用真相反击。",
        audience="喜欢复仇爽感和家庭冲突的短剧观众",
        episode_count=1,
        characters=[
            DramaCharacter(
                id="heroine",
                name="林夏",
                role="女主",
                age_range="25-30",
                appearance="黑色长发，冷静克制，眼神坚定",
                costume="白色衬衫和深色长裤",
                personality="隐忍、聪明、行动果断",
                motivation="查清背叛真相并夺回人生",
                consistency_prompt="林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            )
        ],
        locations=[
            DramaLocation(
                id="living_room",
                name="林家客厅",
                visual_style="现代中式家庭客厅，压抑而整洁",
                time_period="现代",
                lighting="夜晚室内暖光，局部阴影",
                consistency_prompt="modern Chinese family living room, warm indoor light, tense mood",
            )
        ],
        episodes=[
            DramaEpisode(
                index=1,
                title="重生醒来",
                hook="女主在被害当天醒来，发现时间倒流。",
                synopsis="林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                cliffhanger="她拿出录音笔，继母脸色骤变。",
                shots=_shots(),
            )
        ],
        adaptation_notes=["保留原小说的复仇主线，压缩支线。"],
        risk_notes=["避免过度暴力和违法细节。"],
    )
    for key, value in overrides.items():
        setattr(project, key, value)
    return project


def test_project_serializes_to_dict_and_back():
    project = make_project()

    data = project.to_dict()
    restored = DramaProject.from_dict(data)

    assert restored.title == "重生后我不再忍让"
    assert restored.episode_count == 1
    assert restored.total_shots == 6
    assert restored.characters[0].id == "heroine"
    assert restored.episodes[0].shots[0].visual_prompt


def test_rejects_more_than_ten_episodes():
    episodes = [
        DramaEpisode(
            index=i,
            title=f"第{i}集",
            hook="开场钩子",
            synopsis="剧情简介",
            cliffhanger="结尾反转",
            shots=[
                DramaShot(
                    id=f"ep{i:02d}_sc01_sh{j:02d}",
                    episode_index=i,
                    scene_index=1,
                    shot_index=j,
                    duration_seconds=6,
                    location_id="living_room",
                    character_ids=["heroine"],
                    action="角色行动",
                    dialogue="对白",
                    emotion="紧张",
                    camera="medium shot",
                    visual_prompt="cinematic shot",
                    negative_prompt="low quality",
                    consistency_refs=["character.heroine", "location.living_room"],
                )
                for j in range(1, 7)
            ],
        )
        for i in range(1, 12)
    ]
    project = make_project(episode_count=11, episodes=episodes)

    with pytest.raises(DramaValidationError, match="episode_count"):
        project.validate()


def test_rejects_invalid_shot_duration():
    project = make_project()
    project.episodes[0].shots[0].duration_seconds = 9

    with pytest.raises(DramaValidationError, match="duration_seconds"):
        project.validate()


def test_rejects_unknown_character_reference():
    project = make_project()
    project.episodes[0].shots[0].character_ids = ["unknown"]

    with pytest.raises(DramaValidationError, match="unknown character"):
        project.validate()


def test_rejects_unknown_location_reference():
    project = make_project()
    project.episodes[0].shots[0].location_id = "unknown_location"

    with pytest.raises(DramaValidationError, match="unknown location"):
        project.validate()


def test_rejects_blank_character_id():
    project = make_project()
    project.characters[0].id = " "

    with pytest.raises(DramaValidationError, match="character id is required"):
        project.validate()


def test_rejects_blank_location_id():
    project = make_project()
    project.locations[0].id = ""

    with pytest.raises(DramaValidationError, match="location id is required"):
        project.validate()


def test_from_dict_rejects_malformed_episode_count():
    data = make_project().to_dict()
    data["episode_count"] = "many"

    with pytest.raises(DramaValidationError, match="episode_count"):
        DramaProject.from_dict(data)


def test_rejects_episode_with_too_few_shots():
    project = make_project()
    project.episodes[0].shots = project.episodes[0].shots[:5]

    with pytest.raises(DramaValidationError, match="6-12 shots"):
        project.validate()

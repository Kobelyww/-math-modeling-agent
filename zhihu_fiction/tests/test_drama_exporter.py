"""Tests for short-drama prompt package export."""
from __future__ import annotations

import json

from zhihu_fiction.drama.exporter import DramaExporter
from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
)


def make_project() -> DramaProject:
    shots = [
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
            visual_prompt="modern Chinese living room, cinematic lighting",
            negative_prompt="low quality, blurry, distorted face",
            consistency_refs=["character.heroine", "location.living_room"],
        )
        for i in range(1, 7)
    ]
    return DramaProject(
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
                shots=shots,
            )
        ],
        adaptation_notes=["保留原小说的复仇主线，压缩支线。"],
        risk_notes=["避免过度暴力和违法细节。"],
    )


def test_exporter_writes_prompt_package_files(tmp_path):
    exporter = DramaExporter(output_root=tmp_path, now_fn=lambda: "20260609_120000")

    package_dir = exporter.export(make_project())

    assert package_dir.name == "短剧视频Prompt包_20260609_120000"
    assert (package_dir / "manifest.json").exists()
    assert (package_dir / "改编方案.md").exists()
    assert (package_dir / "角色一致性设定.md").exists()
    assert (package_dir / "分集剧本.md").exists()
    assert (package_dir / "镜头表.json").exists()
    assert (package_dir / "视频生成Prompts.md").exists()

    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "重生后我不再忍让"
    assert manifest["episode_count"] == 1
    assert manifest["shot_count"] == 6

    shot_table = json.loads((package_dir / "镜头表.json").read_text(encoding="utf-8"))
    assert shot_table[0]["id"] == "ep01_sc01_sh01"
    assert shot_table[0]["visual_prompt"]


def test_exporter_uses_unique_directory_when_target_exists(tmp_path):
    exporter = DramaExporter(output_root=tmp_path, now_fn=lambda: "20260609_120000")

    first = exporter.export(make_project())
    second = exporter.export(make_project())

    assert first != second
    assert second.name == "短剧视频Prompt包_20260609_120000_2"


def test_export_failure_writes_error_and_raw_output(tmp_path):
    exporter = DramaExporter(output_root=tmp_path, now_fn=lambda: "20260609_120000")

    package_dir = exporter.export_failure(
        source_title="测试主题",
        raw_output="模型原始输出",
        error="Could not parse drama project JSON",
    )

    assert (package_dir / "raw_output.txt").read_text(encoding="utf-8") == "模型原始输出"
    assert "Could not parse" in (package_dir / "error.txt").read_text(encoding="utf-8")

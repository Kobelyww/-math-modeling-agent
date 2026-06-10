"""Tests for the CLI /drama command."""
from __future__ import annotations

from pathlib import Path

import zhihu_fiction.cli as cli_mod
from zhihu_fiction.cli import CLI
from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
)
from zhihu_fiction.orchestrator import WorkflowResult


def make_result() -> WorkflowResult:
    return WorkflowResult(
        topic="测试主题",
        genre="复仇",
        topic_analysis="",
        outline="",
        draft="",
        polished="女主被陷害后重生，决定反击。",
        review="",
        synthesis="发布方案",
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


def test_cmd_drama_requires_loaded_story(capsys):
    cli = CLI.__new__(CLI)
    cli.last_result = None

    cli.cmd_drama()

    captured = capsys.readouterr()
    assert "没有可转换的小说" in captured.out
    assert "/create" in captured.out
    assert "/load" in captured.out


def test_cmd_drama_generates_package(monkeypatch, tmp_path, capsys):
    project = make_project()

    class StubAdapter:
        def __init__(self, llm):
            self.llm = llm

        def adapt_result(self, result):
            assert result.topic == "测试主题"
            return project

    class StubExporter:
        def export(self, exported_project):
            assert exported_project is project
            return tmp_path / "短剧视频Prompt包_20260609_120000"

        def export_failure(self, source_title, raw_output, error):
            raise AssertionError("export_failure should not be called")

    monkeypatch.setattr(cli_mod, "create_llm", lambda settings, temperature=0.3: object())
    monkeypatch.setattr(cli_mod, "DramaAdapter", StubAdapter)
    monkeypatch.setattr(cli_mod, "DramaExporter", StubExporter)

    cli = CLI.__new__(CLI)
    cli.settings = object()
    cli.last_result = make_result()

    cli.cmd_drama()

    captured = capsys.readouterr()
    assert "短剧 Prompt 包已生成" in captured.out
    assert "共 1 集，6 个镜头" in captured.out
    assert str(tmp_path) in captured.out

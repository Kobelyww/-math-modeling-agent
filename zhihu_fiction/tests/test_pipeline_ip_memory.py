"""Tests for Pipeline IP memory integration."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

from zhihu_fiction.ip_memory.models import CharacterCard, IPMemory, StoryBible, StyleGuide
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.pipeline import Pipeline


@pytest.fixture(autouse=True)
def _isolate_pipeline_output(tmp_path, monkeypatch):
    """Redirect Pipeline output to a temp directory so tests don't write real state."""
    import zhihu_fiction.pipeline as pmod

    monkeypatch.setattr(pmod, "RUN_DIR", tmp_path / ".pipeline")
    monkeypatch.setattr(pmod, "SCHEDULE_FILE", tmp_path / ".pipeline" / "schedule.json")
    monkeypatch.setattr(pmod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(pmod, "moderate_content", lambda llm, text: text)


def _make_pipeline(*, coordinator=None, reviewer=None, publisher=None, llm=None) -> Pipeline:
    return Pipeline(
        coordinator=coordinator or MagicMock(),
        reviewer=reviewer or MagicMock(),
        llm=llm or MagicMock(),
        publisher=publisher or MagicMock(),
        scraper=MagicMock(return_value=[{"title": "热榜1", "hot_score": 5000, "excerpt": ""}]),
        quality_threshold=6.0,
        max_rewrites=0,
    )


def test_run_coordinator_includes_memory_context_in_normal_prompt():
    from zhihu_fiction.orchestrator import run_coordinator

    captured = {}

    class CapturingCoordinator:
        def invoke(self, input_msg):
            captured["prompt"] = input_msg["messages"][0]["content"]
            return {
                "messages": [
                    HumanMessage(content="【小说正文】\n完整小说内容\n【发布方案】\n发布方案内容")
                ]
            }

    run_coordinator(
        MagicMock(),
        CapturingCoordinator(),
        topic="雨夜归来",
        memory_context="角色林晚必须保留录音证据线。",
    )

    assert "【创作记忆】" in captured["prompt"]
    assert "角色林晚必须保留录音证据线。" in captured["prompt"]
    assert "角色" in captured["prompt"]
    assert "世界" in captured["prompt"]
    assert "伏笔" in captured["prompt"]
    assert "风格" in captured["prompt"]


def test_pipeline_passes_prior_memory_context_to_chapter_generation(tmp_path):
    captured_prompts: list[str] = []

    class CapturingCoordinator:
        def invoke(self, input_msg):
            captured_prompts.append(input_msg["messages"][0]["content"])
            return {
                "messages": [
                    HumanMessage(content="【小说正文】\n林晚继续追查录音证据。\n【发布方案】\n发布方案")
                ]
            }

    reviewer = MagicMock()
    reviewer.review.return_value = {"total_score": 7.0, "full_report": "ok"}
    publisher = MagicMock()
    publisher.publish.return_value = {"success": True, "url": "https://example.test/story"}
    pipeline = _make_pipeline(coordinator=CapturingCoordinator(), reviewer=reviewer, publisher=publisher)
    pipeline._ip_memory_repo = IPMemoryRepository(tmp_path / "ip_memory")
    pipeline._ip_memory_repo.save(
        IPMemory(
            project_id="run-memory",
            story_bible=StoryBible(title="旧记忆", genre="复仇爽文"),
            characters=[CharacterCard(id="char_linwan", name="林晚", motivation="守住录音证据")],
            style_guide=StyleGuide(tone="冷静克制"),
        )
    )

    result = pipeline.run(topic="雨夜归来", genre="复仇爽文", _resume_state={"run_id": "run-memory"})

    assert result.run_id == "run-memory"
    assert any("【创作记忆】" in prompt for prompt in captured_prompts)
    assert any("林晚" in prompt and "守住录音证据" in prompt for prompt in captured_prompts)


def test_pipeline_refreshes_memory_between_fresh_chapters(tmp_path):
    captured_prompts: list[str] = []
    chapter_stories = [
        "林晚在山西运城的雨夜醒来。三年前，她被继母周岚赶出家门。"
        "这一次，林晚带着父亲死亡的录音证据归来。",
        "第二章里，林晚继续追查真相。",
    ]

    class CapturingCoordinator:
        def invoke(self, input_msg):
            captured_prompts.append(input_msg["messages"][0]["content"])
            story = chapter_stories[len(captured_prompts) - 1]
            return {
                "messages": [
                    HumanMessage(content=f"【小说正文】\n{story}\n【发布方案】\n发布方案")
                ]
            }

    reviewer = MagicMock()
    reviewer.review.return_value = {"total_score": 7.5, "full_report": "ok"}
    publisher = MagicMock()
    publisher.publish.return_value = {"success": True, "url": "https://example.test/story"}
    pipeline = _make_pipeline(coordinator=CapturingCoordinator(), reviewer=reviewer, publisher=publisher)
    pipeline._ip_memory_repo = IPMemoryRepository(tmp_path / "ip_memory")

    result = pipeline.run(
        topic="雨夜归来",
        genre="复仇爽文",
        chapters=2,
        _resume_state={"run_id": "fresh-two-chapters"},
    )

    assert result.error == ""
    assert len(captured_prompts) == 2
    second_prompt = captured_prompts[1]
    assert "【创作记忆】" in second_prompt
    assert "林晚" in second_prompt
    assert "录音证据" in second_prompt
    assert "运城" in second_prompt


def test_pipeline_extracts_memory_after_story_save(tmp_path):
    coordinator = MagicMock()
    coordinator.invoke.return_value = {
        "messages": [
            HumanMessage(
                content=(
                    "【小说正文】\n"
                    "林晚在山西运城的雨夜醒来。三年前，她被继母周岚赶出家门。\n"
                    "这一次，林晚带着父亲死亡的录音证据归来。\n"
                    "【发布方案】\n发布方案"
                )
            )
        ]
    }
    reviewer = MagicMock()
    reviewer.review.return_value = {"total_score": 7.5, "full_report": "ok"}
    publisher = MagicMock()
    publisher.publish.return_value = {"success": True, "url": "https://example.test/story"}
    pipeline = _make_pipeline(coordinator=coordinator, reviewer=reviewer, publisher=publisher)
    pipeline._ip_memory_repo = IPMemoryRepository(tmp_path / "ip_memory")

    result = pipeline.run(topic="雨夜归来", genre="复仇爽文", _resume_state={"run_id": "memory-run"})

    memory = pipeline._ip_memory_repo.load(result.run_id)
    assert memory is not None
    assert memory.project_id == "memory-run"
    assert memory.story_bible.title == "雨夜归来"
    assert any(card.name == "林晚" for card in memory.characters)
    assert result.stages["ip_memory"].status == "ok"
    assert result.stages["ip_memory"].extra["project_id"] == "memory-run"
    assert result.stages["ip_memory"].extra["story_ref"].endswith(".md")
    assert result.stages["ip_memory"].extra["snapshot_hash"].startswith("sha256:")
    assert result.stages["ip_memory"].extra["characters"] >= 1
    assert result.stages["ip_memory"].extra["world_facts"] >= 1

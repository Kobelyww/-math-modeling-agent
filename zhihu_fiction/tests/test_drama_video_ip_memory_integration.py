"""Integration tests for IP memory in drama-video stage generation."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from zhihu_fiction.app.services import drama_video_stage_generation as stage_generation
from zhihu_fiction.ip_memory.models import CharacterCard, IPMemory, StoryBible
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.orchestrator import WorkflowResult, run_drama_video_coordinator


@dataclass
class FakeResult:
    topic: str = "雨夜重生"
    genre: str = "悬疑"
    synthesis: str = "发布方案"
    final_story: str = "林晚发现录音证据。"


def make_memory(project_id: str = "雨夜重生") -> IPMemory:
    return IPMemory(
        project_id=project_id,
        story_bible=StoryBible(title="雨夜重生", premise="林晚带着证据重启人生"),
        characters=[CharacterCard(id="char_linwan", name="林晚", role="女主")],
    )


def test_build_stage_prompt_includes_ip_memory_context():
    memory = make_memory()

    prompt = stage_generation.build_stage_prompt(
        FakeResult(),
        "storyboard",
        {"script": "确认剧本"},
        ip_memory=memory,
    )

    assert "【IP记忆】" in prompt
    assert "林晚" in prompt


def test_run_stage_deepagent_rejects_unknown_stage_without_memory_lookup():
    class ExplodingRepo:
        def load(self, project_id: str):
            raise AssertionError(f"memory lookup should not run for {project_id}")

    deps = SimpleNamespace(settings=SimpleNamespace(model="deepseek-chat"), ip_memory_repo=ExplodingRepo())

    with pytest.raises(HTTPException) as exc_info:
        stage_generation.run_stage_deepagent(deps, "missing.md", "bad_stage", {})

    assert exc_info.value.status_code == 400


def test_run_stage_deepagent_passes_rendered_ip_memory_to_coordinator(tmp_path, monkeypatch):
    story_file = tmp_path / "output" / "rain" / "小说正文.md"
    story_file.parent.mkdir(parents=True)
    story_file.write_text(
        "# 雨夜重生\n> 题材：悬疑\n\n林晚发现录音证据。\n\n# 发布方案\n短剧发布。",
        encoding="utf-8",
    )
    monkeypatch.setattr("zhihu_fiction.app.services.story_library.APP_ROOT", tmp_path)

    repo = IPMemoryRepository(tmp_path / "ip_memory")
    repo.save(make_memory(project_id=str(story_file)))
    captured: dict[str, str] = {}

    def compat_attr(name, default=None):
        replacements = {
            "create_llm": lambda settings, temperature=0.4: "llm",
            "create_drama_video_coordinator": lambda llm, stage: "coordinator",
            "run_drama_video_coordinator": fake_run_drama_video_coordinator,
        }
        return replacements.get(name, default)

    def fake_run_drama_video_coordinator(coordinator, **kwargs):
        captured["memory_context"] = kwargs.get("memory_context", "")
        return {"content": "阶段草稿", "events": []}

    deps = SimpleNamespace(settings=SimpleNamespace(model="deepseek-chat"), ip_memory_repo=repo)

    stage_generation.run_stage_deepagent(
        deps,
        str(story_file.relative_to(tmp_path)),
        "storyboard",
        {},
        compat_attr=compat_attr,
    )

    assert "【IP记忆】" in captured["memory_context"]
    assert "林晚" in captured["memory_context"]


def test_run_drama_video_coordinator_includes_memory_context_in_prompt():
    captured: dict[str, str] = {}

    class FakeCoordinator:
        def invoke(self, input_msg):
            captured["prompt"] = input_msg["messages"][0]["content"]
            return {"messages": [{"type": "ai", "content": "【阶段草稿】\n分镜草稿"}]}

    result = WorkflowResult(
        topic="雨夜重生",
        genre="悬疑",
        topic_analysis="",
        outline="",
        draft="",
        polished="林晚发现录音证据。",
        review="",
        synthesis="发布方案",
    )

    output = run_drama_video_coordinator(
        FakeCoordinator(),
        result=result,
        stage="storyboard",
        stage_drafts={},
        memory_context="【IP记忆】\n- 林晚：女主",
    )

    assert output["content"] == "分镜草稿"
    assert "统一IP记忆" in captured["prompt"]
    assert "林晚" in captured["prompt"]

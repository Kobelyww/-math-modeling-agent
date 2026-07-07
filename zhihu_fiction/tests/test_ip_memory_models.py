from pathlib import Path

from zhihu_fiction.ip_memory.models import (
    CharacterCard,
    IPMemory,
    MemorySource,
    StoryBible,
    WorldFact,
)
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.ip_memory.rendering import render_memory_context


def test_ip_memory_round_trips_with_source_metadata(tmp_path: Path):
    memory = IPMemory(
        project_id="story-001",
        story_bible=StoryBible(
            title="雨夜重生",
            premise="女主在雨夜重生并反击家族阴谋",
            genre="复仇爽文",
            core_hook="三年前被抛弃的人带着证据归来",
            source=MemorySource(kind="story", ref="小说正文.md", excerpt="雨夜"),
        ),
        characters=[
            CharacterCard(
                id="char_heroine",
                name="林晚",
                role="女主",
                visual_identity="黑色长发，冷静克制",
                motivation="查清父亲死亡真相",
                source=MemorySource(kind="story", ref="小说正文.md", excerpt="林晚"),
            )
        ],
        world_facts=[
            WorldFact(
                id="fact_city",
                text="故事发生在现代运城",
                category="setting",
                source=MemorySource(kind="story", ref="小说正文.md", excerpt="运城"),
            )
        ],
    )

    payload = memory.to_dict()
    restored = IPMemory.from_dict(payload)

    assert restored.project_id == "story-001"
    assert restored.story_bible.title == "雨夜重生"
    assert restored.characters[0].source.ref == "小说正文.md"
    assert restored.world_facts[0].text == "故事发生在现代运城"


def test_repository_saves_memory_and_version_patch(tmp_path: Path):
    repo = IPMemoryRepository(tmp_path)
    memory = IPMemory(project_id="project-a", story_bible=StoryBible(title="A"))

    repo.save(memory, patch_note="initial extraction")
    restored = repo.load("project-a")

    assert restored is not None
    assert restored.story_bible.title == "A"
    assert (tmp_path / "project-a" / "memory.json").exists()
    assert list((tmp_path / "project-a" / "versions").glob("*.json"))


def test_render_memory_context_is_compact_and_sectioned():
    memory = IPMemory(
        project_id="project-a",
        story_bible=StoryBible(title="A", premise="B"),
        characters=[CharacterCard(id="c1", name="林晚", role="女主")],
        world_facts=[WorldFact(id="f1", text="现代运城", category="setting")],
    )

    rendered = render_memory_context(memory, max_chars=500)

    assert "【IP记忆】" in rendered
    assert "【故事圣经】" in rendered
    assert "林晚" in rendered
    assert "现代运城" in rendered

from pathlib import Path

import pytest

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
    assert repo.memory_path("project-a").exists()
    assert list((repo.project_dir("project-a") / "versions").glob("*.json"))


def test_repository_keeps_distinct_non_ascii_project_ids(tmp_path: Path):
    repo = IPMemoryRepository(tmp_path)
    first = IPMemory(project_id="雨夜重生", story_bible=StoryBible(title="A"))
    second = IPMemory(project_id="家族阴谋", story_bible=StoryBible(title="B"))

    repo.save(first)
    repo.save(second)

    assert repo.project_dir(first.project_id) != repo.project_dir(second.project_id)
    assert repo.load(first.project_id).story_bible.title == "A"
    assert repo.load(second.project_id).story_bible.title == "B"


def test_repository_keeps_unsafe_ids_inside_root_and_distinct(tmp_path: Path):
    repo = IPMemoryRepository(tmp_path)
    first_id = "../secret"
    second_id = "..?secret"

    repo.save(IPMemory(project_id=first_id, story_bible=StoryBible(title="A")))
    repo.save(IPMemory(project_id=second_id, story_bible=StoryBible(title="B")))

    first_dir = repo.project_dir(first_id).resolve()
    second_dir = repo.project_dir(second_id).resolve()

    assert first_dir.parent == tmp_path.resolve()
    assert second_dir.parent == tmp_path.resolve()
    assert first_dir != second_dir
    assert repo.load(first_id).story_bible.title == "A"
    assert repo.load(second_id).story_bible.title == "B"


def test_repository_avoids_generated_name_collisions(tmp_path: Path):
    repo = IPMemoryRepository(tmp_path)
    unsafe_id = "a/b"
    generated_name = repo.project_dir(unsafe_id).name

    repo.save(IPMemory(project_id=unsafe_id, story_bible=StoryBible(title="A")))
    repo.save(IPMemory(project_id=generated_name, story_bible=StoryBible(title="B")))

    assert repo.project_dir(unsafe_id) != repo.project_dir(generated_name)
    assert repo.load(unsafe_id).story_bible.title == "A"
    assert repo.load(generated_name).story_bible.title == "B"


@pytest.mark.parametrize(
    "field_name",
    ["characters", "world_facts", "foreshadowing", "asset_bindings"],
)
def test_repository_rejects_malformed_patch_list_fields(
    tmp_path: Path,
    field_name: str,
):
    repo = IPMemoryRepository(tmp_path)

    with pytest.raises(ValueError, match=f"{field_name} must be a list of objects"):
        repo.apply_patch("project-a", {field_name: "bad"})

    with pytest.raises(ValueError, match=rf"{field_name}\[0\] must be an object"):
        repo.apply_patch("project-a", {field_name: ["bad"]})


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

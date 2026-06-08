"""Tests for workspace file repositories."""
from __future__ import annotations

import json

from zhihu_fiction.workspace.models import Material, ReviewDraft, StoryTask, TopicCard
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_save_and_list_materials(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    material = Material(id="mat_1", source="manual", title="标题")

    repo.save_material(material)

    assert repo.list_materials() == [material]
    assert repo.get_material("mat_1") == material


def test_update_material_replaces_record(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_material(Material(id="mat_1", source="manual", title="旧标题"))

    updated = repo.update_material("mat_1", {"title": "新标题", "status": "selected"})

    assert updated.title == "新标题"
    assert updated.status == "selected"
    assert repo.list_materials()[0].title == "新标题"


def test_corrupted_jsonl_line_is_skipped(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_material(Material(id="mat_1", source="manual", title="标题"))
    with (tmp_path / "materials.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{bad json\n")

    assert repo.list_materials() == [Material(id="mat_1", source="manual", title="标题")]


def test_topic_card_and_task_round_trip(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    card = TopicCard(id="card_1", title="选题", source_material_ids=["mat_1"])
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="选题",
        genre="悬疑",
        created_at="2026-06-08T12:00:00",
    )

    repo.save_topic_card(card)
    repo.save_task(task)

    assert repo.get_topic_card("card_1") == card
    assert repo.get_task("task_1") == task


def test_save_and_load_review_draft(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    draft = ReviewDraft(
        id="draft_1",
        task_id="task_1",
        story_path="output/story.md",
        original_body="原文",
        title="标题",
    )

    repo.save_review_draft(draft)

    assert repo.get_review_draft("task_1") == draft
    stored = json.loads((tmp_path / "drafts" / "task_1.json").read_text(encoding="utf-8"))
    assert stored["original_body"] == "原文"


def test_list_queued_tasks_sorts_by_priority_then_created_at(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_task(StoryTask(
        id="task_low",
        topic_card_id="card_1",
        topic="低优先",
        genre="悬疑",
        priority=0,
        created_at="2026-06-08T12:00:01",
    ))
    repo.save_task(StoryTask(
        id="task_high",
        topic_card_id="card_2",
        topic="高优先",
        genre="悬疑",
        priority=10,
        created_at="2026-06-08T12:00:02",
    ))

    queued = repo.list_queued_tasks()

    assert [task.id for task in queued] == ["task_high", "task_low"]

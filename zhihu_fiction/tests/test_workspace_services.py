"""Tests for workspace business services."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zhihu_fiction.workspace.models import StoryTask
from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.services import WorkspaceService


def test_import_scraped_items_creates_materials(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)

    result = service.import_scraped_items(
        [
            {
                "title": "热榜素材",
                "excerpt": "摘要",
                "content": "正文",
                "url": "https://example.com/a",
                "votes": "12",
                "tags": ["热榜"],
            },
            {"content": "缺标题"},
        ],
        source="zhihu",
    )

    assert result["imported"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["reason"] == "missing title"
    assert repo.list_materials()[0].title == "热榜素材"


def test_create_topic_card_marks_materials_selected(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    material = service.create_manual_material("人工素材", content="正文")

    card = service.create_topic_card("复仇选题", source_material_ids=[material.id])

    assert card.source_material_ids == [material.id]
    assert repo.get_material(material.id).status == "selected"


def test_approve_card_and_create_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    card = service.create_topic_card("悬疑选题", genre="悬疑", platform="zhihu")

    approved = service.approve_topic_card(card.id)
    task = service.create_task_from_topic_card(
        card.id,
        chapters=3,
        mode="full",
        priority=5,
    )

    assert approved.status == "approved"
    assert task.status == "queued"
    assert task.topic == "悬疑选题"
    assert task.chapters == 3
    assert task.mode == "full"
    assert task.priority == 5


def test_create_task_requires_approved_card(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    card = service.create_topic_card("草稿选题")

    with pytest.raises(ValueError, match="must be approved"):
        service.create_task_from_topic_card(card.id)


def test_create_review_draft_from_completed_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="成稿标题",
        genre="悬疑",
        status="needs_review",
    )
    repo.save_task(task)
    body = "正文内容"

    draft = service.create_review_draft_from_result(
        task,
        Path("output/story.md"),
        body,
        {"score": 8},
    )

    assert draft.task_id == task.id
    assert draft.title == "成稿标题"
    assert draft.original_body == body


def test_update_draft_and_mark_ready_updates_task(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="旧标题",
        genre="悬疑",
        status="needs_review",
    )
    repo.save_task(task)
    service.create_review_draft_from_result(task, Path("story.md"), "正文", {})

    draft = service.update_review_draft(
        task.id,
        {"title": "新标题", "tags": ["悬疑", "反转"]},
    )
    ready = service.mark_draft_ready(task.id)

    assert draft.title == "新标题"
    assert draft.tags == ["悬疑", "反转"]
    assert ready.status == "ready_for_package"
    assert repo.get_task(task.id).status == "approved"


def test_generate_publish_package_uses_exporter(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    service = WorkspaceService(repo)
    task = StoryTask(
        id="task_1",
        topic_card_id="card_1",
        topic="选题",
        genre="悬疑",
        status="approved",
    )
    repo.save_task(task)
    service.create_review_draft_from_result(task, Path("story.md"), "正文", {})
    service.mark_draft_ready(task.id)
    exporter = MagicMock()
    exporter.export.return_value = {"zhihu": tmp_path / "zhihu_pkg"}

    package = service.generate_publish_package(task.id, "zhihu", exporter)

    assert package.platform == "zhihu"
    assert package.status == "generated"
    assert package.package_dir == str(tmp_path / "zhihu_pkg")
    assert service.repo.get_publish_package(package.id) == package
    exporter.export.assert_called_once()

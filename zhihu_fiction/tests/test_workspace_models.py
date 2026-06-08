"""Tests for workspace domain models."""
import pytest

from zhihu_fiction.workspace.models import (
    MATERIAL_STATUSES,
    PACKAGE_STATUSES,
    TASK_STATUSES,
    Material,
    PublishPackage,
    ReviewDraft,
    StoryTask,
    TopicCard,
    new_id,
)


def test_new_id_uses_prefix_and_random_suffix():
    value = new_id("mat")

    assert value.startswith("mat_")
    assert len(value) > len("mat_")


def test_material_round_trips_and_selected_status_is_valid():
    material = Material(
        id="mat_1",
        source="zhihu",
        title="热榜话题",
        excerpt="摘要",
        content="正文",
        url="https://example.com/topic",
        hot_score=9.5,
        tags=["hot", "fiction"],
        status="selected",
    )

    restored = Material.from_dict(material.to_dict())

    assert restored == material
    assert restored.status in MATERIAL_STATUSES


def test_topic_card_defaults_to_draft_and_preserves_source_material_ids():
    topic = TopicCard(
        id="topic_1",
        title="悬疑选题",
        source_material_ids=["mat_1", "mat_2"],
    )

    restored = TopicCard.from_dict(topic.to_dict())

    assert restored.status == "draft"
    assert restored.source_material_ids == ["mat_1", "mat_2"]


def test_story_task_rejects_invalid_status():
    with pytest.raises(ValueError, match="Invalid StoryTask.status"):
        StoryTask(
            id="task_1",
            topic_card_id="topic_1",
            topic="悬疑选题",
            genre="悬疑",
            status="done",
        )


def test_story_task_defaults_are_valid():
    task = StoryTask(
        id="task_1",
        topic_card_id="topic_1",
        topic="悬疑选题",
        genre="悬疑",
    )

    assert task.status == "queued"
    assert task.retry_count == 0
    assert task.status in TASK_STATUSES


def test_review_draft_round_trips_and_preserves_original_body_separately():
    draft = ReviewDraft(
        id="draft_1",
        task_id="task_1",
        story_path="output/story.md",
        original_body="初稿正文",
        title="标题",
        body="编辑后正文",
        tags=["悬疑"],
        review_result={"score": 8},
    )

    restored = ReviewDraft.from_dict(draft.to_dict())

    assert restored == draft
    assert restored.original_body == "初稿正文"
    assert restored.body == "编辑后正文"


def test_review_draft_from_dict_preserves_persisted_empty_body():
    data = {
        "id": "draft_1",
        "task_id": "task_1",
        "story_path": "output/story.md",
        "original_body": "初稿正文",
        "title": "标题",
        "body": "",
    }

    loaded = ReviewDraft.from_dict(data)

    assert loaded.body == ""


def test_publish_package_defaults_to_generated_and_status_is_valid():
    package = PublishPackage(
        id="pkg_1",
        task_id="task_1",
        platform="zhihu",
        title="标题",
        synopsis="简介",
        tags=["悬疑"],
        content_path="package/content.md",
        metadata_path="package/metadata.json",
        package_dir="package",
    )

    assert package.status == "generated"
    assert package.status in PACKAGE_STATUSES

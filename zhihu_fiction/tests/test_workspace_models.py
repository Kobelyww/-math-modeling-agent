"""Tests for workspace domain models."""
import pytest

from zhihu_fiction.workspace.models import (
    DramaProjectSession,
    DramaStageVersion,
    DramaVideoRun,
    MATERIAL_STATUSES,
    PACKAGE_STATUSES,
    PROJECT_STATUSES,
    REVIEW_STATUSES,
    TASK_STATUSES,
    Material,
    Project,
    PublishPackage,
    Review,
    ReviewDraft,
    StoryTask,
    Story,
    TopicCard,
    VideoAsset,
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


def test_project_story_asset_and_review_round_trip():
    project = Project(
        id="project_1",
        title="山西异味事件短剧",
        source="zhihu",
        description="现实悬疑 IP",
        tags=["现实", "悬疑"],
        status="active",
    )
    story = Story(
        id="story_1",
        project_id=project.id,
        title="第一版小说",
        body_path="output/story.md",
        version=2,
        task_id="task_1",
    )
    asset = VideoAsset(
        id="asset_1",
        project_id=project.id,
        run_id="video_1",
        kind="video",
        uri="minio://zhihu-fiction/video.mp4",
        content_type="video/mp4",
        provider="bailian",
        shot_id="shot_1",
    )
    review = Review(
        id="review_1",
        project_id=project.id,
        target_kind="story",
        target_id=story.id,
        reviewer="human",
        decision="approved",
        comment="可以进入短剧改编",
    )

    assert Project.from_dict(project.to_dict()) == project
    assert Story.from_dict(story.to_dict()) == story
    assert VideoAsset.from_dict(asset.to_dict()) == asset
    assert Review.from_dict(review.to_dict()) == review
    assert project.status in PROJECT_STATUSES
    assert review.decision in REVIEW_STATUSES


def test_review_accepts_drama_project_package_target():
    review = Review(
        id="review_package_1",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id="package_1",
        decision="pending",
    )

    assert Review.from_dict(review.to_dict()) == review


def test_drama_video_run_preserves_project_id():
    run = DramaVideoRun(
        id="video_1",
        story_path="故事/小说正文.md",
        project_id="project_1",
    )

    restored = DramaVideoRun.from_dict(run.to_dict())

    assert restored.project_id == "project_1"


def test_drama_session_and_stage_version_preserve_project_id():
    session = DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="故事/小说正文.md",
    )
    version = DramaStageVersion(
        id="version_1",
        run_id=session.id,
        project_id="project_1",
        stage="script",
        content="剧本草稿",
        event="draft",
    )

    assert DramaProjectSession.from_dict(session.to_dict()).project_id == "project_1"
    assert DramaStageVersion.from_dict(version.to_dict()).project_id == "project_1"

"""Tests for workspace file repositories."""
from __future__ import annotations

import json

from zhihu_fiction.workspace.models import (
    ConsistencyProfile,
    CostLedgerEntry,
    DramaProjectPackage,
    DramaProjectSession,
    DramaStageVersion,
    DramaVideoRun,
    Material,
    OperationLog,
    Project,
    ProjectRelease,
    Review,
    ReviewDraft,
    Story,
    StoryTask,
    TopicCard,
    VideoAsset,
)
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
        id="task_z",
        topic_card_id="card_1",
        topic="同优先级较晚",
        genre="悬疑",
        priority=5,
        created_at="2026-06-08T12:00:02",
    ))
    repo.save_task(StoryTask(
        id="task_a",
        topic_card_id="card_2",
        topic="同优先级较早A",
        genre="悬疑",
        priority=5,
        created_at="2026-06-08T12:00:01",
    ))
    repo.save_task(StoryTask(
        id="task_b",
        topic_card_id="card_3",
        topic="同优先级较早B",
        genre="悬疑",
        priority=5,
        created_at="2026-06-08T12:00:01",
    ))
    repo.save_task(StoryTask(
        id="task_high",
        topic_card_id="card_4",
        topic="高优先",
        genre="悬疑",
        priority=10,
        created_at="2026-06-08T12:00:03",
    ))

    queued = repo.list_queued_tasks()

    assert [task.id for task in queued] == ["task_high", "task_a", "task_b", "task_z"]


def test_project_workspace_records_round_trip_and_filter_by_project(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    project = repo.save_project(Project(
        id="project_1",
        title="山西异味事件短剧",
        updated_at="2026-06-12T10:00:00+00:00",
    ))
    other = repo.save_project(Project(
        id="project_2",
        title="其他项目",
        updated_at="2026-06-12T10:01:00+00:00",
    ))
    story = repo.save_story(Story(
        id="story_1",
        project_id=project.id,
        title="小说第一版",
        body_path="output/story.md",
        version=1,
        created_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_story(Story(
        id="story_2",
        project_id=other.id,
        title="其他小说",
        body_path="output/other.md",
    ))
    asset = repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id=project.id,
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
        created_at="2026-06-12T10:05:00+00:00",
    ))
    review = repo.save_review(Review(
        id="review_1",
        project_id=project.id,
        target_kind="story",
        target_id=story.id,
        decision="approved",
        created_at="2026-06-12T10:10:00+00:00",
    ))

    assert repo.get_project(project.id) == project
    assert repo.list_projects()[0].id == other.id
    assert repo.list_stories(project.id) == [story]
    assert repo.list_video_assets(project.id) == [asset]
    assert repo.list_reviews(project.id) == [review]


def test_project_release_round_trip_with_sqlite_backend(tmp_path):
    repo = WorkspaceRepository(
        tmp_path / "workspace",
        backend="sqlite",
        sqlite_path=tmp_path / "workspace.sqlite3",
    )
    repo.save_project_release(ProjectRelease(
        id="release_old",
        project_id="project_1",
        package_id="package_old",
        run_id="run_old",
        status="confirmed",
        reviewer="human",
        created_at="2026-06-12T09:00:00+00:00",
    ))
    repo.save_project_release(ProjectRelease(
        id="release_new",
        project_id="project_1",
        package_id="package_new",
        run_id="run_new",
        status="confirmed",
        reviewer="operator",
        created_at="2026-06-12T10:00:00+00:00",
        metadata={"source": "test"},
    ))
    repo.save_project_release(ProjectRelease(
        id="release_other",
        project_id="project_other",
        package_id="package_other",
        run_id="run_other",
        status="confirmed",
        created_at="2026-06-12T11:00:00+00:00",
    ))

    project_releases = repo.list_project_releases("project_1")

    assert [release.id for release in project_releases] == ["release_new", "release_old"]
    assert project_releases[0].reviewer == "operator"
    assert project_releases[0].metadata == {"source": "test"}


def test_project_release_lookup_does_not_cross_project_boundary(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_project_release(ProjectRelease(
        id="release_other",
        project_id="project_other",
        package_id="package_shared",
        run_id="run_other",
        status="confirmed",
    ))

    assert repo.get_project_release_for_package("project_1", "package_shared") is None


def test_cost_ledger_round_trip_filters_and_sums_today(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_old",
        project_id="project_1",
        release_id="release_old",
        package_id="package_old",
        run_id="run_old",
        source="project_release_confirm",
        amount_cny=1.25,
        created_at="2026-06-14T23:59:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_new",
        project_id="project_1",
        release_id="release_new",
        package_id="package_new",
        run_id="run_new",
        source="project_release_confirm",
        amount_cny=4.0,
        created_at="2026-06-15T01:00:00+00:00",
        metadata={"shot_count": 5},
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_other",
        project_id="project_other",
        release_id="release_other",
        package_id="package_other",
        run_id="run_other",
        source="project_release_confirm",
        amount_cny=2.0,
        created_at="2026-06-15T02:00:00+00:00",
    ))

    project_entries = repo.list_cost_ledger_entries("project_1")

    assert [entry.id for entry in project_entries] == ["cost_new", "cost_old"]
    assert project_entries[0].currency == "CNY"
    assert project_entries[0].estimated is True
    assert project_entries[0].metadata == {"shot_count": 5}
    assert repo.list_cost_ledger_entries(release_id="release_new") == [project_entries[0]]
    assert repo.sum_cost_ledger_entries_for_day("2026-06-15") == 6.0
    assert repo.sum_cost_ledger_entries_for_day("2026-06-15", project_id="project_1") == 4.0


def test_cost_ledger_day_sum_uses_provider_actual_over_video_estimate(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_1",
        project_id="project_1",
        release_id="video_run_video_1",
        package_id="video_run_video_1",
        run_id="video_1",
        source="video_run_estimate",
        amount_cny=3.0,
        estimated=True,
        created_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_provider_bailian_task_1",
        project_id="project_1",
        release_id="provider_task_1",
        package_id="video_1:shot_1",
        run_id="video_1",
        source="provider_bailian",
        amount_cny=2.5,
        estimated=False,
        created_at="2026-06-15T02:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_2",
        project_id="project_1",
        release_id="video_run_video_2",
        package_id="video_run_video_2",
        run_id="video_2",
        source="video_run_estimate",
        amount_cny=1.0,
        estimated=True,
        created_at="2026-06-15T03:00:00+00:00",
    ))

    assert repo.sum_cost_ledger_entries_for_day("2026-06-15") == 3.5
    assert repo.sum_cost_ledger_entries_for_day("2026-06-15", project_id="project_1") == 3.5
    assert [
        entry.id
        for entry in repo.list_effective_cost_ledger_entries_for_day("2026-06-15")
    ] == [
        "cost_video_run_estimate_video_2",
        "cost_provider_bailian_task_1",
    ]


def test_cost_ledger_lists_covered_video_estimates_for_day(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    estimate = repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_1",
        project_id="project_1",
        release_id="video_run_video_1",
        package_id="video_run_video_1",
        run_id="video_1",
        source="video_run_estimate",
        amount_cny=3.0,
        estimated=True,
        created_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_provider_bailian_task_1",
        project_id="project_1",
        release_id="provider_task_1",
        package_id="video_1:shot_1",
        run_id="video_1",
        source="provider_bailian",
        amount_cny=2.5,
        estimated=False,
        created_at="2026-06-15T02:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_video_2",
        project_id="project_1",
        release_id="video_run_video_2",
        package_id="video_run_video_2",
        run_id="video_2",
        source="video_run_estimate",
        amount_cny=1.0,
        estimated=True,
        created_at="2026-06-15T03:00:00+00:00",
    ))

    covered = repo.list_covered_video_estimate_entries_for_day("2026-06-15")

    assert covered == [estimate]


def test_cost_ledger_coverage_does_not_cross_project_boundary(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    project_a_estimate = repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_video_run_estimate_project_a",
        project_id="project_a",
        release_id="video_run_shared",
        package_id="video_run_shared",
        run_id="shared_run",
        source="video_run_estimate",
        amount_cny=3.0,
        estimated=True,
        created_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_provider_project_b",
        project_id="project_b",
        release_id="provider_task_1",
        package_id="shared_run:shot_1",
        run_id="shared_run",
        source="provider_bailian",
        amount_cny=2.5,
        estimated=False,
        created_at="2026-06-15T02:00:00+00:00",
    ))

    assert repo.list_effective_cost_ledger_entries_for_day("2026-06-15") == [
        repo.get_cost_ledger_entry_for_release("provider_task_1"),
        project_a_estimate,
    ]
    assert repo.list_covered_video_estimate_entries_for_day("2026-06-15") == []


def test_consistency_profiles_round_trip_filter_and_latest_session(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_consistency_profile(ConsistencyProfile(
        id="profile_old",
        project_id="project_1",
        session_id="deepagent_1",
        source_version_ids=["version_old"],
        updated_at="2026-06-15T09:00:00+00:00",
    ))
    repo.save_consistency_profile(ConsistencyProfile(
        id="profile_new",
        project_id="project_1",
        session_id="deepagent_1",
        source_version_ids=["version_new"],
        narrative_constraints=["保留旧版主角动机"],
        updated_at="2026-06-15T10:00:00+00:00",
    ))
    repo.save_consistency_profile(ConsistencyProfile(
        id="profile_other_project",
        project_id="project_2",
        session_id="deepagent_2",
        updated_at="2026-06-15T11:00:00+00:00",
    ))

    project_profiles = repo.list_consistency_profiles("project_1")

    assert [profile.id for profile in project_profiles] == ["profile_new", "profile_old"]
    assert repo.get_consistency_profile("profile_new") == project_profiles[0]
    assert repo.latest_consistency_profile_for_session("deepagent_1") == project_profiles[0]
    assert repo.latest_consistency_profile_for_session("missing") is None


def test_operation_logs_round_trip_filter_and_sort(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_operation_log(OperationLog(
        id="op_old",
        project_id="project_1",
        action="start_session",
        actor="human",
        target_kind="drama_session",
        target_id="deepagent_1",
        created_at="2026-06-15T09:00:00+00:00",
    ))
    repo.save_operation_log(OperationLog(
        id="op_new",
        project_id="project_1",
        action="confirm_stage",
        actor="reviewer",
        target_kind="stage_version",
        target_id="version_1",
        session_id="deepagent_1",
        created_at="2026-06-15T10:00:00+00:00",
        metadata={"stage": "script"},
    ))
    repo.save_operation_log(OperationLog(
        id="op_other_project",
        project_id="project_2",
        action="export_package",
        actor="operator",
        target_kind="asset",
        target_id="package_1",
        created_at="2026-06-15T11:00:00+00:00",
    ))

    project_logs = repo.list_operation_logs("project_1")

    assert [log.id for log in project_logs] == ["op_new", "op_old"]
    assert project_logs[0].actor == "reviewer"
    assert project_logs[0].metadata == {"stage": "script"}


def test_project_timeline_includes_story_asset_and_review_events(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
        created_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
        created_at="2026-06-12T10:05:00+00:00",
    ))
    repo.save_review(Review(
        id="review_1",
        project_id="project_1",
        target_kind="video_asset",
        target_id="asset_1",
        decision="changes_requested",
        created_at="2026-06-12T10:10:00+00:00",
    ))

    timeline = repo.project_timeline("project_1")

    assert [(item["kind"], item["id"]) for item in timeline] == [
        ("review", "review_1"),
        ("video_asset", "asset_1"),
        ("story", "story_1"),
    ]


def test_project_timeline_includes_drama_production_events(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_project(Project(id="project_2", title="其他项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
        created_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        updated_at="2026-06-12T10:01:00+00:00",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="script",
        content="script draft",
        event="draft",
        created_at="2026-06-12T10:02:00+00:00",
    ))
    repo.save_drama_video_run(DramaVideoRun(
        id="video_1",
        project_id="project_1",
        story_path="story.md",
        updated_at="2026-06-12T10:03:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=1,
        created_at="2026-06-12T10:04:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_other",
        project_id="project_2",
        story_path="other.md",
        updated_at="2026-06-12T10:05:00+00:00",
    ))
    repo.save_drama_video_run(DramaVideoRun(
        id="video_story_fallback",
        story_path="story.md",
        updated_at="2026-06-12T10:06:00+00:00",
    ))

    timeline = repo.project_timeline("project_1")

    assert [(item["kind"], item["id"]) for item in timeline] == [
        ("drama_video_run", "video_story_fallback"),
        ("drama_project_package", "package_1"),
        ("drama_video_run", "video_1"),
        ("drama_stage_version", "version_1"),
        ("drama_session", "deepagent_1"),
        ("story", "story_1"),
    ]
    assert all(item["project_id"] == "project_1" for item in timeline)


def test_project_assets_unifies_video_stage_and_package_assets(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
        content_type="video/mp4",
        shot_id="shot_1",
        created_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="storyboard",
        content="分镜 Prompt",
        event="confirmation",
        created_at="2026-06-12T10:01:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=1,
        created_at="2026-06-12T10:02:00+00:00",
    ))

    assets = repo.project_assets("project_1")

    assert [(item["source"], item["id"], item["kind"], item["title"]) for item in assets] == [
        ("drama_project_package", "package_1", "package", "短剧项目包"),
        ("stage_version", "version_1", "prompt", "storyboard / confirmation"),
        ("video_asset", "asset_1", "video", "shot_1"),
    ]
    assert assets[0]["uri"] == "local://package.json"
    assert assets[1]["content_type"] == "text/plain"
    assert assets[2]["content_type"] == "video/mp4"


def test_project_assets_include_latest_review_decision_and_summary(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
        content_type="video/mp4",
        created_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="storyboard",
        content="分镜 Prompt",
        event="confirmation",
        created_at="2026-06-12T10:01:00+00:00",
    ))
    repo.save_review(Review(
        id="review_old",
        project_id="project_1",
        target_kind="video_asset",
        target_id="asset_1",
        decision="pending",
        created_at="2026-06-12T10:02:00+00:00",
    ))
    repo.save_review(Review(
        id="review_new",
        project_id="project_1",
        target_kind="video_asset",
        target_id="asset_1",
        decision="changes_requested",
        created_at="2026-06-12T10:03:00+00:00",
    ))

    assets = repo.project_assets("project_1")
    summary = repo.project_asset_summary("project_1")

    assert assets[0]["review"]["decision"] == "unreviewed"
    assert assets[1]["review"]["decision"] == "changes_requested"
    assert summary == {
        "total": 2,
        "by_kind": {"prompt": 1, "video": 1},
        "by_source": {"stage_version": 1, "video_asset": 1},
        "review": {
            "unreviewed": 1,
            "pending": 0,
            "approved": 0,
            "changes_requested": 1,
            "rejected": 0,
        },
        "awaiting_review": 1,
        "needs_changes": 1,
    }

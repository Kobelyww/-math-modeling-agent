"""Tests for project workspace API routes."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.app.routes.projects import _release_package_for_manifest
from zhihu_fiction.workspace.models import (
    ConsistencyProfile,
    CostLedgerEntry,
    DramaProjectPackage,
    DramaProjectSession,
    DramaStageVersion,
    DramaVideoRun,
    OperationLog,
    Project,
    ProjectRelease,
    Review,
    Story,
    VideoAsset,
)
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_project_api_lists_projects(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(
        id="project_old",
        title="旧项目",
        updated_at="2026-06-12T09:00:00+00:00",
    ))
    repo.save_project(Project(
        id="project_new",
        title="新项目",
        tags=["悬疑"],
        updated_at="2026-06-12T10:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data["projects"]] == ["project_new", "project_old"]
    assert data["projects"][0]["title"] == "新项目"


def test_project_api_returns_workspace_bundle(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="山西异味事件短剧"))
    story = repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说第一版",
        body_path="output/story.md",
    ))
    asset = repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
        created_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="output/story.md",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="character_refs",
        content="人物参考图 Prompt",
        event="confirmation",
        created_at="2026-06-12T10:01:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="output/story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=1,
        created_at="2026-06-12T10:02:00+00:00",
    ))
    review = repo.save_review(Review(
        id="review_1",
        project_id="project_1",
        target_kind="story",
        target_id=story.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    data = response.json()
    assert data["project"]["id"] == "project_1"
    assert data["stories"] == [story.to_dict()]
    assert data["video_assets"] == [asset.to_dict()]
    assert [(item["source"], item["id"], item["kind"]) for item in data["assets"]] == [
        ("drama_project_package", "package_1", "package"),
        ("stage_version", "version_1", "prompt"),
        ("video_asset", "asset_1", "video"),
    ]
    assert data["assets"][2]["review"]["decision"] == "unreviewed"
    assert data["assets_summary"] == {
        "total": 3,
        "by_kind": {"package": 1, "prompt": 1, "video": 1},
        "by_source": {
            "drama_project_package": 1,
            "stage_version": 1,
            "video_asset": 1,
        },
        "review": {
            "unreviewed": 3,
            "pending": 0,
            "approved": 0,
            "changes_requested": 0,
            "rejected": 0,
        },
        "awaiting_review": 3,
        "needs_changes": 0,
    }
    assert data["rework_requests"] == []
    assert data["drama_sessions"] == [
        {
            **repo.get_drama_session("deepagent_1").to_dict(),
            "stage_version_count": 1,
            "confirmed_stage_count": 0,
            "latest_package": {
                **repo.get_drama_project_package("package_1").to_dict(),
                "package_summary": {
                    "available": False,
                    "reason": "package asset key is missing",
                },
            },
            "package_count": 1,
            "can_export_package": False,
        }
    ]
    assert data["reviews"] == [review.to_dict()]


def test_project_api_returns_operation_logs(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    log = repo.save_operation_log(OperationLog(
        id="op_1",
        project_id="project_1",
        action="start_session",
        actor="system",
        target_kind="drama_session",
        target_id="deepagent_1",
        created_at="2026-06-15T10:00:00+00:00",
    ))
    repo.save_operation_log(OperationLog(
        id="op_other",
        project_id="project_2",
        action="start_session",
        actor="system",
        target_kind="drama_session",
        target_id="deepagent_2",
        created_at="2026-06-15T11:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["operation_logs"][0] == log.to_dict()


def test_project_api_returns_consistency_profiles(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_consistency_profile(ConsistencyProfile(
        id="consistency_1",
        project_id="project_1",
        session_id="deepagent_1",
        source_version_ids=["version_1"],
        narrative_constraints=["女主不能提前知道真相"],
        updated_at="2026-06-15T10:00:00+00:00",
    ))
    repo.save_consistency_profile(ConsistencyProfile(
        id="consistency_other",
        project_id="project_2",
        session_id="deepagent_2",
        updated_at="2026-06-15T11:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    data = response.json()
    assert data["consistency_profiles"][0]["id"] == "consistency_1"
    assert data["latest_consistency_profile"]["narrative_constraints"] == [
        "女主不能提前知道真相"
    ]


def test_project_workspace_payload_includes_next_action_and_stage_summary(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    project = repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id=project.id,
        story_path="story.md",
        status="awaiting_confirmation",
        pending_stage="script",
        updated_at="2026-06-15T01:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_action"] == {
        "kind": "confirm_stage",
        "label": "确认 script 阶段",
        "target_id": "deepagent_1",
        "stage": "script",
    }
    assert payload["stage_summary"]["pending_stage"] == "script"
    assert payload["stage_summary"]["status"] == "awaiting_confirmation"
    assert payload["stage_summary"]["session_id"] == "deepagent_1"


def test_project_api_returns_export_ready_drama_sessions_for_legacy_story_path(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_legacy",
        project_id="",
        story_path="story.md",
        stage_drafts={
            "script": "剧本",
            "style": "风格",
            "plot": "剧情",
            "character_refs": "人物",
            "storyboard": "分镜",
        },
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_legacy",
        stage="script",
        content="剧本",
        event="confirmation",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    sessions = response.json()["drama_sessions"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == "deepagent_legacy"
    assert sessions[0]["project_id"] == ""
    assert sessions[0]["stage_version_count"] == 1
    assert sessions[0]["confirmed_stage_count"] == 5
    assert sessions[0]["latest_package"] is None
    assert sessions[0]["package_count"] == 0
    assert sessions[0]["can_export_package"] is True


def test_project_api_returns_production_status_summary(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_ready",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
        updated_at="2026-06-12T12:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_waiting",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style"],
        pending_stage="plot",
        status="awaiting_confirmation",
        updated_at="2026-06-12T11:00:00+00:00",
        rework_requests=[{
            "review_id": "review_1",
            "stage": "plot",
            "status": "requested",
            "target_id": "version_1",
        }],
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
        updated_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    production_status = response.json()["production_status"]
    assert production_status["cost_guardrail"]["currency"] == "CNY"
    assert production_status["cost_guardrail"]["configured"] is False
    assert production_status["cost_guardrail"]["within_budget"] is True
    production_status_without_cost = {
        key: value
        for key, value in production_status.items()
        if key != "cost_guardrail"
    }
    assert production_status_without_cost == {
        "story_count": 1,
        "drama_session_count": 3,
        "asset_count": 2,
        "awaiting_review_count": 2,
        "pending_rework_count": 1,
        "export_ready_count": 1,
        "exported_package_count": 1,
        "latest_session_id": "deepagent_ready",
        "recommended_run_id": "deepagent_waiting",
        "next_action": "resolve_rework",
        "next_action_label": "处理返工请求",
        "next_stage": "plot",
        "release_ready": False,
        "release_action": "",
        "release_action_label": "",
        "release_blockers": [
            {"code": "pending_rework", "label": "存在待处理返工", "count": 1},
            {"code": "awaiting_review", "label": "存在待审核资产", "count": 2},
        ],
    }


def test_project_api_production_status_marks_release_ready_after_package_and_reviews(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    status = response.json()["production_status"]
    assert status["release_ready"] is True
    assert status["release_blockers"] == []
    assert status["release_action"] == "ready_to_release"
    assert status["release_action_label"] == "可以发布"
    assert status["next_action"] == "continue_drama"
    assert status["next_action_label"] == "继续短剧生产"
    release_manifest = response.json()["release_manifest"]
    assert release_manifest["cost_guardrail"]["currency"] == "CNY"
    assert release_manifest["cost_guardrail"]["configured"] is False
    release_manifest_without_cost = {
        key: value
        for key, value in release_manifest.items()
        if key != "cost_guardrail"
    }
    assert release_manifest_without_cost == {
        "project": {
            "id": "project_1",
            "title": "项目",
            "source": "zhihu",
        },
        "release_ready": True,
        "release_action": "ready_to_release",
        "release_action_label": "可以发布",
        "release_blockers": [],
        "story_count": 1,
        "asset_summary": response.json()["assets_summary"],
        "recommended_run_id": "deepagent_packaged",
        "latest_session_id": "deepagent_packaged",
        "release_package_run_id": "deepagent_packaged",
        "release_package": response.json()["drama_sessions"][0]["latest_package"],
        "delivery_actions": {
            "download_url": "/api/projects/project_1/release/package/download",
            "confirm_url": "/api/projects/project_1/release/confirm",
            "can_download": False,
            "can_confirm": True,
        },
    }


def test_project_release_manifest_exposes_cost_guardrail_when_budget_allows(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "0.80")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "10")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "2")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    manifest = response.json()["release_manifest"]
    assert manifest["cost_guardrail"] == {
        "currency": "CNY",
        "billable_stage": "video",
        "estimate": {
            "currency": "CNY",
            "shot_count": 5,
            "seconds_per_shot": 6,
            "estimated_seconds": 30,
            "unit_price_cny": 0.8,
            "estimated_total_cny": 4.0,
        },
        "budget": {
            "daily_budget_cny": 10.0,
            "spent_today_cny": 2.0,
            "remaining_today_cny": 8.0,
        },
        "within_budget": True,
        "configured": True,
    }
    assert manifest["release_ready"] is True
    assert manifest["release_blockers"] == []


def test_project_release_confirm_blocks_when_cost_exceeds_remaining_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "3")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "1")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    workspace = client.get("/api/projects/project_1").json()
    response = client.post("/api/projects/project_1/release/confirm")

    assert workspace["release_manifest"]["release_ready"] is False
    assert workspace["release_manifest"]["cost_guardrail"]["within_budget"] is False
    assert workspace["release_manifest"]["release_blockers"] == [
        {"code": "budget_exceeded", "label": "预算不足", "count": 1},
    ]
    assert response.status_code == 409
    assert response.json()["detail"]["release_blockers"] == workspace["release_manifest"]["release_blockers"]


def test_project_release_budget_uses_package_storyboard_shot_count(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "8")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    asset_path = tmp_path / "workspace" / "assets" / "drama-projects" / "deepagent_packaged" / "package.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text(
        json.dumps({
            "run_id": "deepagent_packaged",
            "story_path": "story.md",
            "structured_assets": {
                "storyboard": {
                    "shots": [{"index": index} for index in range(1, 11)],
                },
            },
        }),
        encoding="utf-8",
    )
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_packaged/package.json",
        stage_count=5,
        version_count=5,
        metadata={
            "asset_key": "drama-projects/deepagent_packaged/package.json",
            "asset_backend": "local",
        },
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    manifest = response.json()["release_manifest"]
    assert response.status_code == 200
    assert manifest["cost_guardrail"]["estimate"]["shot_count"] == 10
    assert manifest["cost_guardrail"]["estimate"]["estimated_total_cny"] == 10.0
    assert manifest["cost_guardrail"]["within_budget"] is False
    assert manifest["release_blockers"] == [
        {"code": "budget_exceeded", "label": "预算不足", "count": 1},
    ]


def test_project_release_budget_blocker_preserves_existing_blockers(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "3")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["release_manifest"]["release_blockers"] == [
        {"code": "awaiting_review", "label": "存在待审核资产", "count": 1},
        {"code": "budget_exceeded", "label": "预算不足", "count": 1},
    ]


def test_project_api_production_status_blocks_release_for_rejected_assets(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="rejected",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    status = response.json()["production_status"]
    assert status["release_ready"] is False
    assert status["release_action"] == ""
    assert status["release_blockers"] == [
        {"code": "needs_changes", "label": "存在需修改或已驳回资产", "count": 1},
    ]
    assert response.json()["release_manifest"]["release_ready"] is False
    assert response.json()["release_manifest"]["release_package"]["id"] == "package_1"
    assert response.json()["release_manifest"]["release_blockers"] == status["release_blockers"]


def test_project_release_manifest_uses_latest_project_package_across_sessions(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="run_newer_session",
        project_id="project_1",
        story_path="story.md",
        updated_at="2026-06-12T12:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="run_older_session",
        project_id="project_1",
        story_path="story.md",
        updated_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_old",
        run_id="run_newer_session",
        story_path="story.md",
        package_uri="local://old.json",
        stage_count=5,
        version_count=5,
        created_at="2026-06-12T09:00:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_new",
        run_id="run_older_session",
        story_path="story.md",
        package_uri="local://new.json",
        stage_count=5,
        version_count=5,
        created_at="2026-06-12T13:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["release_manifest"]["latest_session_id"] == "run_newer_session"
    assert response.json()["release_manifest"]["release_package_run_id"] == "run_older_session"
    assert response.json()["release_manifest"]["release_package"]["id"] == "package_new"


def test_project_release_manifest_compares_package_created_at_by_instant(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="run_offset_package",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="run_utc_package",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_offset_earlier",
        run_id="run_offset_package",
        story_path="story.md",
        package_uri="local://offset.json",
        stage_count=5,
        version_count=5,
        created_at="2026-06-12T13:00:00+08:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_utc_later",
        run_id="run_utc_package",
        story_path="story.md",
        package_uri="local://utc.json",
        stage_count=5,
        version_count=5,
        created_at="2026-06-12T06:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["release_manifest"]["release_package_run_id"] == "run_utc_package"
    assert response.json()["release_manifest"]["release_package"]["id"] == "package_utc_later"


def test_project_release_manifest_uses_latest_package_within_run_by_instant(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="run_1",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_offset_earlier",
        run_id="run_1",
        story_path="story.md",
        package_uri="local://offset.json",
        stage_count=5,
        version_count=5,
        created_at="2026-06-12T13:00:00+08:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_utc_later",
        run_id="run_1",
        story_path="story.md",
        package_uri="local://utc.json",
        stage_count=5,
        version_count=5,
        created_at="2026-06-12T06:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["drama_sessions"][0]["latest_package"]["id"] == "package_utc_later"
    assert response.json()["release_manifest"]["release_package"]["id"] == "package_utc_later"


def test_release_manifest_package_selection_ignores_malformed_package_rows():
    package = _release_package_for_manifest([
        {"latest_package": "not-a-package"},
        {"latest_package": {"id": "valid_package", "run_id": "run_1", "created_at": "2026-06-12T10:00:00+00:00"}},
    ])

    assert package == {
        "id": "valid_package",
        "run_id": "run_1",
        "created_at": "2026-06-12T10:00:00+00:00",
    }


def test_release_manifest_package_selection_demotes_missing_blank_and_invalid_created_at():
    package = _release_package_for_manifest([
        {"latest_package": {"id": "missing_created_at", "run_id": "run_missing"}},
        {"latest_package": {"id": "blank_created_at", "run_id": "run_blank", "created_at": ""}},
        {"latest_package": {"id": "invalid_created_at", "run_id": "run_invalid", "created_at": "not-a-date"}},
        {"latest_package": {"id": "valid_package", "run_id": "run_valid", "created_at": "2026-06-12T10:00:00+00:00"}},
    ])

    assert package == {
        "id": "valid_package",
        "run_id": "run_valid",
        "created_at": "2026-06-12T10:00:00+00:00",
    }


def test_project_api_drama_sessions_use_latest_package_and_filter_other_projects(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_story(Story(
        id="story_2",
        project_id="project_other",
        title="其它小说",
        body_path="other.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        updated_at="2026-06-12T10:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_other_project",
        project_id="project_other",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        updated_at="2026-06-12T11:00:00+00:00",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_other_story",
        project_id="",
        story_path="other.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        updated_at="2026-06-12T12:00:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_old",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://old-package.json",
        stage_count=5,
        version_count=1,
        created_at="2026-06-12T10:05:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_new",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://new-package.json",
        stage_count=5,
        version_count=2,
        created_at="2026-06-12T10:10:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    sessions = response.json()["drama_sessions"]
    assert [session["id"] for session in sessions] == ["deepagent_1"]
    assert sessions[0]["package_count"] == 2
    assert sessions[0]["latest_package"]["id"] == "package_new"
    assert sessions[0]["latest_package"]["package_uri"] == "local://new-package.json"
    assert sessions[0]["can_export_package"] is False


def test_project_api_drama_session_latest_package_includes_readable_summary(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
    ))
    asset_path = tmp_path / "workspace" / "assets" / "drama-projects" / "deepagent_1" / "package.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text(
        """
        {
          "run_id": "deepagent_1",
          "story_path": "story.md",
          "shot_limit": 3,
          "status": "video_started",
          "stage_drafts": {"script": "剧本", "style": "风格"},
          "structured_assets": {"script": {"summary": "剧本摘要"}},
          "confirmed_stages": ["script", "style"],
          "video_run_id": "video_run_1",
          "versions": [{"id": "version_1"}, {"id": "version_2"}],
          "exported_at": "2026-06-12T10:10:00+00:00"
        }
        """,
        encoding="utf-8",
    )
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=2,
        version_count=2,
        video_run_id="video_run_1",
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    package = response.json()["drama_sessions"][0]["latest_package"]
    assert package["package_summary"] == {
        "available": True,
        "run_id": "deepagent_1",
        "story_path": "story.md",
        "shot_count": 0,
        "shot_limit": 3,
        "status": "video_started",
        "stage_count": 2,
        "structured_asset_count": 1,
        "confirmed_stage_count": 2,
        "version_count": 2,
        "video_run_id": "video_run_1",
        "exported_at": "2026-06-12T10:10:00+00:00",
    }


def test_project_api_drama_session_package_summary_degrades_for_unreadable_assets(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="minio://zhihu-fiction/drama-projects/deepagent_1/package.json",
        stage_count=0,
        version_count=0,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "minio"},
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    summary = response.json()["drama_sessions"][0]["latest_package"]["package_summary"]
    assert summary["available"] is False
    assert summary["reason"] == "package asset is not local"


def test_project_release_manifest_exposes_package_delivery_actions(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    manifest = response.json()["release_manifest"]
    assert manifest["delivery_actions"] == {
        "download_url": "/api/projects/project_1/release/package/download",
        "confirm_url": "/api/projects/project_1/release/confirm",
        "can_download": False,
        "can_confirm": True,
    }


def test_project_release_package_download_returns_latest_local_package_payload(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    asset_path = tmp_path / "workspace" / "assets" / "drama-projects" / "deepagent_1" / "package.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text('{"run_id":"deepagent_1","payload":"发布包"}', encoding="utf-8")
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/package/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment;" in response.headers["content-disposition"]
    assert response.json() == {"run_id": "deepagent_1", "payload": "发布包"}


def test_project_release_manifest_marks_downloadable_when_local_package_is_readable(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    asset_path = tmp_path / "workspace" / "assets" / "drama-projects" / "deepagent_1" / "package.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text('{"run_id":"deepagent_1"}', encoding="utf-8")
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["release_manifest"]["delivery_actions"]["can_download"] is True


def test_project_release_confirm_marks_latest_package_confirmed(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post("/api/projects/project_1/release/confirm")

    assert response.status_code == 200
    data = response.json()
    assert data["release_confirmation"]["release_id"].startswith("release_")
    assert data["release_confirmation"] == {
        "project_id": "project_1",
        "package_id": package.id,
        "run_id": "deepagent_1",
        "status": "confirmed",
        "release_id": data["release_confirmation"]["release_id"],
    }
    assert data["release_history"][0]["project_id"] == "project_1"
    assert data["release_history"][0]["package_id"] == package.id
    assert data["release_history"][0]["run_id"] == "deepagent_1"
    assert data["release_history"][0]["status"] == "confirmed"
    assert data["release_history"][0]["reviewer"] == "human"
    assert data["release_history"][0]["metadata"] == {
        "source": "project_release_confirm",
        "manifest_snapshot": data["release_manifest"],
        "package_snapshot": data["release_manifest"]["release_package"],
        "review_summary": data["assets_summary"]["review"],
    }
    assert data["release_manifest"]["release_package"]["status"] == "confirmed"
    assert repo.get_drama_project_package(package.id).status == "confirmed"
    assert repo.list_project_releases("project_1")[0].package_id == package.id


def test_project_release_audit_detail_returns_snapshot_for_project_release(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))
    confirmed = client.post("/api/projects/project_1/release/confirm").json()

    response = client.get(
        "/api/projects/project_1/release/history/"
        + confirmed["release_confirmation"]["release_id"]
    )

    assert response.status_code == 200
    data = response.json()
    assert data["release"]["id"] == confirmed["release_confirmation"]["release_id"]
    assert data["release"]["project_id"] == "project_1"
    assert data["package"]["id"] == package.id
    assert data["manifest_snapshot"]["project"]["id"] == "project_1"
    assert data["manifest_snapshot"]["release_package"]["id"] == package.id
    assert data["review_summary"] == confirmed["assets_summary"]["review"]


def test_project_release_audit_detail_reports_integrity_for_readable_package(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    asset_path = tmp_path / "workspace" / "assets" / "drama-projects" / "deepagent_1" / "package.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text(
        (
            '{"run_id":"deepagent_1","story_path":"story.md","shot_limit":3,'
            '"stage_drafts":{"script":"剧本","style":"风格","plot":"剧情","character_refs":"人物","storyboard":"分镜"},'
            '"confirmed_stages":["script","style","plot","character_refs","storyboard"],'
            '"versions":[1,2,3,4,5]}'
        ),
        encoding="utf-8",
    )
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_project_release(ProjectRelease(
        id="release_1",
        project_id="project_1",
        package_id=package.id,
        run_id="deepagent_1",
        metadata={
            "manifest_snapshot": {"release_package": {"id": package.id, "run_id": "deepagent_1"}},
            "package_snapshot": {"id": package.id, "run_id": "deepagent_1", "stage_count": 5},
            "review_summary": {"approved": 1},
        },
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_1")

    assert response.status_code == 200
    integrity = response.json()["integrity"]
    assert integrity["status"] == "passed"
    assert integrity["summary"] == {"passed": 5, "failed": 0, "warning": 0}
    assert [(check["code"], check["status"]) for check in integrity["checks"]] == [
        ("package_record", "passed"),
        ("package_asset", "passed"),
        ("package_snapshot", "passed"),
        ("run_consistency", "passed"),
        ("stage_coverage", "passed"),
    ]


def test_project_release_audit_detail_reports_integrity_failure_for_missing_asset(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_project_release(ProjectRelease(
        id="release_1",
        project_id="project_1",
        package_id=package.id,
        run_id="deepagent_1",
        metadata={
            "package_snapshot": {"id": package.id, "run_id": "deepagent_1"},
            "review_summary": {"approved": 1},
        },
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_1")

    assert response.status_code == 200
    integrity = response.json()["integrity"]
    assert integrity["status"] == "failed"
    assert integrity["summary"]["failed"] == 1
    asset_check = next(check for check in integrity["checks"] if check["code"] == "package_asset")
    assert asset_check["status"] == "failed"
    assert asset_check["label"] == "项目包文件"
    assert asset_check["message"] == "package asset not found"


def test_project_release_audit_detail_reports_snapshot_mismatch(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    asset_path = tmp_path / "workspace" / "assets" / "drama-projects" / "deepagent_1" / "package.json"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text('{"run_id":"deepagent_1"}', encoding="utf-8")
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_project_release(ProjectRelease(
        id="release_1",
        project_id="project_1",
        package_id=package.id,
        run_id="deepagent_1",
        metadata={
            "package_snapshot": {
                "id": package.id,
                "run_id": "deepagent_old",
                "stage_count": 3,
                "version_count": 4,
            },
        },
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_1")

    assert response.status_code == 200
    snapshot_check = next(
        check for check in response.json()["integrity"]["checks"]
        if check["code"] == "package_snapshot"
    )
    assert snapshot_check["status"] == "failed"
    assert snapshot_check["message"] == "snapshot package mismatch"


def test_project_release_audit_detail_handles_legacy_non_dict_package_metadata(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata=["legacy"],
    ))
    repo.save_project_release(ProjectRelease(
        id="release_1",
        project_id="project_1",
        package_id=package.id,
        run_id="deepagent_1",
        metadata={"package_snapshot": {"id": package.id, "run_id": "deepagent_1"}},
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_1")

    assert response.status_code == 200
    asset_check = next(
        check for check in response.json()["integrity"]["checks"]
        if check["code"] == "package_asset"
    )
    assert asset_check["status"] == "failed"
    assert asset_check["message"] == "package asset key is missing"


def test_project_release_audit_detail_rejects_other_project_release(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_project_release(ProjectRelease(
        id="release_other",
        project_id="project_other",
        package_id="package_1",
        run_id="run_1",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_other")

    assert response.status_code == 404
    assert response.json()["detail"] == "release not found"


def test_project_release_audit_detail_handles_missing_package_record(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_project_release(ProjectRelease(
        id="release_1",
        project_id="project_1",
        package_id="missing_package",
        run_id="run_1",
        metadata={
            "manifest_snapshot": {"project": {"id": "project_1"}},
            "package_snapshot": {"id": "missing_package"},
            "review_summary": {"approved": 1},
        },
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_1")

    assert response.status_code == 200
    assert response.json()["package"] is None
    assert response.json()["package_snapshot"] == {"id": "missing_package"}
    assert response.json()["review_summary"] == {"approved": 1}


def test_project_release_audit_detail_handles_legacy_non_dict_metadata(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_project_release(ProjectRelease(
        id="release_1",
        project_id="project_1",
        package_id="missing_package",
        run_id="run_1",
        metadata=None,
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/release/history/release_1")

    assert response.status_code == 200
    assert response.json()["package"] is None
    assert response.json()["manifest_snapshot"] == {}
    assert response.json()["package_snapshot"] == {}
    assert response.json()["review_summary"] == {}


def test_project_release_confirm_is_idempotent_for_same_package(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    first = client.post("/api/projects/project_1/release/confirm")
    second = client.post("/api/projects/project_1/release/confirm")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["release_confirmation"]["release_id"] == first.json()["release_confirmation"]["release_id"]
    assert [item["id"] for item in second.json()["release_history"]] == [
        first.json()["release_confirmation"]["release_id"],
    ]
    assert len(repo.list_project_releases("project_1")) == 1


def test_project_release_confirm_records_estimated_cost_ledger_once(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "0.8")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "20")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "1.5")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    first = client.post("/api/projects/project_1/release/confirm")
    second = client.post("/api/projects/project_1/release/confirm")

    assert first.status_code == 200
    assert second.status_code == 200
    release_id = first.json()["release_confirmation"]["release_id"]
    entries = repo.list_cost_ledger_entries(project_id="project_1", release_id=release_id)
    assert len(entries) == 1
    assert entries[0].source == "project_release_confirm"
    assert entries[0].package_id == package.id
    assert entries[0].run_id == "deepagent_1"
    assert entries[0].amount_cny == 4.0
    assert entries[0].currency == "CNY"
    assert entries[0].estimated is True
    assert entries[0].metadata == {
        "billable_stage": "video",
        "estimate": first.json()["release_manifest"]["cost_guardrail"]["estimate"],
    }
    assert len(repo.list_cost_ledger_entries(project_id="project_1")) == 1
    assert second.json()["cost_ledger"] == [entries[0].to_dict()]


def test_project_release_confirm_idempotent_even_after_spend_exhausts_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "5")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    first = client.post("/api/projects/project_1/release/confirm")
    second = client.post("/api/projects/project_1/release/confirm")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["release_confirmation"]["release_id"] == first.json()["release_confirmation"]["release_id"]
    assert len(repo.list_cost_ledger_entries(project_id="project_1")) == 1
    assert second.json()["release_manifest"]["cost_guardrail"]["within_budget"] is False


def test_project_release_confirm_backfills_legacy_release_cost_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "5")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
        status="generated",
    ))
    repo.save_project_release(ProjectRelease(
        id="release_legacy",
        project_id="project_1",
        package_id=package.id,
        run_id="deepagent_1",
        status="confirmed",
        metadata={"source": "legacy"},
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post("/api/projects/project_1/release/confirm")

    assert response.status_code == 200
    assert response.json()["release_confirmation"] == {
        "project_id": "project_1",
        "package_id": package.id,
        "run_id": "deepagent_1",
        "status": "confirmed",
        "release_id": "release_legacy",
    }
    entries = repo.list_cost_ledger_entries(project_id="project_1", release_id="release_legacy")
    assert len(entries) == 1
    assert entries[0].amount_cny == 5.0
    assert repo.get_drama_project_package(package.id).status == "confirmed"


def test_project_release_manifest_spent_today_includes_persisted_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "0.8")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "10")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "1")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_today",
        project_id="project_1",
        release_id="release_existing",
        package_id="package_existing",
        run_id="deepagent_existing",
        source="project_release_confirm",
        amount_cny=4.0,
    ))
    repo.save_cost_ledger_entry(CostLedgerEntry(
        id="cost_other_project",
        project_id="project_other",
        release_id="release_other",
        package_id="package_other",
        run_id="deepagent_other",
        source="project_release_confirm",
        amount_cny=2.0,
    ))
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_packaged",
        project_id="project_1",
        story_path="story.md",
        confirmed_stages=["script", "style", "plot", "character_refs", "storyboard"],
        status="video_started",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_packaged",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=5,
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    guardrail = response.json()["release_manifest"]["cost_guardrail"]
    assert guardrail["budget"] == {
        "daily_budget_cny": 10.0,
        "spent_today_cny": 7.0,
        "remaining_today_cny": 3.0,
    }
    assert guardrail["within_budget"] is False


def test_project_release_audit_detail_includes_cost_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "0.8")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "20")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="approved",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))
    confirmed = client.post("/api/projects/project_1/release/confirm").json()

    response = client.get(
        "/api/projects/project_1/release/history/"
        + confirmed["release_confirmation"]["release_id"]
    )

    assert response.status_code == 200
    assert response.json()["cost_ledger"] == confirmed["cost_ledger"]
    assert response.json()["cost_ledger_summary"] == {
        "currency": "CNY",
        "entry_count": 1,
        "estimated_total_cny": 4.0,
        "actual_total_cny": 0.0,
        "total_cny": 4.0,
    }


def test_project_release_confirm_blocks_when_release_not_ready(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    package = repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://drama-projects/deepagent_1/package.json",
        stage_count=5,
        version_count=5,
        metadata={"asset_key": "drama-projects/deepagent_1/package.json", "asset_backend": "local"},
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
    ))
    repo.save_review(Review(
        id="review_package",
        project_id="project_1",
        target_kind="drama_project_package",
        target_id=package.id,
        decision="rejected",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    workspace = client.get("/api/projects/project_1").json()
    response = client.post("/api/projects/project_1/release/confirm")

    assert workspace["release_manifest"]["delivery_actions"]["can_confirm"] is False
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": "release is blocked",
        "release_blockers": [
            {"code": "needs_changes", "label": "存在需修改或已驳回资产", "count": 1},
        ],
    }
    assert repo.get_drama_project_package(package.id).status == "generated"
    assert repo.list_project_releases("project_1") == []


def test_project_workspace_returns_release_history_sorted_latest_first(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
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
    ))
    repo.save_project_release(ProjectRelease(
        id="release_other",
        project_id="project_other",
        package_id="package_other",
        run_id="run_other",
        status="confirmed",
        created_at="2026-06-12T11:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["release_history"]] == [
        "release_new",
        "release_old",
    ]
    assert response.json()["release_history"][0]["reviewer"] == "operator"


def test_project_api_package_summary_safely_handles_bad_local_assets(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    for run_id, asset_key in (
        ("run_escape", "../escape.json"),
        ("run_missing", "drama-projects/missing/package.json"),
        ("run_bad_json", "drama-projects/bad-json/package.json"),
        ("run_bad_types", "drama-projects/bad-types/package.json"),
    ):
        repo.save_drama_session(DramaProjectSession(
            id=run_id,
            project_id="project_1",
            story_path=f"{run_id}.md",
            updated_at=f"2026-06-12T10:0{len(run_id) % 10}:00+00:00",
        ))
        repo.save_drama_project_package(DramaProjectPackage(
            id=f"package_{run_id}",
            run_id=run_id,
            story_path=f"{run_id}.md",
            package_uri=f"local://{asset_key}",
            stage_count=0,
            version_count=0,
            metadata={"asset_key": asset_key, "asset_backend": "local"},
        ))

    bad_json_path = tmp_path / "workspace" / "assets" / "drama-projects" / "bad-json" / "package.json"
    bad_json_path.parent.mkdir(parents=True)
    bad_json_path.write_text("{not json", encoding="utf-8")
    bad_types_path = tmp_path / "workspace" / "assets" / "drama-projects" / "bad-types" / "package.json"
    bad_types_path.parent.mkdir(parents=True)
    bad_types_path.write_text(
        """
        {
          "run_id": "run_bad_types",
          "story_path": "bad-types.md",
          "shot_limit": "abc",
          "stage_drafts": "not-object",
          "structured_assets": "not-object",
          "confirmed_stages": "not-list",
          "versions": "not-list"
        }
        """,
        encoding="utf-8",
    )
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    summaries = {
        session["id"]: session["latest_package"]["package_summary"]
        for session in response.json()["drama_sessions"]
    }
    assert summaries["run_escape"] == {
        "available": False,
        "reason": "package asset key is invalid",
    }
    assert summaries["run_missing"] == {
        "available": False,
        "reason": "package asset not found",
    }
    assert summaries["run_bad_json"] == {
        "available": False,
        "reason": "package asset is unreadable",
    }
    assert summaries["run_bad_types"]["available"] is True
    assert summaries["run_bad_types"]["shot_limit"] == 0
    assert summaries["run_bad_types"]["stage_count"] == 0
    assert summaries["run_bad_types"]["structured_asset_count"] == 0
    assert summaries["run_bad_types"]["confirmed_stage_count"] == 0
    assert summaries["run_bad_types"]["version_count"] == 0


def test_project_api_creates_asset_review_and_returns_refreshed_workspace(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post(
        "/api/projects/project_1/assets/reviews",
        json={
            "target_kind": "video_asset",
            "target_id": "asset_1",
            "decision": "approved",
            "comment": "可以进入发布包",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["review"]["project_id"] == "project_1"
    assert data["review"]["target_kind"] == "video_asset"
    assert data["review"]["target_id"] == "asset_1"
    assert data["review"]["decision"] == "approved"
    assert data["review"]["comment"] == "可以进入发布包"
    assert data["review"]["metadata"] == {"source": "project_asset_dialog"}
    assert data["assets"][0]["review"]["decision"] == "approved"
    assert data["assets_summary"]["review"]["approved"] == 1
    assert data["assets_summary"]["awaiting_review"] == 0
    assert repo.list_reviews("project_1")[0].decision == "approved"


def test_project_api_preserves_asset_review_metadata_with_dialog_source(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post(
        "/api/projects/project_1/assets/reviews",
        json={
            "target_kind": "video_asset",
            "target_id": "asset_1",
            "decision": "changes_requested",
            "comment": "镜头开场需要更强冲突",
            "metadata": {"agent_instruction": "重写第一镜头"},
        },
    )

    assert response.status_code == 200
    review = response.json()["review"]
    assert review["metadata"] == {
        "agent_instruction": "重写第一镜头",
        "source": "project_asset_dialog",
    }


def test_project_api_creates_rework_request_for_stage_version_changes(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        stage_drafts={"script": "旧剧本"},
        confirmed_stages=["script"],
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="script",
        content="旧剧本",
        event="confirmation",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post(
        "/api/projects/project_1/assets/reviews",
        json={
            "target_kind": "stage_version",
            "target_id": "version_1",
            "decision": "changes_requested",
            "comment": "人物动机不够明确",
            "metadata": {"agent_instruction": "重写主角动机并增强冲突"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["rework_request"] == {
        "review_id": data["review"]["id"],
        "project_id": "project_1",
        "run_id": "deepagent_1",
        "stage": "script",
        "target_kind": "stage_version",
        "target_id": "version_1",
        "instruction": "重写主角动机并增强冲突",
        "comment": "人物动机不够明确",
        "status": "requested",
    }
    session = repo.get_drama_session("deepagent_1")
    assert session.rework_requests == [data["rework_request"]]


def test_project_api_returns_rework_requests_in_workspace_bundle(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        rework_requests=[
            {
                "review_id": "review_1",
                "project_id": "project_1",
                "run_id": "deepagent_1",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_1",
                "instruction": "加强冲突",
                "comment": "冲突不够",
                "status": "requested",
            }
        ],
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["rework_requests"] == [
        {
            "review_id": "review_1",
            "project_id": "project_1",
            "run_id": "deepagent_1",
            "stage": "script",
            "target_kind": "stage_version",
            "target_id": "version_1",
            "instruction": "加强冲突",
            "comment": "冲突不够",
            "status": "requested",
        }
    ]


def test_project_api_returns_completed_rework_version_entry_in_workspace_bundle(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        rework_requests=[
            {
                "review_id": "review_1",
                "project_id": "project_1",
                "run_id": "deepagent_1",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_1",
                "instruction": "加强冲突",
                "comment": "冲突不够",
                "status": "completed",
                "completed_stage_version_id": "version_rework_1",
            }
        ],
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_rework_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="script",
        content="返工后剧本",
        event="revision",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    request = response.json()["rework_requests"][0]
    assert request["status"] == "completed"
    assert request["completed_stage_version_id"] == "version_rework_1"
    assert request["completed_stage_version"]["id"] == "version_rework_1"
    assert request["completed_stage_version"]["event"] == "revision"
    assert request["completed_stage_version"]["content"] == "返工后剧本"


def test_project_api_does_not_attach_completed_rework_version_from_wrong_run_or_stage(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        rework_requests=[
            {
                "review_id": "review_wrong_run",
                "project_id": "project_1",
                "run_id": "other_run",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_1",
                "instruction": "加强冲突",
                "comment": "冲突不够",
                "status": "completed",
                "completed_stage_version_id": "version_wrong_run",
            },
            {
                "review_id": "review_wrong_stage",
                "project_id": "project_1",
                "run_id": "deepagent_1",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_2",
                "instruction": "强化钩子",
                "comment": "钩子弱",
                "status": "completed",
                "completed_stage_version_id": "version_wrong_stage",
            },
            {
                "review_id": "review_missing",
                "project_id": "project_1",
                "run_id": "deepagent_1",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_3",
                "instruction": "补细节",
                "comment": "细节少",
                "status": "completed",
                "completed_stage_version_id": "version_missing",
            },
        ],
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_wrong_run",
        run_id="other_run",
        project_id="project_1",
        stage="script",
        content="其他会话版本",
        event="revision",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_wrong_stage",
        run_id="deepagent_1",
        project_id="project_1",
        stage="style",
        content="错误阶段版本",
        event="revision",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    requests = response.json()["rework_requests"]
    assert requests[0]["run_id"] == "deepagent_1"
    assert [item["completed_stage_version_id"] for item in requests] == [
        "version_wrong_run",
        "version_wrong_stage",
        "version_missing",
    ]
    assert all("completed_stage_version" not in item for item in requests)


def test_project_api_returns_rework_requests_for_legacy_session_owned_by_story_path(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="小说",
        body_path="story.md",
    ))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_legacy",
        project_id="",
        story_path="story.md",
        rework_requests=[
            {
                "review_id": "review_1",
                "run_id": "deepagent_legacy",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_1",
                "instruction": "加强冲突",
                "comment": "冲突不够",
                "status": "requested",
            }
        ],
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["rework_requests"] == [
        {
            "review_id": "review_1",
            "project_id": "project_1",
            "run_id": "deepagent_legacy",
            "stage": "script",
            "target_kind": "stage_version",
            "target_id": "version_1",
            "instruction": "加强冲突",
            "comment": "冲突不够",
            "status": "requested",
        }
    ]


def test_project_workspace_rework_request_is_completed_after_deepagent_revision(monkeypatch, tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        drafts={"script": "旧剧本"},
        rework_requests=[
            {
                "review_id": "review_1",
                "project_id": "project_1",
                "run_id": "deepagent_1",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_1",
                "instruction": "加强冲突",
                "comment": "冲突不够",
                "status": "requested",
            }
        ],
    ))
    from zhihu_fiction.app.services import drama_video_runtime

    monkeypatch.setattr(
        drama_video_runtime,
        "run_video_stage_deepagent",
        lambda deps, story_path, stage, stage_drafts, current_draft="", human_feedback="": {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": f"修订后：{human_feedback}",
            "events": [],
        },
    )
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    revise = client.post(
        "/api/drama-video/deepagent/revise",
        json={
            "run_id": "deepagent_1",
            "stage": "script",
            "feedback": "加强冲突",
        },
    )
    workspace = client.get("/api/projects/project_1")

    assert revise.status_code == 200
    request = workspace.json()["rework_requests"][0]
    assert request["status"] == "completed"
    assert request["completed_stage_version_id"]


def test_project_api_rejects_invalid_asset_review_decision(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post(
        "/api/projects/project_1/assets/reviews",
        json={
            "target_kind": "video_asset",
            "target_id": "asset_1",
            "decision": "done",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid review decision"


def test_project_api_returns_404_when_reviewing_missing_asset(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post(
        "/api/projects/project_1/assets/reviews",
        json={
            "target_kind": "video_asset",
            "target_id": "missing",
            "decision": "approved",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "asset not found"


def test_project_api_rejects_non_object_asset_review_metadata(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="项目"))
    repo.save_video_asset(VideoAsset(
        id="asset_1",
        project_id="project_1",
        run_id="video_1",
        kind="video",
        uri="local://video.mp4",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.post(
        "/api/projects/project_1/assets/reviews",
        json={
            "target_kind": "video_asset",
            "target_id": "asset_1",
            "decision": "approved",
            "metadata": ["not", "object"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "metadata must be an object"


def test_project_api_returns_timeline(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
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
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_1",
        project_id="project_1",
        story_path="story.md",
        updated_at="2026-06-12T10:06:00+00:00",
    ))
    repo.save_drama_stage_version(DramaStageVersion(
        id="version_1",
        run_id="deepagent_1",
        project_id="project_1",
        stage="script",
        content="script draft",
        event="draft",
        created_at="2026-06-12T10:07:00+00:00",
    ))
    repo.save_drama_video_run(DramaVideoRun(
        id="video_run_1",
        project_id="project_1",
        story_path="story.md",
        updated_at="2026-06-12T10:08:00+00:00",
    ))
    repo.save_drama_project_package(DramaProjectPackage(
        id="package_1",
        run_id="deepagent_1",
        story_path="story.md",
        package_uri="local://package.json",
        stage_count=5,
        version_count=1,
        created_at="2026-06-12T10:09:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1/timeline")

    assert response.status_code == 200
    data = response.json()
    assert [(item["kind"], item["id"]) for item in data["timeline"]] == [
        ("drama_project_package", "package_1"),
        ("drama_video_run", "video_run_1"),
        ("drama_stage_version", "version_1"),
        ("drama_session", "deepagent_1"),
        ("video_asset", "asset_1"),
        ("story", "story_1"),
    ]


def test_project_api_returns_404_for_missing_project(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "project not found"

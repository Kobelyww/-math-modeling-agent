"""Tests for short-drama DeepAgent workflow service."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from zhihu_fiction.app.services.drama_video_deepagent_flow import (
    advance_deepagent,
    confirm_stage,
    revise_stage,
    retry_failed_stage,
    start_deepagent_run,
    start_deepagent_video_loop,
)
from zhihu_fiction.app.state import AppState
from zhihu_fiction.ip_memory.models import CharacterCard, IPMemory
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.ip_memory.trace import AgentTraceStore
from zhihu_fiction.workspace.models import DramaProjectSession
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def _deps(repo):
    return SimpleNamespace(workspace_repo=repo)


def _trace_deps(repo, tmp_path):
    return SimpleNamespace(
        workspace_repo=repo,
        ip_memory_repo=IPMemoryRepository(tmp_path / "memory"),
        agent_trace_store=AgentTraceStore(tmp_path / "traces"),
    )


def test_start_deepagent_run_initializes_spec_and_persists_session(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    state = AppState()

    response = start_deepagent_run(
        _deps(repo),
        state,
        story_path="测试主题/小说正文.md",
        project_id="project_1",
        shot_limit=2,
        stage_drafts={"script": "已有剧本"},
        id_factory=lambda prefix: "deepagent_fixed",
    )

    assert response == {
        "run_id": "deepagent_fixed",
        "status": "started",
        "agent": "deepagent",
        "next_stage": "style",
    }
    assert state.video_deepagent_specs["deepagent_fixed"]["confirmed_stages"] == ["script"]
    assert state.video_deepagent_specs["deepagent_fixed"]["project_id"] == "project_1"
    assert repo.get_drama_session("deepagent_fixed").status == "started"
    assert repo.get_drama_session("deepagent_fixed").project_id == "project_1"


def test_start_and_confirm_stage_record_operation_logs(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = _deps(repo)
    state = AppState()

    start_deepagent_run(
        deps,
        state,
        story_path="测试主题/小说正文.md",
        project_id="project_1",
        shot_limit=2,
        stage_drafts={},
        id_factory=lambda prefix: "deepagent_fixed",
    )
    confirm_stage(
        deps,
        state,
        "deepagent_fixed",
        "script",
        "确认剧本",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )

    logs = repo.list_operation_logs("project_1")

    assert [log.action for log in logs] == ["confirm_stage", "start_session"]
    assert logs[0].metadata["stage"] == "script"
    assert logs[0].target_kind == "stage_version"
    assert logs[0].target_id == repo.list_drama_stage_versions("deepagent_fixed")[0].id
    assert logs[1].target_kind == "drama_session"
    assert logs[1].target_id == "deepagent_fixed"
    assert logs[1].metadata == {
        "story_path": "测试主题/小说正文.md",
        "shot_limit": 2,
    }


def test_confirm_stage_updates_consistency_profile(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = _deps(repo)
    state = AppState()

    start_deepagent_run(
        deps,
        state,
        story_path="测试主题/小说正文.md",
        project_id="project_1",
        shot_limit=2,
        stage_drafts={},
        id_factory=lambda prefix: "deepagent_consistency",
    )
    confirm_stage(
        deps,
        state,
        "deepagent_consistency",
        "script",
        "角色：林晚。地点：运城。限制：女主不能提前知道真相。",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )

    profile = repo.latest_consistency_profile_for_session("deepagent_consistency")

    assert profile is not None
    assert profile.project_id == "project_1"
    assert profile.characters == [{"name": "林晚", "source_stage": "script"}]
    assert profile.world_facts == [{"text": "运城", "source_stage": "script"}]
    assert profile.narrative_constraints == ["女主不能提前知道真相"]
    assert profile.source_version_ids == [
        repo.list_drama_stage_versions("deepagent_consistency")[0].id
    ]


def test_confirm_stage_records_agent_trace_and_memory_patch(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = _trace_deps(repo, tmp_path)
    state = AppState()
    deps.ip_memory_repo.save(
        IPMemory(
            project_id="project-a",
            characters=[
                CharacterCard(
                    id="lin-wan",
                    name="林晚",
                    visual_identity="黑色长发",
                )
            ],
        )
    )
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project-a",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {"script": "林晚以黑色长发出场，发现账本线索。"},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
    }

    confirm_stage(
        deps,
        state,
        "run_1",
        "script",
        "",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )

    events = deps.agent_trace_store.list("run_1")
    assert len(events) == 1
    event = events[0].to_dict()
    version = repo.list_drama_stage_versions("run_1")[0]
    assert event["event"] == "human_confirmed"
    assert event["node_id"] == "drama.script"
    assert event["stage"] == "script"
    assert event["memory_snapshot"].startswith("sha256:")
    assert event["memory_snapshot"] != "sha256:empty"
    assert event["human_decision"] == {"decision": "confirm"}
    assert event["metadata"]["version_id"] == version.id
    assert event["review"]["stage"] == "script"
    assert event["review"]["status"] == "ok"


def test_confirm_stage_merges_consistency_profile_without_losing_prior_data(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project_1",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
    }

    confirm_stage(
        deps,
        state,
        "run_1",
        "script",
        "角色：林晚。风格：冷暖对比。",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )
    confirm_stage(
        deps,
        state,
        "run_1",
        "style",
        "视觉：低饱和城市夜景。镜头：手持纪实。",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )
    profile = repo.latest_consistency_profile_for_session("run_1")
    profile.asset_bindings = {"林晚": {"ref_image": "asset_character_linwan"}}
    repo.save_consistency_profile(profile)

    confirm_stage(
        deps,
        state,
        "run_1",
        "plot",
        "剧情：异味线索逐步升级。",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )
    confirm_stage(
        deps,
        state,
        "run_1",
        "character_refs",
        "角色：林晚。人物参考图：白衬衫，疲惫但警觉。",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": "video_unused",
    )

    profile = repo.latest_consistency_profile_for_session("run_1")

    assert profile.visual_style["notes"] == [
        "冷暖对比",
        "低饱和城市夜景",
        "手持纪实",
    ]
    assert profile.asset_bindings["林晚"]["ref_image"] == "asset_character_linwan"
    assert profile.asset_bindings["林晚"]["generated_refs"][0]["source_stage"] == "character_refs"
    assert len(profile.source_version_ids) == 4


def test_deepagent_auto_loop_stops_at_confirmation_checkpoint(monkeypatch, tmp_path):
    story_dir = tmp_path / "故事"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 故事\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = _deps(repo)
    state = AppState()

    result = start_deepagent_video_loop(
        deps,
        state,
        story_path="故事/小说正文.md",
        project_id="project_1",
        shot_limit=2,
        stage_drafts={},
        model_runner=lambda stage, context: f"{stage} draft",
        id_factory=lambda prefix: "deepagent_1",
    )

    session = repo.get_drama_session("deepagent_1")
    assert result["run_id"] == "deepagent_1"
    assert result["status"] == "awaiting_confirmation"
    assert result["pending_stage"] == "script"
    assert result["draft"] == "script draft"
    assert session.pending_stage == "script"
    assert session.project_id == "project_1"
    assert session.drafts["script"] == "script draft"
    assert repo.list_drama_stage_versions("deepagent_1")[0].project_id == "project_1"
    assert state.video_deepagent_specs["deepagent_1"]["drafts"]["script"] == "script draft"


def test_start_deepagent_video_loop_records_draft_agent_trace(monkeypatch, tmp_path):
    story_dir = tmp_path / "故事"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 故事\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = _trace_deps(repo, tmp_path)
    state = AppState()

    start_deepagent_video_loop(
        deps,
        state,
        story_path="故事/小说正文.md",
        project_id="project-a",
        shot_limit=2,
        stage_drafts={},
        model_runner=lambda stage, context: {
            "content": "script draft",
            "events": [{"type": "tool_call", "name": "draft_script"}],
        },
        id_factory=lambda prefix: "deepagent_trace_draft",
    )

    event = deps.agent_trace_store.list("deepagent_trace_draft")[0].to_dict()
    version = repo.list_drama_stage_versions("deepagent_trace_draft")[0]
    assert event["event"] == "draft_created"
    assert event["node_id"] == "drama.script"
    assert event["metadata"]["version_id"] == version.id
    assert event["metadata"]["events"] == [{"type": "tool_call", "name": "draft_script"}]


def test_advance_deepagent_generates_and_caches_next_stage(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {},
        "confirmed_stages": [],
        "pending_stage": None,
        "video_run_id": "",
    }

    response = advance_deepagent(
        deps,
        state,
        "run_1",
        generator=lambda story_path, stage, drafts: {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "content": "script draft",
            "events": [],
        },
    )
    repeated = advance_deepagent(deps, state, "run_1")

    assert response["status"] == "awaiting_confirmation"
    assert response["stage"] == "script"
    assert repeated["content"] == "script draft"
    assert [item.event for item in repo.list_drama_stage_versions("run_1")] == ["draft"]


def test_advance_deepagent_trace_is_best_effort_when_memory_load_fails(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _trace_deps(repo, tmp_path)

    def fail_load(project_id):
        raise RuntimeError("memory unavailable")

    deps.ip_memory_repo.load = fail_load
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project-a",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {},
        "confirmed_stages": [],
        "pending_stage": None,
        "video_run_id": "",
    }

    response = advance_deepagent(
        deps,
        state,
        "run_1",
        generator=lambda story_path, stage, drafts: {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "content": "script draft",
            "events": [],
        },
    )

    assert response["status"] == "awaiting_confirmation"
    event = deps.agent_trace_store.list("run_1")[0].to_dict()
    assert event["event"] == "draft_created"
    assert event["memory_snapshot"] == "sha256:empty"
    assert event["review"] == {
        "stage": "script",
        "status": "ok",
        "warnings": [],
        "score": 1.0,
    }


def test_confirm_stage_can_resume_pending_draft_from_repository(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    first_state = AppState()
    first_state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {},
        "confirmed_stages": [],
        "pending_stage": None,
        "video_run_id": "",
    }
    advance_deepagent(
        deps,
        first_state,
        "run_1",
        generator=lambda story_path, stage, drafts: {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "content": "durable script draft",
            "events": [],
        },
    )

    resumed_state = AppState()
    response = confirm_stage(
        deps,
        resumed_state,
        "run_1",
        "script",
        "",
        video_starter=lambda state, story_path, shot_limit, drafts: "video_unused",
    )

    assert response["status"] == "ready_for_next_stage"
    assert response["next_stage"] == "style"
    assert resumed_state.video_deepagent_specs["run_1"]["stage_drafts"]["script"] == "durable script draft"
    assert repo.get_drama_session("run_1").stage_drafts["script"] == "durable script draft"


def test_confirm_stage_starts_video_after_final_confirmation(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "测试主题/小说正文.md",
        "project_id": "project_1",
        "shot_limit": 3,
        "stage_drafts": {
            "script": "script",
            "style": "style",
            "plot": "plot",
            "character_refs": "refs",
        },
        "drafts": {},
        "confirmed_stages": ["script", "style", "plot", "character_refs"],
        "pending_stage": "storyboard",
        "video_run_id": "",
    }

    response = confirm_stage(
        deps,
        state,
        "run_1",
        "storyboard",
        "storyboard confirmed",
        video_starter=lambda state, story_path, shot_limit, drafts, project_id="": f"video_for_{project_id}",
    )

    assert response["status"] == "video_started"
    assert response["video_run_id"] == "video_for_project_1"
    assert state.video_deepagent_specs["run_1"]["stage_drafts"]["storyboard"] == "storyboard confirmed"


def test_revise_stage_records_human_feedback(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {"script": "old draft"},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
    }

    response = revise_stage(
        deps,
        state,
        "run_1",
        "script",
        current_draft="",
        feedback="更强冲突",
        reviser=lambda story_path, stage, drafts, current_draft="", human_feedback="": {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": f"revised from {current_draft}: {human_feedback}",
            "events": [],
        },
    )

    assert response["status"] == "awaiting_confirmation"
    assert "old draft" in response["content"]
    version = repo.list_drama_stage_versions("run_1")[0]
    assert version.event == "revision"
    assert version.human_feedback == "更强冲突"


def test_revise_stage_records_human_revision_requested_trace(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _trace_deps(repo, tmp_path)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project-a",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {"script": "old draft"},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
    }

    revise_stage(
        deps,
        state,
        "run_1",
        "script",
        current_draft="",
        feedback="更强冲突",
        reviser=lambda story_path, stage, drafts, current_draft="", human_feedback="": {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": "revised script",
            "events": [{"type": "human_feedback", "content": human_feedback}],
        },
    )

    event = deps.agent_trace_store.list("run_1")[0].to_dict()
    version = repo.list_drama_stage_versions("run_1")[0]
    assert event["event"] == "human_revision_requested"
    assert event["node_id"] == "drama.script"
    assert event["human_decision"] == {
        "decision": "revise",
        "feedback": "更强冲突",
    }
    assert event["metadata"]["version_id"] == version.id
    assert event["metadata"]["feedback"] == "更强冲突"
    assert event["metadata"]["events"] == [{"type": "human_feedback", "content": "更强冲突"}]


def test_revise_stage_marks_matching_rework_request_completed(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project_1",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {"script": "old draft"},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
        "rework_requests": [
            {
                "review_id": "review_1",
                "project_id": "project_1",
                "run_id": "run_1",
                "stage": "script",
                "target_kind": "stage_version",
                "target_id": "version_1",
                "instruction": "加强冲突",
                "comment": "冲突不够",
                "status": "requested",
            }
        ],
    }

    response = revise_stage(
        deps,
        state,
        "run_1",
        "script",
        current_draft="",
        feedback="加强冲突",
        reviser=lambda story_path, stage, drafts, current_draft="", human_feedback="": {
            "stage": stage,
            "label": "剧本",
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": "revised script",
            "events": [],
        },
    )

    request = state.video_deepagent_specs["run_1"]["rework_requests"][0]
    assert request["status"] == "completed"
    assert request["completed_stage_version_id"]
    assert response["rework_request"] == request


def test_retry_failed_stage_regenerates_pending_stage_without_skipping_confirmation(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project_1",
        "shot_limit": 1,
        "stage_drafts": {"script": "confirmed script"},
        "drafts": {"style": "stale failed draft"},
        "confirmed_stages": ["script"],
        "pending_stage": "style",
        "video_run_id": "",
    }
    repo.save_drama_session(
        DramaProjectSession(
            id="run_1",
            story_path="故事.md",
            project_id="project_1",
            shot_limit=1,
            stage_drafts={"script": "confirmed script"},
            drafts={"style": "stale failed draft"},
            confirmed_stages=["script"],
            pending_stage="style",
            status="failed",
            error="model timeout",
        )
    )

    response = retry_failed_stage(
        deps,
        state,
        "run_1",
        generator=lambda story_path, stage, drafts: {
            "stage": stage,
            "label": "风格设计",
            "model": "deepseek-v4-pro",
            "content": "retried style draft",
            "events": [{"type": "ai_text", "content": "retry"}],
        },
    )

    assert response["status"] == "awaiting_confirmation"
    assert response["stage"] == "style"
    assert response["content"] == "retried style draft"
    assert state.video_deepagent_specs["run_1"]["drafts"]["style"] == "retried style draft"
    assert state.video_deepagent_specs["run_1"]["confirmed_stages"] == ["script"]
    session = repo.get_drama_session("run_1")
    assert session.status == "awaiting_confirmation"
    assert session.pending_stage == "style"
    assert session.error == ""
    assert session.stage_drafts == {"script": "confirmed script"}
    versions = repo.list_drama_stage_versions("run_1")
    assert [(version.stage, version.event, version.content) for version in versions] == [
        ("style", "restore", "retried style draft")
    ]


def test_retry_failed_stage_records_restored_draft_trace(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _trace_deps(repo, tmp_path)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project-a",
        "shot_limit": 1,
        "stage_drafts": {"script": "confirmed script"},
        "drafts": {"style": "stale failed draft"},
        "confirmed_stages": ["script"],
        "pending_stage": "style",
        "video_run_id": "",
    }
    repo.save_drama_session(
        DramaProjectSession(
            id="run_1",
            story_path="故事.md",
            project_id="project-a",
            stage_drafts={"script": "confirmed script"},
            drafts={"style": "stale failed draft"},
            confirmed_stages=["script"],
            pending_stage="style",
            status="failed",
            error="model timeout",
        )
    )

    retry_failed_stage(
        deps,
        state,
        "run_1",
        generator=lambda story_path, stage, drafts: {
            "stage": stage,
            "label": "风格设计",
            "model": "deepseek-v4-pro",
            "content": "retried style draft",
            "events": [{"type": "ai_text", "content": "retry"}],
        },
    )

    event = deps.agent_trace_store.list("run_1")[0].to_dict()
    version = repo.list_drama_stage_versions("run_1")[0]
    assert event["event"] == "draft_created"
    assert event["node_id"] == "drama.style"
    assert event["metadata"]["version_id"] == version.id
    assert event["metadata"]["retry"] is True
    assert event["metadata"]["events"] == [{"type": "ai_text", "content": "retry"}]


def test_retry_failed_stage_rejects_non_failed_session(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {"script": "draft"},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
    }
    repo.save_drama_session(
        DramaProjectSession(
            id="run_1",
            story_path="故事.md",
            drafts={"script": "draft"},
            pending_stage="script",
            status="awaiting_confirmation",
        )
    )

    with pytest.raises(HTTPException) as exc:
        retry_failed_stage(
            deps,
            state,
            "run_1",
            generator=lambda story_path, stage, drafts: {"content": "new draft"},
        )

    assert exc.value.status_code == 409
    assert "只有失败" in exc.value.detail


def test_retry_failed_stage_requires_persisted_failed_session(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {},
        "drafts": {"script": "draft"},
        "confirmed_stages": [],
        "pending_stage": "script",
        "video_run_id": "",
    }

    with pytest.raises(HTTPException) as exc:
        retry_failed_stage(
            deps,
            state,
            "run_1",
            generator=lambda story_path, stage, drafts: {"content": "new draft"},
        )

    assert exc.value.status_code == 409
    assert "只有失败" in exc.value.detail


def test_retry_failed_stage_rejects_already_confirmed_pending_stage(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {"script": "confirmed script", "style": "confirmed style"},
        "drafts": {"style": "failed style draft"},
        "confirmed_stages": ["script", "style"],
        "pending_stage": "style",
        "video_run_id": "",
    }
    repo.save_drama_session(
        DramaProjectSession(
            id="run_1",
            story_path="故事.md",
            stage_drafts={"script": "confirmed script", "style": "confirmed style"},
            drafts={"style": "failed style draft"},
            confirmed_stages=["script", "style"],
            pending_stage="style",
            status="failed",
            error="model timeout",
        )
    )

    with pytest.raises(HTTPException) as exc:
        retry_failed_stage(
            deps,
            state,
            "run_1",
            generator=lambda story_path, stage, drafts: {"content": "new style"},
        )

    assert exc.value.status_code == 409
    assert "已确认" in exc.value.detail
    assert repo.get_drama_session("run_1").status == "failed"


def test_retry_failed_stage_keeps_session_failed_when_generator_fails(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "project_id": "project_1",
        "shot_limit": 1,
        "stage_drafts": {"script": "confirmed script"},
        "drafts": {"style": "failed style draft"},
        "confirmed_stages": ["script"],
        "pending_stage": "style",
        "video_run_id": "",
    }
    repo.save_drama_session(
        DramaProjectSession(
            id="run_1",
            story_path="故事.md",
            project_id="project_1",
            stage_drafts={"script": "confirmed script"},
            drafts={"style": "failed style draft"},
            confirmed_stages=["script"],
            pending_stage="style",
            status="failed",
            error="model timeout",
        )
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        retry_failed_stage(
            deps,
            state,
            "run_1",
            generator=lambda story_path, stage, drafts: (_ for _ in ()).throw(
                RuntimeError("provider unavailable")
            ),
        )

    session = repo.get_drama_session("run_1")
    assert session.status == "failed"
    assert session.pending_stage == "style"
    assert session.error == "provider unavailable"
    assert session.stage_drafts == {"script": "confirmed script"}


def test_advance_deepagent_rejects_failed_session_until_retry(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    state.video_deepagent_specs["run_1"] = {
        "story_path": "故事.md",
        "shot_limit": 1,
        "stage_drafts": {"script": "confirmed script"},
        "drafts": {"style": "failed style draft"},
        "confirmed_stages": ["script"],
        "pending_stage": "style",
        "video_run_id": "",
    }
    repo.save_drama_session(
        DramaProjectSession(
            id="run_1",
            story_path="故事.md",
            stage_drafts={"script": "confirmed script"},
            drafts={"style": "failed style draft"},
            confirmed_stages=["script"],
            pending_stage="style",
            status="failed",
            error="model timeout",
        )
    )

    with pytest.raises(HTTPException) as exc:
        advance_deepagent(
            deps,
            state,
            "run_1",
            generator=lambda story_path, stage, drafts: {"content": "bypass draft"},
        )

    assert exc.value.status_code == 409
    assert "请先重试失败阶段" in exc.value.detail

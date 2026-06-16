"""Tests for short-drama DeepAgent session persistence helpers."""
from __future__ import annotations

from types import SimpleNamespace

from zhihu_fiction.app.services.drama_video_sessions import (
    get_session_spec,
    persist_session,
    record_stage_version,
    session_to_spec,
)
from zhihu_fiction.app.state import AppState
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def _deps(repo):
    return SimpleNamespace(workspace_repo=repo)


def test_persist_session_round_trips_spec_and_preserves_created_at(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    spec = {
        "story_path": "故事/小说正文.md",
        "project_id": "project_1",
        "shot_limit": 3,
        "stage_drafts": {"script": "确认剧本"},
        "drafts": {"style": "风格草稿"},
        "confirmed_stages": ["script"],
        "pending_stage": "style",
        "video_run_id": "video_1",
        "rework_requests": [
            {
                "review_id": "review_1",
                "stage": "style",
                "instruction": "加强赛博朋克视觉",
                "status": "requested",
            }
        ],
    }

    first = persist_session(deps, "run_1", spec, "awaiting_confirmation")
    second = persist_session(deps, "run_1", spec, "ready_for_next_stage")

    assert second.created_at == first.created_at
    assert second.status == "ready_for_next_stage"
    assert second.project_id == "project_1"
    assert session_to_spec(second) == spec


def test_get_session_spec_hydrates_runtime_state_from_repository(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    state = AppState()
    persist_session(deps, "run_1", {"story_path": "故事.md", "project_id": "project_1", "shot_limit": 1}, "started")

    spec = get_session_spec(deps, state, "run_1")

    assert spec["story_path"] == "故事.md"
    assert spec["project_id"] == "project_1"
    assert state.video_deepagent_specs["run_1"] is spec


def test_record_stage_version_truncates_content_and_persists_metadata(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    deps = _deps(repo)
    persist_session(
        deps,
        "run_1",
        {"story_path": "故事.md", "project_id": "project_1", "shot_limit": 1},
        "started",
    )

    version = record_stage_version(
        deps,
        "run_1",
        "script",
        "x" * 20050,
        "revision",
        human_feedback="加快节奏",
        metadata={"events": [{"type": "tool_call"}]},
    )

    assert len(version.content) == 20000
    assert version.project_id == "project_1"
    assert version.human_feedback == "加快节奏"
    assert repo.list_drama_stage_versions("run_1")[0].metadata == {"events": [{"type": "tool_call"}]}

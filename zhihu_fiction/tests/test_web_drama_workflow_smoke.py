"""Fast API smoke tests for the project short-drama workflow."""
from __future__ import annotations

from fastapi.testclient import TestClient

import zhihu_fiction.server as server_mod
from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.app.services import drama_video_runtime
from zhihu_fiction.app.state import AppState
from zhihu_fiction.ip_memory.repository import IPMemoryRepository
from zhihu_fiction.ip_memory.trace import AgentTraceStore
from zhihu_fiction.workspace.models import Project, Story
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_project_workspace_guides_deepagent_stage_loop_from_story_to_video(monkeypatch, tmp_path):
    story_rel_path = "output/smoke_story/小说正文.md"
    story_file = tmp_path / story_rel_path
    story_file.parent.mkdir(parents=True)
    story_file.write_text(
        "# 山西异味事件短剧\n\n> 题材：现实悬疑\n\n女主被异味熏醒后追查真相。",
        encoding="utf-8",
    )
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path / "output")

    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_smoke", title="山西异味事件短剧"))
    repo.save_story(Story(
        id="story_smoke",
        project_id="project_smoke",
        title="小说正文",
        body_path=story_rel_path,
    ))
    dependencies = AppDependencies(
        workspace_repo=repo,
        ip_memory_repo=IPMemoryRepository(tmp_path / "ip_memory"),
        agent_trace_store=AgentTraceStore(tmp_path / "agent_traces"),
    )
    state = AppState()

    counters = {"deepagent": 0, "video": 0}

    def deterministic_id(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}_smoke_{counters[prefix]}"

    def fake_generate_stage(_dependencies, story_path, stage, stage_drafts):
        return {
            "stage": stage,
            "label": stage,
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": f"{stage} draft for {story_path}; confirmed={','.join(stage_drafts)}",
            "events": [{"type": "tool_call", "name": f"draft_{stage}"}],
        }

    def fake_revise_stage(
        _dependencies,
        story_path,
        stage,
        stage_drafts,
        current_draft="",
        human_feedback="",
    ):
        return {
            "stage": stage,
            "label": stage,
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": f"{current_draft} | human feedback: {human_feedback}",
            "events": [{"type": "human_feedback", "content": human_feedback}],
        }

    monkeypatch.setattr(drama_video_runtime, "new_video_run_id", deterministic_id)
    monkeypatch.setattr(drama_video_runtime, "generate_video_stage_draft", fake_generate_stage)
    monkeypatch.setattr(drama_video_runtime, "run_video_stage_deepagent", fake_revise_stage)

    client = TestClient(create_app(dependencies=dependencies, state=state))

    started = client.post(
        "/api/drama-video/deepagent/loop",
        json={
            "story_path": story_rel_path,
            "project_id": "project_smoke",
            "shot_limit": 1,
        },
    )
    assert started.status_code == 200
    run_id = started.json()["run_id"]
    assert started.json()["status"] == "awaiting_confirmation"
    assert started.json()["pending_stage"] == "script"

    workspace = client.get("/api/projects/project_smoke").json()
    assert workspace["next_action"] == {
        "kind": "confirm_stage",
        "label": "确认 script 阶段",
        "target_id": run_id,
        "stage": "script",
    }

    confirmed_script = client.post(
        "/api/drama-video/deepagent/confirm",
        json={
            "run_id": run_id,
            "stage": "script",
            "content": "角色：林晚。地点：运城。限制：真相不能提前揭露。",
        },
    )
    assert confirmed_script.status_code == 200
    assert confirmed_script.json()["status"] == "ready_for_next_stage"
    assert confirmed_script.json()["next_stage"] == "style"

    workspace = client.get("/api/projects/project_smoke").json()
    assert workspace["next_action"] == {
        "kind": "generate_stage",
        "label": "生成 style 阶段",
        "target_id": run_id,
        "stage": "style",
    }

    advanced_style = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
    assert advanced_style.status_code == 200
    assert advanced_style.json()["stage"] == "style"

    revised_style = client.post(
        "/api/drama-video/deepagent/revise",
        json={
            "run_id": run_id,
            "stage": "style",
            "current_draft": advanced_style.json()["content"],
            "feedback": "增强压迫感和夜景氛围",
        },
    )
    assert revised_style.status_code == 200
    assert "增强压迫感和夜景氛围" in revised_style.json()["content"]

    confirmed_style = client.post(
        "/api/drama-video/deepagent/confirm",
        json={
            "run_id": run_id,
            "stage": "style",
            "content": revised_style.json()["content"],
        },
    )
    assert confirmed_style.status_code == 200

    for stage in ["plot", "character_refs", "storyboard"]:
        advanced = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
        assert advanced.status_code == 200
        assert advanced.json()["stage"] == stage
        confirmed = client.post(
            "/api/drama-video/deepagent/confirm",
            json={
                "run_id": run_id,
                "stage": stage,
                "content": advanced.json()["content"],
            },
        )
        assert confirmed.status_code == 200

    final_confirmation = confirmed.json()
    assert final_confirmation["status"] == "video_started"
    assert final_confirmation["video_run_id"] == "video_smoke_1"
    assert final_confirmation["stream_url"] == "/api/drama-video/stream/video_smoke_1"

    final_workspace = client.get("/api/projects/project_smoke").json()
    session = final_workspace["drama_sessions"][0]
    assert session["id"] == run_id
    assert session["status"] == "video_started"
    assert session["confirmed_stages"] == [
        "script",
        "style",
        "plot",
        "character_refs",
        "storyboard",
    ]
    assert session["video_run_id"] == "video_smoke_1"
    assert repo.get_drama_video_run("video_smoke_1").status == "queued"

    versions = client.get(f"/api/drama-video/deepagent/{run_id}/versions").json()["versions"]
    assert [version["event"] for version in versions].count("confirmation") == 5
    assert any(
        version["event"] == "revision"
        and version["human_feedback"] == "增强压迫感和夜景氛围"
        for version in versions
    )

    trace_events = client.get(f"/api/drama-video/deepagent/{run_id}/trace").json()["events"]
    assert {event["event"] for event in trace_events} >= {
        "draft_created",
        "human_revision_requested",
        "human_confirmed",
    }

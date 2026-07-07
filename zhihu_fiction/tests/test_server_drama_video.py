"""Tests for web short-drama video task endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import zhihu_fiction.server as server_mod
from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
)
from zhihu_fiction.drama.video import VideoJob, VideoJobStore
from zhihu_fiction.ip_memory.trace import AgentTraceEvent, AgentTraceStore
from zhihu_fiction.workspace.models import DramaProjectSession, DramaVideoJob, DramaVideoRun
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def make_project() -> DramaProject:
    shots = [
        DramaShot(
            id=f"ep01_sc01_sh{i:02d}",
            episode_index=1,
            scene_index=1,
            shot_index=i,
            duration_seconds=6,
            location_id="living_room",
            character_ids=["heroine"],
            action=f"女主完成第 {i} 个关键动作。",
            dialogue="我不会再退让。",
            emotion="克制但坚定",
            camera="medium close-up, slow push in",
            visual_prompt="modern Chinese living room, cinematic lighting",
            negative_prompt="low quality, blurry, distorted face",
            consistency_refs=["character.heroine", "location.living_room"],
        )
        for i in range(1, 7)
    ]
    return DramaProject(
        title="重生后我不再忍让",
        source_title="测试主题",
        genre="复仇",
        logline="被背叛的女主重生后用真相反击。",
        audience="喜欢复仇爽感和家庭冲突的短剧观众",
        episode_count=1,
        characters=[
            DramaCharacter(
                id="heroine",
                name="林夏",
                role="女主",
                age_range="25-30",
                appearance="黑色长发，冷静克制，眼神坚定",
                costume="白色衬衫和深色长裤",
                personality="隐忍、聪明、行动果断",
                motivation="查清背叛真相并夺回人生",
                consistency_prompt="林夏，25岁左右，中国女性，黑色长发，白色衬衫，冷静坚定",
            )
        ],
        locations=[
            DramaLocation(
                id="living_room",
                name="林家客厅",
                visual_style="现代中式家庭客厅，压抑而整洁",
                time_period="现代",
                lighting="夜晚室内暖光，局部阴影",
                consistency_prompt="modern Chinese family living room, warm indoor light, tense mood",
            )
        ],
        episodes=[
            DramaEpisode(
                index=1,
                title="重生醒来",
                hook="女主在被害当天醒来，发现时间倒流。",
                synopsis="林夏重新回到被陷害的夜晚，第一次选择正面反击。",
                cliffhanger="她拿出录音笔，继母脸色骤变。",
                shots=shots,
            )
        ],
        adaptation_notes=["保留原小说的复仇主线，压缩支线。"],
        risk_notes=["避免过度暴力和违法细节。"],
    )


def test_drama_video_endpoint_submits_limited_shots(monkeypatch, tmp_path):
    project = make_project()
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    story_file = story_dir / "小说正文.md"
    story_file.write_text("# 测试主题\n\n> 题材：复仇\n\n女主被陷害后重生。", encoding="utf-8")
    submitted_shot_ids = []
    appended_jobs = []

    class StubAdapter:
        def __init__(self, llm):
            self.llm = llm

        def adapt_result(self, result):
            assert result.topic == "测试主题"
            assert "女主被陷害后重生" in result.final_story
            return project

    class StubExporter:
        def export(self, exported_project):
            assert exported_project is project
            package_dir = tmp_path / "测试主题" / "短剧视频Prompt包_20260610_120000"
            package_dir.mkdir()
            return package_dir

        def export_failure(self, source_title, raw_output, error):
            raise AssertionError("export_failure should not be called")

    class StubJob:
        def __init__(self, shot_id):
            self.shot_id = shot_id
            self.provider_job_id = f"task-{shot_id}"
            self.status = "PENDING"

        def to_dict(self):
            return {
                "shot_id": self.shot_id,
                "provider_job_id": self.provider_job_id,
                "status": self.status,
            }

    class StubProvider:
        def submit_shot(self, shot):
            submitted_shot_ids.append(shot.id)
            return StubJob(shot.id)

    class StubStore:
        def __init__(self, path: Path):
            self.path = path

        def append(self, job):
            appended_jobs.append(job)

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "create_llm", lambda settings, temperature=0.3: object())
    monkeypatch.setattr(server_mod, "DramaAdapter", StubAdapter)
    monkeypatch.setattr(server_mod, "DramaExporter", StubExporter)
    monkeypatch.setattr(server_mod, "create_video_provider", lambda: StubProvider())
    monkeypatch.setattr(server_mod, "VideoJobStore", StubStore)

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "submitted"
    assert data["submitted_count"] == 2
    assert data["package_dir"].endswith("短剧视频Prompt包_20260610_120000")
    assert data["jobs_path"].endswith("video_jobs.jsonl")
    assert [job["shot_id"] for job in data["jobs"]] == [
        "ep01_sc01_sh01",
        "ep01_sc01_sh02",
    ]
    assert submitted_shot_ids == ["ep01_sc01_sh01", "ep01_sc01_sh02"]
    assert [job.shot_id for job in appended_jobs] == submitted_shot_ids


def test_drama_video_endpoint_requires_cost_confirmation_before_submit(monkeypatch, tmp_path):
    story_dir = tmp_path / "同步预算主题"
    story_dir.mkdir()
    story_file = story_dir / "小说正文.md"
    story_file.write_text("# 同步预算主题\n\n正文", encoding="utf-8")
    called = {"adapter": 0, "provider": 0}

    class BlockingAdapter:
        def __init__(self, llm):
            called["adapter"] += 1
            raise AssertionError("adapter must not run before budget confirmation")

    class BlockingProvider:
        def submit_shot(self, shot):
            called["provider"] += 1
            raise AssertionError("provider must not run before budget confirmation")

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "DramaAdapter", BlockingAdapter)
    monkeypatch.setattr(server_mod, "create_video_provider", lambda: BlockingProvider())
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "1")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video",
        json={"story_path": "同步预算主题/小说正文.md", "shot_limit": 2},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert detail["cost_guardrail"]["within_budget"] is False
    assert detail["cost_guardrail"]["estimate"]["estimated_total_cny"] == 2.0
    assert called == {"adapter": 0, "provider": 0}


def test_drama_video_stream_reports_generation_stages(monkeypatch, tmp_path):
    project = make_project()
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    story_file = story_dir / "小说正文.md"
    story_file.write_text("# 测试主题\n\n> 题材：复仇\n\n女主被陷害后重生。", encoding="utf-8")

    class StubAdapter:
        def __init__(self, llm):
            self.llm = llm

        def adapt_result(self, result):
            assert "剧本草稿：保留女主反击主线" in result.synthesis
            assert "风格草稿：现代都市冷色电影感" in result.synthesis
            assert "不会进入生成上下文" not in result.synthesis
            return project

    class StubExporter:
        def export(self, exported_project):
            package_dir = tmp_path / "测试主题" / "短剧视频Prompt包_20260610_120000"
            package_dir.mkdir()
            return package_dir

        def export_failure(self, source_title, raw_output, error):
            raise AssertionError("export_failure should not be called")

    class StubJob:
        def __init__(self, shot_id):
            self.shot_id = shot_id
            self.provider_job_id = f"task-{shot_id}"
            self.status = "PENDING"

        def to_dict(self):
            return {
                "shot_id": self.shot_id,
                "provider_job_id": self.provider_job_id,
                "status": self.status,
            }

    class StubProvider:
        def submit_shot(self, shot):
            return StubJob(shot.id)

    class StubStore:
        def __init__(self, path: Path):
            self.path = path

        def append(self, job):
            pass

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "create_llm", lambda settings, temperature=0.3: object())
    monkeypatch.setattr(server_mod, "DramaAdapter", StubAdapter)
    monkeypatch.setattr(server_mod, "DramaExporter", StubExporter)
    monkeypatch.setattr(server_mod, "create_video_provider", lambda: StubProvider())
    monkeypatch.setattr(server_mod, "VideoJobStore", StubStore)

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/run",
        json={
            "story_path": "测试主题/小说正文.md",
            "shot_limit": 2,
            "stage_drafts": {
                "script": "剧本草稿：保留女主反击主线",
                "style": "风格草稿：现代都市冷色电影感",
                "unexpected": "不会进入生成上下文",
            },
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    queued_run = server_mod.workspace_repo.get_drama_video_run(run_id)
    assert queued_run.status == "queued"
    assert queued_run.stage_drafts == {
        "script": "剧本草稿：保留女主反击主线",
        "style": "风格草稿：现代都市冷色电影感",
    }

    with client.stream("GET", f"/api/drama-video/stream/{run_id}") as stream:
        text = "".join(stream.iter_text())

    completed_run = server_mod.workspace_repo.get_drama_video_run(run_id)
    assert completed_run.status == "completed"
    assert completed_run.submitted_count == 2
    assert completed_run.jobs_path.endswith("video_jobs.jsonl")
    assert "event: stage_update" in text
    assert '"stage": "script"' in text
    assert '"stage": "style"' in text
    assert '"stage": "plot"' in text
    assert '"stage": "character_refs"' in text
    assert '"stage": "storyboard"' in text
    assert '"stage": "video"' in text
    assert "event: complete" in text
    assert '"status": "completed"' in text
    assert '"submitted_count": 2' in text


def test_drama_video_stream_uses_video_queue(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    enqueued = []

    class RecordingQueue:
        def enqueue(self, job_id, submit):
            enqueued.append(job_id)
            return submit()

    class ImmediateBackgroundTasks:
        def create_task(self, coro):
            coro.close()
            server_mod.app.state.runtime.video_events[run_id].put_nowait({
                "type": "complete",
                "data": {
                    "run_id": run_id,
                    "status": "completed",
                    "message": "scheduled",
                    "progress": 100,
                },
            })
            return "scheduled"

    monkeypatch.setattr(server_mod.drama_video_runtime, "create_video_queue", lambda: RecordingQueue())
    monkeypatch.setattr(
        server_mod.drama_video_runtime,
        "create_background_task",
        ImmediateBackgroundTasks().create_task,
    )

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 1},
    )
    run_id = started.json()["run_id"]

    with client.stream("GET", f"/api/drama-video/stream/{run_id}") as stream:
        _ = next(stream.iter_text())

    assert enqueued == [run_id]


def test_drama_video_run_persists_project_id(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/run",
        json={
            "story_path": "测试主题/小说正文.md",
            "shot_limit": 1,
            "project_id": "project_1",
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    run = server_mod.workspace_repo.get_drama_video_run(run_id)
    job = server_mod.workspace_repo.get_drama_video_job(run_id)
    assert run.project_id == "project_1"
    assert job.payload["project_id"] == "project_1"


def test_drama_video_run_requires_cost_confirmation_when_budget_is_exceeded(monkeypatch, tmp_path):
    story_dir = tmp_path / "预算主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 预算主题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "1")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    run_ids_before = {run.id for run in server_mod.workspace_repo.list_drama_video_runs()}
    response = client.post(
        "/api/drama-video/run",
        json={"story_path": "预算主题/小说正文.md", "shot_limit": 2},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "video generation budget requires confirmation"
    assert detail["requires_confirmation"] is True
    assert detail["cost_guardrail"]["configured"] is True
    assert detail["cost_guardrail"]["within_budget"] is False
    assert detail["cost_guardrail"]["estimate"]["shot_count"] == 2
    assert detail["cost_guardrail"]["estimate"]["estimated_total_cny"] == 2.0
    assert detail["cost_guardrail"]["budget"]["remaining_today_cny"] < 2.0
    assert {run.id for run in server_mod.workspace_repo.list_drama_video_runs()} == run_ids_before


def test_drama_video_run_allows_explicit_cost_confirmation(monkeypatch, tmp_path):
    story_dir = tmp_path / "预算确认主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 预算确认主题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "1")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/run",
        json={
            "story_path": "预算确认主题/小说正文.md",
            "shot_limit": 2,
            "confirm_cost": True,
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    run = server_mod.workspace_repo.get_drama_video_run(run_id)
    assert run.story_path == "预算确认主题/小说正文.md"
    assert run.shot_limit == 2
    assert server_mod.workspace_repo.get_drama_video_job(run_id).status == "queued"


def test_drama_video_run_confirmation_records_estimated_cost_for_budget_reuse(monkeypatch, tmp_path):
    story_dir = tmp_path / "预算复用主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 预算复用主题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "3")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    first = client.post(
        "/api/drama-video/run",
        json={
            "story_path": "预算复用主题/小说正文.md",
            "shot_limit": 2,
            "project_id": "project_budget_reuse",
            "confirm_cost": True,
        },
    )
    assert first.status_code == 200
    first_run_id = first.json()["run_id"]
    entries = [
        entry
        for entry in server_mod.workspace_repo.list_cost_ledger_entries(project_id="project_budget_reuse")
        if entry.run_id == first_run_id and entry.source == "video_run_estimate"
    ]
    assert len(entries) == 1
    assert entries[0].amount_cny == 2.0

    second = client.post(
        "/api/drama-video/run",
        json={
            "story_path": "预算复用主题/小说正文.md",
            "shot_limit": 2,
            "project_id": "project_budget_reuse",
        },
    )

    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["cost_guardrail"]["budget"]["spent_today_cny"] >= 2.0
    assert detail["cost_guardrail"]["budget"]["remaining_today_cny"] <= 1.0
    assert detail["cost_guardrail"]["within_budget"] is False


def test_drama_video_endpoint_rejects_missing_story():
    client = TestClient(server_mod.app)

    response = client.post("/api/drama-video", json={"story_path": "missing.md"})

    assert response.status_code == 404


def test_drama_video_stage_endpoint_uses_deepagent_with_deepseek_v4pro(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    story_file = story_dir / "小说正文.md"
    story_file.write_text("# 测试主题\n\n> 题材：复仇\n\n女主被陷害后重生。", encoding="utf-8")

    fake_llm = object()
    fake_coordinator = object()
    captured = {}

    def fake_create_llm(incoming_settings, temperature=0.3):
        captured["settings"] = incoming_settings
        captured["temperature"] = temperature
        return fake_llm

    def fake_create_drama_video_coordinator(llm, stage):
        captured["coordinator_llm"] = llm
        captured["coordinator_stage"] = stage
        return fake_coordinator

    def fake_run_drama_video_coordinator(
        coordinator,
        *,
        result,
        stage,
        stage_drafts,
        current_draft="",
        human_feedback="",
        stream_callback=None,
    ):
        captured["run_coordinator"] = coordinator
        captured["result"] = result
        captured["stage"] = stage
        captured["stage_drafts"] = dict(stage_drafts)
        captured["current_draft"] = current_draft
        captured["human_feedback"] = human_feedback
        if stream_callback:
            stream_callback({"type": "tool_call", "name": "design_drama_style", "args": {}})
        return {
            "content": "## 风格设计\n现代都市冷色电影感，稳定角色一致性。",
            "events": [{"type": "tool_call", "name": "design_drama_style"}],
        }

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "settings", SimpleNamespace(model="deepseek-v4-pro"))
    monkeypatch.setattr(server_mod, "create_llm", fake_create_llm)
    monkeypatch.setattr(server_mod, "create_drama_video_coordinator", fake_create_drama_video_coordinator)
    monkeypatch.setattr(server_mod, "run_drama_video_coordinator", fake_run_drama_video_coordinator)

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/stage",
        json={
            "story_path": "测试主题/小说正文.md",
            "stage": "style",
            "stage_drafts": {
                "script": "剧本草稿：保留女主反击主线",
                "unexpected": "不会进入生成上下文",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stage"] == "style"
    assert data["label"] == "风格设计"
    assert data["model"] == "deepseek-v4-pro"
    assert data["agent"] == "deepagent"
    assert "现代都市冷色电影感" in data["content"]
    assert captured["temperature"] == 0.4
    assert captured["coordinator_llm"] is fake_llm
    assert captured["coordinator_stage"] == "style"
    assert captured["run_coordinator"] is fake_coordinator
    assert captured["stage"] == "style"
    assert captured["result"].topic == "测试主题"
    assert "女主被陷害后重生" in captured["result"].final_story
    assert captured["stage_drafts"] == {"script": "剧本草稿：保留女主反击主线"}
    assert captured["current_draft"] == ""
    assert captured["human_feedback"] == ""


def test_drama_video_stage_endpoint_rejects_video_stage(tmp_path, monkeypatch):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/stage",
        json={"story_path": "测试主题/小说正文.md", "stage": "video"},
    )

    assert response.status_code == 400


def test_drama_video_run_refresh_updates_provider_jobs(monkeypatch, tmp_path):
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    store = VideoJobStore(jobs_path)
    store.append(VideoJob(provider="bailian", provider_job_id="task-1", shot_id="shot_1", status="PENDING"))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_refresh",
            story_path="测试主题/小说正文.md",
            shot_limit=1,
            status="completed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(jobs_path.parent),
        )
    )

    class StubProvider:
        def get_job(self, provider_job_id, shot_id=""):
            return VideoJob(
                provider="bailian",
                provider_job_id=provider_job_id,
                shot_id=shot_id,
                status="SUCCEEDED",
                video_url="https://example.com/video.mp4",
            )

    monkeypatch.setattr(server_mod, "create_video_provider", lambda: StubProvider())

    client = TestClient(server_mod.app)
    response = client.post(f"/api/drama-video/run/{run.id}/refresh")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["summary"] == {"SUCCEEDED": 1}
    assert data["jobs"][0]["video_url"] == "https://example.com/video.mp4"
    assert server_mod.workspace_repo.get_drama_video_run(run.id).status == "completed"
    assert VideoJobStore(jobs_path).list()[0].status == "SUCCEEDED"


def test_drama_video_jobs_api_lists_jobs_for_run():
    server_mod.workspace_repo.save_drama_video_job(DramaVideoJob(
        id="video_jobs_api_run",
        kind="generate_video",
        run_id="video_jobs_api_run",
        status="completed",
        payload={"story_path": "故事/小说正文.md"},
        result={"submitted_count": 2},
        updated_at="2026-06-11T10:00:00+00:00",
    ))
    server_mod.workspace_repo.save_drama_video_job(DramaVideoJob(
        id="video_jobs_api_retry",
        kind="retry_shot",
        run_id="video_jobs_api_run",
        shot_id="shot_1",
        status="queued",
        updated_at="2026-06-11T11:00:00+00:00",
    ))
    server_mod.workspace_repo.save_drama_video_job(DramaVideoJob(
        id="video_jobs_api_other",
        kind="generate_video",
        run_id="video_jobs_api_other",
        status="completed",
    ))

    client = TestClient(server_mod.app)
    response = client.get("/api/drama-video/jobs", params={"run_id": "video_jobs_api_run"})

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "video_jobs_api_run"
    assert [job["id"] for job in data["jobs"]] == [
        "video_jobs_api_retry",
        "video_jobs_api_run",
    ]
    assert data["summary"] == {"queued": 1, "completed": 1}


def test_drama_video_retry_job_api_queues_background_work(monkeypatch, tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text(
        json.dumps([
            {
                "id": "shot_1",
                "episode_index": 1,
                "scene_index": 1,
                "shot_index": 1,
                "duration_seconds": 6,
                "location_id": "room",
                "character_ids": ["hero"],
                "action": "反击",
                "dialogue": "我不会退让。",
                "emotion": "坚定",
                "camera": "close up",
                "visual_prompt": "cinematic room",
                "negative_prompt": "low quality",
                "consistency_refs": ["character.hero", "location.room"],
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_retry_api",
            story_path="测试主题/小说正文.md",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
            error="1 video job(s) failed",
        )
    )

    class BlockingProvider:
        def submit_shot(self, shot):
            raise AssertionError("retry provider must not run in request thread")

    class ImmediateBackgroundTasks:
        def __init__(self):
            self.scheduled = 0

        def create_task(self, coro):
            self.scheduled += 1
            coro.close()

    background = ImmediateBackgroundTasks()
    monkeypatch.setattr(server_mod, "create_video_provider", lambda: BlockingProvider())
    monkeypatch.setattr(server_mod.drama_video_runtime, "create_background_task", background.create_task)

    client = TestClient(server_mod.app)
    response = client.post(
        f"/api/drama-video/run/{run.id}/retry",
        json={"shot_id": "shot_1", "confirm_cost": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["run_id"] == run.id
    assert data["shot_id"] == "shot_1"
    assert data["retry_job_id"].startswith("video_retry_")
    assert data["retry_url"] == f"/api/drama-video/retry/{data['retry_job_id']}"
    assert background.scheduled == 1
    assert VideoJobStore(jobs_path).list()[0].provider_job_id == "task-failed"
    assert server_mod.app.state.runtime.video_retry_jobs[data["retry_job_id"]]["status"] == "queued"
    stored_job = server_mod.workspace_repo.get_drama_video_job(data["retry_job_id"])
    assert stored_job.kind == "retry_shot"
    assert stored_job.run_id == run.id
    assert stored_job.shot_id == "shot_1"
    assert stored_job.status == "queued"
    assert stored_job.payload == {"shot_id": "shot_1"}


def test_drama_video_retry_job_api_uses_video_queue(monkeypatch, tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text("[]", encoding="utf-8")
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_queue_api",
            story_path="测试主题/小说正文.md",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
        )
    )
    enqueued = []

    class RecordingQueue:
        def enqueue(self, job_id, submit):
            enqueued.append(job_id)
            return submit()

    class ImmediateBackgroundTasks:
        def create_task(self, coro):
            coro.close()
            return "scheduled"

    monkeypatch.setattr(server_mod.drama_video_runtime, "create_video_queue", lambda: RecordingQueue())
    monkeypatch.setattr(
        server_mod.drama_video_runtime,
        "create_background_task",
        ImmediateBackgroundTasks().create_task,
    )

    client = TestClient(server_mod.app)
    response = client.post(
        f"/api/drama-video/run/{run.id}/retry",
        json={"shot_id": "shot_1", "confirm_cost": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert enqueued == [data["retry_job_id"]]
    assert data["status"] == "queued"


def test_drama_video_retry_requires_cost_confirmation_when_budget_is_exceeded(monkeypatch, tmp_path):
    package_dir = tmp_path / "budget_retry_package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text("[]", encoding="utf-8")
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_retry_budget_guard",
            story_path="预算主题/小说正文.md",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
        )
    )
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "0")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    job_ids_before = {
        job.id
        for job in server_mod.workspace_repo.list_drama_video_jobs(run_id=run.id)
    }
    response = client.post(f"/api/drama-video/run/{run.id}/retry", json={"shot_id": "shot_1"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "video generation budget requires confirmation"
    assert detail["requires_confirmation"] is True
    assert detail["cost_guardrail"]["within_budget"] is False
    assert detail["cost_guardrail"]["estimate"]["shot_count"] == 1
    assert {
        job.id
        for job in server_mod.workspace_repo.list_drama_video_jobs(run_id=run.id)
    } == job_ids_before
    assert not any(
        job.get("run_id") == run.id
        for job in server_mod.app.state.runtime.video_retry_jobs.values()
    )


def test_drama_video_retry_validates_shot_before_cost_confirmation(monkeypatch, tmp_path):
    package_dir = tmp_path / "budget_retry_missing_shot_package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text("[]", encoding="utf-8")
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_retry_budget_missing_shot",
            story_path="预算主题/小说正文.md",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
        )
    )
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "0")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    job_ids_before = {
        job.id
        for job in server_mod.workspace_repo.list_drama_video_jobs(run_id=run.id)
    }
    response = client.post(f"/api/drama-video/run/{run.id}/retry", json={"shot_id": "missing_shot"})

    assert response.status_code == 404
    assert response.json()["detail"] == "镜头任务未找到"
    assert {
        job.id
        for job in server_mod.workspace_repo.list_drama_video_jobs(run_id=run.id)
    } == job_ids_before


def test_drama_video_retry_rejects_missing_shot_even_with_cost_confirmation(monkeypatch, tmp_path):
    package_dir = tmp_path / "budget_retry_missing_shot_confirm_package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text("[]", encoding="utf-8")
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_retry_budget_missing_shot_confirm",
            story_path="预算主题/小说正文.md",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
        )
    )
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "0")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    job_ids_before = {
        job.id
        for job in server_mod.workspace_repo.list_drama_video_jobs(run_id=run.id)
    }
    response = client.post(
        f"/api/drama-video/run/{run.id}/retry",
        json={"shot_id": "missing_shot", "confirm_cost": True},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "镜头任务未找到"
    assert {
        job.id
        for job in server_mod.workspace_repo.list_drama_video_jobs(run_id=run.id)
    } == job_ids_before


def test_drama_video_retry_allows_explicit_cost_confirmation(monkeypatch, tmp_path):
    package_dir = tmp_path / "budget_retry_confirm_package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text("[]", encoding="utf-8")
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_retry_budget_confirm",
            story_path="预算主题/小说正文.md",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
        )
    )
    enqueued = []

    class RecordingQueue:
        def enqueue(self, job_id, submit):
            enqueued.append(job_id)
            return submit()

    class ImmediateBackgroundTasks:
        def create_task(self, coro):
            coro.close()
            return "scheduled"

    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "0")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    monkeypatch.setattr(server_mod.drama_video_runtime, "create_video_queue", lambda: RecordingQueue())
    monkeypatch.setattr(
        server_mod.drama_video_runtime,
        "create_background_task",
        ImmediateBackgroundTasks().create_task,
    )

    client = TestClient(server_mod.app)
    response = client.post(
        f"/api/drama-video/run/{run.id}/retry",
        json={"shot_id": "shot_1", "confirm_cost": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["run_id"] == run.id
    assert data["retry_job_id"] in enqueued
    assert server_mod.workspace_repo.get_drama_video_job(data["retry_job_id"]).status == "queued"


def test_drama_video_retry_records_estimated_cost(monkeypatch, tmp_path):
    package_dir = tmp_path / "budget_retry_estimate_package"
    package_dir.mkdir()
    (package_dir / "镜头表.json").write_text("[]", encoding="utf-8")
    jobs_path = package_dir / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-failed",
        shot_id="shot_1",
        status="FAILED",
        error="quota exceeded",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_retry_cost_estimate",
            story_path="预算主题/小说正文.md",
            project_id="project_retry_estimate",
            shot_limit=1,
            status="failed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(package_dir),
        )
    )

    class ImmediateBackgroundTasks:
        def create_task(self, coro):
            coro.close()
            return "scheduled"

    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1.25")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "2")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    monkeypatch.setattr(
        server_mod.drama_video_runtime,
        "create_background_task",
        ImmediateBackgroundTasks().create_task,
    )

    client = TestClient(server_mod.app)
    response = client.post(
        f"/api/drama-video/run/{run.id}/retry",
        json={"shot_id": "shot_1", "confirm_cost": True},
    )

    assert response.status_code == 200
    data = response.json()
    entries = [
        entry
        for entry in server_mod.workspace_repo.list_cost_ledger_entries(project_id="project_retry_estimate")
        if entry.id == f"cost_video_retry_estimate_{data['retry_job_id']}"
    ]
    assert len(entries) == 1
    assert entries[0].id == f"cost_video_retry_estimate_{data['retry_job_id']}"
    assert entries[0].source == "video_retry_estimate"
    assert entries[0].amount_cny == 1.25
    assert entries[0].estimated is True
    assert entries[0].run_id == run.id
    assert entries[0].release_id == f"video_retry_{data['retry_job_id']}"
    assert entries[0].package_id == f"{run.id}:shot_1"
    assert entries[0].metadata["retry_job_id"] == data["retry_job_id"]
    assert entries[0].metadata["shot_id"] == "shot_1"
    assert entries[0].metadata["estimate"]["estimated_total_cny"] == 1.25


def test_drama_video_refresh_does_not_require_cost_confirmation(monkeypatch, tmp_path):
    jobs_path = tmp_path / "budget_refresh_package" / "video_jobs.jsonl"
    store = VideoJobStore(jobs_path)
    store.append(VideoJob(provider="bailian", provider_job_id="task-1", shot_id="shot_1", status="PENDING"))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_refresh_budget_guard",
            story_path="预算主题/小说正文.md",
            shot_limit=1,
            status="completed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(jobs_path.parent),
        )
    )

    class StubProvider:
        def get_job(self, provider_job_id, shot_id=""):
            return VideoJob(
                provider="bailian",
                provider_job_id=provider_job_id,
                shot_id=shot_id,
                status="SUCCEEDED",
                video_url="https://example.com/video.mp4",
            )

    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "0")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")
    monkeypatch.setattr(server_mod, "create_video_provider", lambda: StubProvider())

    client = TestClient(server_mod.app)
    response = client.post(f"/api/drama-video/run/{run.id}/refresh")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_drama_video_runs_api_returns_story_run_history(tmp_path):
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    store = VideoJobStore(jobs_path)
    store.append(VideoJob(
        provider="bailian",
        provider_job_id="task-1",
        shot_id="shot_1",
        status="SUCCEEDED",
        video_url="https://example.com/video.mp4",
    ))
    run = server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_history",
            story_path="历史主题/小说正文.md",
            shot_limit=1,
            status="completed",
            submitted_count=1,
            jobs_path=str(jobs_path),
            package_dir=str(jobs_path.parent),
        )
    )
    server_mod.workspace_repo.save_drama_video_run(
        DramaVideoRun(
            id="video_other_story",
            story_path="其他主题/小说正文.md",
            shot_limit=1,
            status="queued",
        )
    )

    client = TestClient(server_mod.app)
    response = client.get("/api/drama-video/runs", params={"story_path": "历史主题/小说正文.md"})

    assert response.status_code == 200
    data = response.json()
    assert data["story_path"] == "历史主题/小说正文.md"
    assert data["latest"]["run"]["id"] == run.id
    assert data["latest"]["summary"] == {"SUCCEEDED": 1}
    assert data["latest"]["jobs"][0]["video_url"] == "https://example.com/video.mp4"
    assert [item["run"]["id"] for item in data["runs"]] == ["video_history"]


def test_drama_video_latest_deepagent_session_returns_story_session():
    server_mod.workspace_repo.save_drama_session(
        DramaProjectSession(
            id="deepagent_old",
            story_path="历史主题/小说正文.md",
            shot_limit=1,
            drafts={"script": "old script"},
            pending_stage="script",
            status="awaiting_confirmation",
            updated_at="2026-06-10T00:00:00+00:00",
        )
    )
    latest = server_mod.workspace_repo.save_drama_session(
        DramaProjectSession(
            id="deepagent_latest",
            story_path="历史主题/小说正文.md",
            shot_limit=2,
            stage_drafts={"script": "confirmed script"},
            drafts={"style": "style draft"},
            confirmed_stages=["script"],
            pending_stage="style",
            status="awaiting_confirmation",
            updated_at="2026-06-12T00:00:00+00:00",
        )
    )
    server_mod.workspace_repo.save_drama_session(
        DramaProjectSession(
            id="deepagent_other",
            story_path="其他主题/小说正文.md",
            shot_limit=1,
            status="awaiting_confirmation",
            updated_at="2026-06-13T00:00:00+00:00",
        )
    )

    client = TestClient(server_mod.app)
    response = client.get(
        "/api/drama-video/deepagent/latest",
        params={"story_path": "历史主题/小说正文.md"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session"]["id"] == latest.id
    assert data["session"]["pending_stage"] == "style"
    assert data["session"]["drafts"]["style"] == "style draft"
    assert data["next_stage"] == "style"


def test_drama_video_deepagent_loop_starts_and_generates_first_checkpoint(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")

    def fake_generate(story_path, stage, stage_drafts):
        return {
            "stage": stage,
            "label": server_mod._VIDEO_STAGE_DRAFT_LABELS[stage],
            "model": "deepseek-v4-pro",
            "content": f"{stage} draft",
            "events": [],
        }

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "_generate_video_stage_draft", fake_generate)

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/deepagent/loop",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2, "project_id": "project_1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_confirmation"
    assert data["stage"] == "script"
    assert data["content"] == "script draft"
    session = server_mod.workspace_repo.get_drama_session(data["run_id"])
    assert session.pending_stage == "script"
    assert session.project_id == "project_1"
    assert session.drafts["script"] == "script draft"
    versions = server_mod.workspace_repo.list_drama_stage_versions(data["run_id"])
    assert versions[0].project_id == "project_1"


def test_drama_video_deepagent_advances_after_stage_confirmation(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    captured_contexts = []

    def fake_generate(story_path, stage, stage_drafts):
        captured_contexts.append((story_path, stage, dict(stage_drafts)))
        return {
            "status": "ok",
            "stage": stage,
            "label": server_mod._VIDEO_STAGE_DRAFT_LABELS[stage],
            "model": "deepseek-v4-pro",
            "content": f"{stage} draft",
        }

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "_generate_video_stage_draft", fake_generate)

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2},
    )

    assert started.status_code == 200
    run_id = started.json()["run_id"]

    first = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
    assert first.status_code == 200
    assert first.json()["stage"] == "script"
    assert first.json()["status"] == "awaiting_confirmation"
    assert first.json()["agent"] == "deepagent"

    repeated = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
    assert repeated.status_code == 200
    assert repeated.json()["stage"] == "script"
    assert repeated.json()["content"] == "script draft"

    confirmed = client.post(
        "/api/drama-video/deepagent/confirm",
        json={"run_id": run_id, "stage": "script", "content": "confirmed script"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["next_stage"] == "style"

    second = client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
    assert second.status_code == 200
    assert second.json()["stage"] == "style"
    assert captured_contexts == [
        ("测试主题/小说正文.md", "script", {}),
        ("测试主题/小说正文.md", "style", {"script": "confirmed script"}),
    ]

    persisted = server_mod.workspace_repo.get_drama_session(run_id)
    assert persisted.story_path == "测试主题/小说正文.md"
    assert persisted.stage_drafts == {"script": "confirmed script"}
    assert persisted.confirmed_stages == ["script"]
    versions = server_mod.workspace_repo.list_drama_stage_versions(run_id)
    assert [(version.stage, version.event, version.content) for version in versions] == [
        ("script", "draft", "script draft"),
        ("script", "confirmation", "confirmed script"),
        ("style", "draft", "style draft"),
    ]


def test_drama_video_deepagent_background_advance_returns_without_blocking(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    called = {"generate": 0, "scheduled": 0}

    def blocking_generate(story_path, stage, stage_drafts):
        called["generate"] += 1
        raise AssertionError("background advance must not generate in request thread")

    class ImmediateBackgroundTasks:
        def create_task(self, coro):
            called["scheduled"] += 1
            coro.close()

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "_generate_video_stage_draft", blocking_generate)
    monkeypatch.setattr(server_mod.asyncio, "create_task", ImmediateBackgroundTasks().create_task)

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2},
    )
    run_id = started.json()["run_id"]

    response = client.post(
        "/api/drama-video/deepagent/advance",
        json={"run_id": run_id, "background": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "generating"
    assert data["stage"] == "script"
    assert data["poll_url"] == f"/api/drama-video/deepagent/{run_id}"
    assert called == {"generate": 0, "scheduled": 1}
    persisted = server_mod.workspace_repo.get_drama_session(run_id)
    assert persisted.status == "generating"
    assert persisted.pending_stage == "script"


def test_drama_video_deepagent_revises_stage_with_human_feedback(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    captured = {}

    def fake_create_llm(incoming_settings, temperature=0.3):
        captured["temperature"] = temperature
        return object()

    def fake_create_drama_video_coordinator(llm, stage):
        captured["coordinator_stage"] = stage
        return object()

    def fake_run_drama_video_coordinator(
        coordinator,
        *,
        result,
        stage,
        stage_drafts,
        current_draft="",
        human_feedback="",
        stream_callback=None,
    ):
        captured["stage"] = stage
        captured["stage_drafts"] = dict(stage_drafts)
        captured["current_draft"] = current_draft
        captured["human_feedback"] = human_feedback
        return {
            "content": "调整后剧本：开场更强，冲突提前。",
            "events": [{"type": "ai_text", "content": "已根据反馈调整"}],
        }

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "create_llm", fake_create_llm)
    monkeypatch.setattr(server_mod, "create_drama_video_coordinator", fake_create_drama_video_coordinator)
    monkeypatch.setattr(server_mod, "run_drama_video_coordinator", fake_run_drama_video_coordinator)

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2},
    )
    run_id = started.json()["run_id"]

    response = client.post(
        "/api/drama-video/deepagent/revise",
        json={
            "run_id": run_id,
            "stage": "script",
            "current_draft": "原剧本：铺垫太长。",
            "feedback": "开场必须更短，前 10 秒给出冲突。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_confirmation"
    assert data["stage"] == "script"
    assert data["agent"] == "deepagent"
    assert data["content"] == "调整后剧本：开场更强，冲突提前。"
    assert captured["temperature"] == 0.4
    assert captured["coordinator_stage"] == "script"
    assert captured["stage_drafts"] == {}
    assert captured["current_draft"] == "原剧本：铺垫太长。"
    assert captured["human_feedback"] == "开场必须更短，前 10 秒给出冲突。"

    versions = server_mod.workspace_repo.list_drama_stage_versions(run_id)
    assert versions[-1].event == "revision"
    assert versions[-1].stage == "script"
    assert versions[-1].human_feedback == "开场必须更短，前 10 秒给出冲突。"


def test_drama_video_deepagent_starts_video_after_storyboard_confirmation(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 3, "project_id": "project_1"},
    )

    assert started.status_code == 200
    run_id = started.json()["run_id"]
    for stage in ("script", "style", "plot", "character_refs"):
        confirmed = client.post(
            "/api/drama-video/deepagent/confirm",
            json={"run_id": run_id, "stage": stage, "content": f"{stage} confirmed"},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "ready_for_next_stage"

    final = client.post(
        "/api/drama-video/deepagent/confirm",
        json={"run_id": run_id, "stage": "storyboard", "content": "storyboard confirmed"},
    )

    assert final.status_code == 200
    data = final.json()
    assert data["status"] == "video_started"
    assert data["stage"] == "video"
    assert data["video_run_id"].startswith("video_")
    assert data["stream_url"] == f"/api/drama-video/stream/{data['video_run_id']}"
    assert server_mod._video_specs[data["video_run_id"]]["shot_limit"] == 3
    assert server_mod._video_specs[data["video_run_id"]]["stage_drafts"] == {
        "script": "script confirmed",
        "style": "style confirmed",
        "plot": "plot confirmed",
        "character_refs": "character_refs confirmed",
        "storyboard": "storyboard confirmed",
    }
    persisted_video = server_mod.workspace_repo.get_drama_video_run(data["video_run_id"])
    assert persisted_video.status == "queued"
    assert persisted_video.project_id == "project_1"
    assert persisted_video.shot_limit == 3
    assert persisted_video.stage_drafts == server_mod._video_specs[data["video_run_id"]]["stage_drafts"]


def test_drama_video_deepagent_storyboard_confirmation_requires_cost_confirmation(monkeypatch, tmp_path):
    story_dir = tmp_path / "deepagent预算主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# deepagent预算主题\n\n正文", encoding="utf-8")

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "1")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "deepagent预算主题/小说正文.md", "shot_limit": 3, "project_id": "project_budget"},
    )
    assert started.status_code == 200
    run_id = started.json()["run_id"]
    for stage in ("script", "style", "plot", "character_refs"):
        confirmed = client.post(
            "/api/drama-video/deepagent/confirm",
            json={"run_id": run_id, "stage": stage, "content": f"{stage} confirmed"},
        )
        assert confirmed.status_code == 200

    run_ids_before = {run.id for run in server_mod.workspace_repo.list_drama_video_runs()}
    blocked = client.post(
        "/api/drama-video/deepagent/confirm",
        json={"run_id": run_id, "stage": "storyboard", "content": "storyboard confirmed"},
    )

    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["message"] == "video generation budget requires confirmation"
    assert detail["requires_confirmation"] is True
    assert detail["cost_guardrail"]["estimate"]["shot_count"] == 3
    assert detail["cost_guardrail"]["within_budget"] is False
    session = server_mod.workspace_repo.get_drama_session(run_id)
    assert session.status == "ready_for_next_stage"
    assert "storyboard" not in session.stage_drafts
    assert {run.id for run in server_mod.workspace_repo.list_drama_video_runs()} == run_ids_before

    confirmed = client.post(
        "/api/drama-video/deepagent/confirm",
        json={
            "run_id": run_id,
            "stage": "storyboard",
            "content": "storyboard confirmed",
            "confirm_cost": True,
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "video_started"
    video_run = server_mod.workspace_repo.get_drama_video_run(confirmed.json()["video_run_id"])
    assert video_run.project_id == "project_budget"
    assert video_run.shot_limit == 3


def test_drama_video_deepagent_storyboard_confirmation_validates_content_before_cost(monkeypatch, tmp_path):
    story_dir = tmp_path / "deepagent空分镜主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# deepagent空分镜主题\n\n正文", encoding="utf-8")

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1")
    monkeypatch.setenv("ZH_DAILY_BUDGET_CNY", "0")
    monkeypatch.setenv("ZH_TODAY_SPEND_CNY", "0")

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "deepagent空分镜主题/小说正文.md", "shot_limit": 3},
    )
    run_id = started.json()["run_id"]
    for stage in ("script", "style", "plot", "character_refs"):
        confirmed = client.post(
            "/api/drama-video/deepagent/confirm",
            json={"run_id": run_id, "stage": stage, "content": f"{stage} confirmed"},
        )
        assert confirmed.status_code == 200

    response = client.post(
        "/api/drama-video/deepagent/confirm",
        json={"run_id": run_id, "stage": "storyboard", "content": ""},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "content is required"


def test_drama_video_deepagent_session_and_versions_api(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")

    def fake_generate(story_path, stage, stage_drafts):
        return {
            "status": "ok",
            "stage": stage,
            "label": server_mod._VIDEO_STAGE_DRAFT_LABELS[stage],
            "model": "deepseek-v4-pro",
            "content": f"{stage} draft",
        }

    def fake_revise(story_path, stage, stage_drafts, current_draft="", human_feedback=""):
        return {
            "status": "ok",
            "stage": stage,
            "label": server_mod._VIDEO_STAGE_DRAFT_LABELS[stage],
            "model": "deepseek-v4-pro",
            "agent": "deepagent",
            "content": f"{stage} revised",
            "events": [],
        }

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "_generate_video_stage_draft", fake_generate)
    monkeypatch.setattr(server_mod, "_run_video_stage_deepagent", fake_revise)

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2},
    )
    run_id = started.json()["run_id"]
    client.post("/api/drama-video/deepagent/advance", json={"run_id": run_id})
    client.post(
        "/api/drama-video/deepagent/revise",
        json={
            "run_id": run_id,
            "stage": "script",
            "current_draft": "script draft",
            "feedback": "更强冲突",
        },
    )

    session = client.get(f"/api/drama-video/deepagent/{run_id}")
    versions = client.get(f"/api/drama-video/deepagent/{run_id}/versions")

    assert session.status_code == 200
    assert session.json()["session"]["id"] == run_id
    assert session.json()["session"]["pending_stage"] == "script"
    assert versions.status_code == 200
    assert [item["event"] for item in versions.json()["versions"]] == ["draft", "revision"]
    assert versions.json()["versions"][-1]["human_feedback"] == "更强冲突"


def test_drama_video_deepagent_retry_failed_stage_endpoint(monkeypatch, tmp_path):
    story_dir = tmp_path / "失败重试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 失败重试主题\n\n正文", encoding="utf-8")

    def fake_generate(story_path, stage, stage_drafts):
        return {
            "status": "ok",
            "stage": stage,
            "label": server_mod._VIDEO_STAGE_DRAFT_LABELS[stage],
            "model": "deepseek-v4-pro",
            "content": f"{stage} retried draft",
            "events": [{"type": "ai_text", "content": "retry"}],
        }

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "_generate_video_stage_draft", fake_generate)
    server_mod.workspace_repo.save_drama_session(
        DramaProjectSession(
            id="deepagent_failed",
            story_path="失败重试主题/小说正文.md",
            project_id="project_1",
            shot_limit=2,
            stage_drafts={"script": "confirmed script"},
            drafts={"style": "failed style draft"},
            confirmed_stages=["script"],
            pending_stage="style",
            status="failed",
            error="model timeout",
        )
    )

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/deepagent/retry",
        json={"run_id": "deepagent_failed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_confirmation"
    assert data["stage"] == "style"
    assert data["content"] == "style retried draft"
    session = server_mod.workspace_repo.get_drama_session("deepagent_failed")
    assert session.status == "awaiting_confirmation"
    assert session.pending_stage == "style"
    assert session.error == ""
    assert session.confirmed_stages == ["script"]
    assert server_mod.workspace_repo.list_drama_stage_versions("deepagent_failed")[-1].event == "restore"


def test_drama_video_deepagent_retry_rejects_non_failed_session(tmp_path):
    server_mod.workspace_repo.save_drama_session(
        DramaProjectSession(
            id="deepagent_waiting",
            story_path="故事/小说正文.md",
            drafts={"script": "draft"},
            pending_stage="script",
            status="awaiting_confirmation",
        )
    )

    client = TestClient(server_mod.app)
    response = client.post(
        "/api/drama-video/deepagent/retry",
        json={"run_id": "deepagent_waiting"},
    )

    assert response.status_code == 409
    assert "只有失败" in response.json()["detail"]


def test_drama_video_project_package_export_persists_asset(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setattr(server_mod, "OUTPUT_DIR", tmp_path)

    client = TestClient(server_mod.app)
    started = client.post(
        "/api/drama-video/deepagent/run",
        json={"story_path": "测试主题/小说正文.md", "shot_limit": 2},
    )
    run_id = started.json()["run_id"]
    client.post(
        "/api/drama-video/deepagent/confirm",
        json={"run_id": run_id, "stage": "script", "content": "confirmed script"},
    )

    exported = client.post("/api/drama-video/package/export", json={"run_id": run_id})

    assert exported.status_code == 200
    data = exported.json()
    assert data["package"]["run_id"] == run_id
    assert data["package"]["package_uri"].startswith("local://drama-projects/")
    assert data["asset"]["content_type"] == "application/json"
    stored_path = tmp_path / "data" / "workspace" / "assets" / data["asset"]["key"]
    payload = stored_path.read_text(encoding="utf-8")
    assert '"confirmed script"' in payload


def test_video_page_serves_standalone_video_workspace():
    client = TestClient(server_mod.app)

    response = client.get("/video")

    assert response.status_code == 200
    assert "短剧视频生产" in response.text
    assert "startDramaVideoRun" in response.text
    assert "videoStageLog" in response.text
    assert "openVideoWorkspace" in response.text
    assert "workspaceOpen" in response.text
    assert "workspaceRestoreStatus" in response.text
    assert "workspaceRestoring" in response.text
    assert "workspaceActionHint" in response.text
    assert "stageHasDraft" in response.text
    assert "currentStagePlaceholder" in response.text
    assert "activeStage" in response.text
    assert "confirmedStageDrafts" in response.text
    assert "readyForVideoStages" in response.text
    assert "startDeepAgentRun" in response.text
    assert "startDeepAgentLoop" in response.text
    assert "advanceDeepAgent" in response.text
    assert "background: true" in response.text
    assert "startDeepAgentPolling" in response.text
    assert "pollDeepAgentSession" in response.text
    assert "stopDeepAgentPolling" in response.text
    assert "DeepAgent 自动生产" in response.text
    assert "打开作品后会自动恢复最近会话" in response.text
    assert "当前阶段没有草稿" in response.text
    assert "准备就绪" in response.text
    assert "正在恢复工作台" in response.text
    assert "Promise.allSettled" in response.text
    assert "一键生成短剧流程" in response.text
    assert "/api/drama-video/deepagent/run" in response.text
    assert "/api/drama-video/deepagent/loop" in response.text
    assert "/api/drama-video/deepagent/advance" in response.text
    assert "/api/drama-video/deepagent/confirm" in response.text
    assert "/api/drama-video/deepagent/revise" in response.text
    assert "human-loop-chat" in response.text
    assert "humanLoopMessages" in response.text
    assert "sendHumanLoopFeedback" in response.text
    assert "workspace-human-loop-dialog" in response.text
    assert "workspaceHumanLoopPrompt" in response.text
    assert "sendWorkspaceHumanLoopPrompt" in response.text
    assert "Human Loop" in response.text
    assert "人类反馈" in response.text
    assert "Agent 输出" in response.text
    assert "backend-status" in response.text
    assert "loadInfrastructureStatus" in response.text
    assert "version-history" in response.text
    assert "loadDeepAgentVersions" in response.text
    assert "exportDramaProjectPackage" in response.text
    assert "refreshVideoRunJobs" in response.text
    assert "retryVideoRunJob" in response.text
    assert "retryingJobId" in response.text
    assert "videoRetryJobs" in response.text
    assert "loadVideoRetryJob" in response.text
    assert "canRetryVideoJob" in response.text
    assert "refreshingJobs" in response.text
    assert "videoJobSummary" in response.text
    assert "state_summary?.normalized" in response.text
    assert "normalized_status" in response.text
    assert "videoRunHistory" in response.text
    assert "loadingVideoRuns" in response.text
    assert "selectedVideoRunId" in response.text
    assert "loadVideoRunHistory" in response.text
    assert "applyVideoRunHistory" in response.text
    assert "selectVideoRunHistory" in response.text
    assert "videoRunLabel" in response.text
    assert "restoreLatestDeepAgentSession" in response.text
    assert "/api/drama-video/deepagent/latest" in response.text
    assert "/api/drama-video/infrastructure" in response.text
    assert "/api/drama-video/package/export" in response.text
    assert "/api/drama-video/deepagent/" in response.text
    assert "/api/drama-video/runs" in response.text
    assert "/refresh" in response.text
    assert "/retry" in response.text
    assert "/api/drama-video/retry/" in response.text
    assert "重试镜头" in response.text
    assert "镜头重试已入队" in response.text
    assert "镜头重试" in response.text
    assert "历史视频任务" in response.text
    assert "选择历史任务" in response.text
    assert "当前任务" in response.text
    assert "已恢复最近一次视频任务" in response.text
    assert "视频状态刷新" in response.text
    assert "刷新状态" in response.text
    assert "job.video_url" in response.text
    assert "job.error" in response.text
    assert "单作品短剧工作台" not in response.text
    assert "确认本阶段" in response.text
    assert "generateActiveStageDraft" in response.text
    assert "/api/drama-video/stage" in response.text
    assert "DeepSeek V4 Pro 创作" in response.text
    assert "进入短剧工作台" in response.text
    assert "返回作品库" in response.text
    for stage in ("script", "style", "plot", "character_refs", "storyboard", "video"):
        assert stage in response.text
    assert "production-timeline" in response.text
    assert "shot-board" in response.text
    assert "cost-guardrail" in response.text
    assert "model-settings" in response.text
    assert "镜头提交队列" in response.text
    assert "生成过程" in response.text
    assert "/api/drama-video/run" in response.text
    assert "/api/drama-video/stream/" in response.text
    assert "/api/drama-video" in response.text


def test_video_page_contains_unified_job_timeline_controls():
    client = TestClient(server_mod.app)

    response = client.get("/video")

    assert response.status_code == 200
    assert "loadVideoRunJobs" in response.text
    assert "/api/drama-video/jobs" in response.text
    assert "videoJobs" in response.text
    assert "任务时间线" in response.text


def test_main_workspace_does_not_embed_video_submission_controls():
    client = TestClient(server_mod.app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/video"' in response.text
    assert "submitDramaVideo" not in response.text
    assert "生成视频任务" not in response.text


def test_drama_video_recovery_endpoint_reports_attention_items(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_waiting",
        project_id="project_1",
        story_path="story.md",
        status="awaiting_confirmation",
        pending_stage="script",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/drama-video/recovery")

    assert response.status_code == 200
    assert response.json()["needs_attention_count"] == 1
    assert response.json()["awaiting_confirmation_sessions"][0]["id"] == "deepagent_waiting"


def test_deepagent_trace_endpoint_returns_empty_events_without_store(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/drama-video/deepagent/run_missing/trace")

    assert response.status_code == 200
    assert response.json() == {"run_id": "run_missing", "events": []}


def test_deepagent_trace_endpoint_returns_serialized_store_events(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = AppDependencies(workspace_repo=repo)
    deps.agent_trace_store = AgentTraceStore(tmp_path / "traces")
    deps.agent_trace_store.append(
        AgentTraceEvent(
            run_id="run_1",
            node_id="drama.script",
            stage="script",
            event="human_confirmed",
            metadata={"version_id": "version_1"},
        )
    )
    client = TestClient(create_app(dependencies=deps))

    response = client.get("/api/drama-video/deepagent/run_1/trace")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run_1"
    assert len(data["events"]) == 1
    assert data["events"][0]["event"] == "human_confirmed"
    assert data["events"][0]["node_id"] == "drama.script"
    assert data["events"][0]["metadata"] == {"version_id": "version_1"}

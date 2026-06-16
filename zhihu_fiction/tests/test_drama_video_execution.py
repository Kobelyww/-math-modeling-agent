"""Tests for short-drama video execution service."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from zhihu_fiction.app.services.drama_video_execution import (
    create_video_tasks_payload,
    execute_video_run_in_background,
    execute_video_retry_job,
    ensure_video_run_estimated_cost,
    list_video_runs_for_story,
    normalize_provider_video_status,
    provider_job_actual_cost_cny,
    refresh_video_run_jobs,
    retry_video_run_job,
    start_video_run_spec,
    summarize_video_job_states,
)
from zhihu_fiction.app.state import AppState
from zhihu_fiction.drama.models import (
    DramaCharacter,
    DramaEpisode,
    DramaLocation,
    DramaProject,
    DramaShot,
)
from zhihu_fiction.workspace.repositories import WorkspaceRepository
from zhihu_fiction.workspace.models import DramaVideoRun, Project, Story
from zhihu_fiction.drama.video import VideoJob, VideoJobStore


def test_start_video_run_spec_initializes_queue_and_spec(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    state = AppState()

    run_id = start_video_run_spec(
        state,
        "测试主题/小说正文.md",
        3,
        {"script": "确认剧本"},
        id_factory=lambda prefix: "video_fixed",
    )

    assert run_id == "video_fixed"
    assert run_id in state.video_events
    assert state.video_progress[run_id] == {"status": "starting"}
    assert state.video_specs[run_id] == {
        "story_path": "测试主题/小说正文.md",
        "shot_limit": 3,
        "stage_drafts": {"script": "确认剧本"},
        "project_id": "",
        "started": False,
    }


def test_start_video_run_spec_persists_video_run(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()

    run_id = start_video_run_spec(
        state,
        "测试主题/小说正文.md",
        2,
        {"script": "确认剧本"},
        dependencies=deps,
        project_id="project_1",
        id_factory=lambda prefix: "video_fixed",
    )

    stored = repo.get_drama_video_run(run_id)
    assert stored.id == "video_fixed"
    assert stored.status == "queued"
    assert stored.story_path == "测试主题/小说正文.md"
    assert stored.shot_limit == 2
    assert stored.stage_drafts == {"script": "确认剧本"}

    job = repo.get_drama_video_job(run_id)
    assert job.id == "video_fixed"
    assert job.kind == "generate_video"
    assert job.run_id == "video_fixed"
    assert job.status == "queued"
    assert job.payload == {
        "story_path": "测试主题/小说正文.md",
        "shot_limit": 2,
        "stage_drafts": {"script": "确认剧本"},
        "project_id": "project_1",
    }
    assert stored.project_id == "project_1"
    assert job.result == {}
    assert job.error == ""


def test_start_video_run_spec_records_estimated_cost_once(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1.5")
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()

    run_id = start_video_run_spec(
        state,
        "测试主题/小说正文.md",
        2,
        {"script": "确认剧本"},
        dependencies=deps,
        project_id="project_1",
        id_factory=lambda prefix: "video_estimate_once",
    )
    ensure_video_run_estimated_cost(deps, repo.get_drama_video_run(run_id))

    entries = repo.list_cost_ledger_entries(project_id="project_1")
    assert len(entries) == 1
    assert entries[0].id == "cost_video_run_estimate_video_estimate_once"
    assert entries[0].source == "video_run_estimate"
    assert entries[0].amount_cny == 3.0
    assert entries[0].estimated is True
    assert entries[0].run_id == run_id
    assert entries[0].release_id == f"video_run_{run_id}"
    assert entries[0].package_id == f"video_run_{run_id}"
    assert entries[0].metadata == {
        "billable_stage": "video",
        "estimate": {
            "currency": "CNY",
            "shot_count": 2,
            "seconds_per_shot": 6,
            "estimated_seconds": 12,
            "unit_price_cny": 1.5,
            "estimated_total_cny": 3.0,
        },
        "story_path": "测试主题/小说正文.md",
    }


def test_video_run_estimated_cost_skips_runs_without_project(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    monkeypatch.setenv("ZH_VIDEO_UNIT_PRICE_CNY", "1.5")
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()

    run_id = start_video_run_spec(
        state,
        "测试主题/小说正文.md",
        2,
        {},
        dependencies=deps,
        id_factory=lambda prefix: "video_no_project",
    )

    assert ensure_video_run_estimated_cost(deps, repo.get_drama_video_run(run_id)) is None
    assert repo.list_cost_ledger_entries() == []


def test_execute_video_run_in_background_updates_persisted_status(monkeypatch, tmp_path):
    story_dir = tmp_path / "故事"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 故事\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()
    run_id = start_video_run_spec(
        state,
        "故事/小说正文.md",
        2,
        {"script": "确认剧本"},
        dependencies=deps,
        id_factory=lambda prefix: "video_1",
    )

    async def run_once():
        await execute_video_run_in_background(
            deps,
            state,
            run_id,
            "故事/小说正文.md",
            2,
            stage_drafts={"script": "确认剧本"},
            payload_factory=lambda *args, **kwargs: {
                "story_path": "故事/小说正文.md",
                "package_dir": "/tmp/package",
                "jobs_path": "/tmp/package/video_jobs.jsonl",
                "submitted_count": 2,
                "shot_limit": 2,
                "jobs": [],
            },
        )

    __import__("asyncio").run(run_once())

    stored = repo.get_drama_video_run("video_1")
    assert stored.status == "completed"
    assert stored.submitted_count == 2
    assert stored.package_dir == "/tmp/package"
    assert stored.jobs_path == "/tmp/package/video_jobs.jsonl"

    job = repo.get_drama_video_job("video_1")
    assert job.status == "completed"
    assert job.error == ""
    assert job.result["jobs_path"] == "/tmp/package/video_jobs.jsonl"
    assert job.result["package_dir"] == "/tmp/package"
    assert job.result["submitted_count"] == 2


def test_execute_video_run_in_background_registers_video_assets_for_project(monkeypatch, tmp_path):
    story_dir = tmp_path / "故事"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 故事\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="故事"))
    repo.save_story(Story(
        id="story_1",
        project_id="project_1",
        title="故事",
        body_path="故事/小说正文.md",
    ))
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()
    run_id = start_video_run_spec(
        state,
        "故事/小说正文.md",
        1,
        {},
        dependencies=deps,
        id_factory=lambda prefix: "video_1",
    )

    async def run_once():
        await execute_video_run_in_background(
            deps,
            state,
            run_id,
            "故事/小说正文.md",
            1,
            payload_factory=lambda *args, **kwargs: {
                "story_path": "故事/小说正文.md",
                "package_dir": "/tmp/package",
                "jobs_path": "/tmp/package/video_jobs.jsonl",
                "submitted_count": 1,
                "shot_limit": 1,
                "jobs": [{
                    "provider": "bailian",
                    "provider_job_id": "task-1",
                    "shot_id": "shot_1",
                    "status": "SUCCEEDED",
                    "video_url": "https://example.com/shot_1.mp4",
                }],
            },
        )

    __import__("asyncio").run(run_once())

    assets = repo.list_video_assets("project_1")
    assert len(assets) == 1
    assert assets[0].run_id == "video_1"
    assert assets[0].kind == "video"
    assert assets[0].uri == "https://example.com/shot_1.mp4"
    assert assets[0].provider == "bailian"
    assert assets[0].shot_id == "shot_1"


def test_execute_video_run_in_background_registers_assets_from_run_project_id(monkeypatch, tmp_path):
    story_dir = tmp_path / "故事"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 故事\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_project(Project(id="project_1", title="故事"))
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()
    run_id = start_video_run_spec(
        state,
        "故事/小说正文.md",
        1,
        {},
        dependencies=deps,
        project_id="project_1",
        id_factory=lambda prefix: "video_1",
    )

    async def run_once():
        await execute_video_run_in_background(
            deps,
            state,
            run_id,
            "故事/小说正文.md",
            1,
            payload_factory=lambda *args, **kwargs: {
                "story_path": "故事/小说正文.md",
                "package_dir": "/tmp/package",
                "jobs_path": "/tmp/package/video_jobs.jsonl",
                "submitted_count": 1,
                "shot_limit": 1,
                "jobs": [{
                    "provider": "bailian",
                    "provider_job_id": "task-1",
                    "shot_id": "shot_1",
                    "status": "SUCCEEDED",
                    "video_url": "https://example.com/shot_1.mp4",
                }],
            },
        )

    __import__("asyncio").run(run_once())

    assert repo.get_drama_video_run(run_id).project_id == "project_1"
    assets = repo.list_video_assets("project_1")
    assert len(assets) == 1
    assert assets[0].uri == "https://example.com/shot_1.mp4"


def test_execute_video_run_in_background_marks_generate_job_failed(monkeypatch, tmp_path):
    story_dir = tmp_path / "故事"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 故事\n\n正文", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = SimpleNamespace(workspace_repo=repo)
    state = AppState()
    run_id = start_video_run_spec(
        state,
        "故事/小说正文.md",
        2,
        {"script": "确认剧本"},
        dependencies=deps,
        id_factory=lambda prefix: "video_1",
    )

    def fail_payload_factory(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    async def run_once():
        await execute_video_run_in_background(
            deps,
            state,
            run_id,
            "故事/小说正文.md",
            2,
            stage_drafts={"script": "确认剧本"},
            payload_factory=fail_payload_factory,
        )

    __import__("asyncio").run(run_once())

    stored = repo.get_drama_video_run("video_1")
    assert stored.status == "failed"
    assert stored.error == "provider unavailable"
    job = repo.get_drama_video_job("video_1")
    assert job.status == "failed"
    assert job.error == "provider unavailable"


def test_normalize_provider_video_status_maps_bailian_states():
    assert normalize_provider_video_status("PENDING") == "polling"
    assert normalize_provider_video_status("RUNNING") == "polling"
    assert normalize_provider_video_status("SUCCEEDED") == "succeeded"
    assert normalize_provider_video_status("FAILED") == "failed"
    assert normalize_provider_video_status("CANCELED") == "canceled"
    assert normalize_provider_video_status("") == "unknown"


def test_summarize_video_job_states_includes_raw_and_normalized_counts():
    jobs = [
        VideoJob(provider="bailian", provider_job_id="task-1", shot_id="shot_1", status="PENDING"),
        VideoJob(provider="bailian", provider_job_id="task-2", shot_id="shot_2", status="SUCCEEDED"),
        VideoJob(provider="bailian", provider_job_id="task-3", shot_id="shot_3", status="FAILED"),
    ]

    summary = summarize_video_job_states(jobs)

    assert summary["raw"] == {"PENDING": 1, "SUCCEEDED": 1, "FAILED": 1}
    assert summary["normalized"] == {"polling": 1, "succeeded": 1, "failed": 1}
    assert summary["total"] == 3
    assert summary["terminal"] == 2


def test_refresh_video_run_jobs_queries_provider_and_updates_run(tmp_path):
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    store = VideoJobStore(jobs_path)
    store.append(VideoJob(provider="bailian", provider_job_id="task-1", shot_id="shot_1", status="PENDING"))
    store.append(VideoJob(provider="bailian", provider_job_id="task-2", shot_id="shot_2", status="PENDING"))
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_1",
        story_path="故事/小说正文.md",
        shot_limit=2,
        status="completed",
        submitted_count=2,
        jobs_path=str(jobs_path),
        package_dir=str(jobs_path.parent),
    ))

    class StubProvider:
        def get_job(self, provider_job_id, shot_id=""):
            if provider_job_id == "task-1":
                return VideoJob(
                    provider="bailian",
                    provider_job_id=provider_job_id,
                    shot_id=shot_id,
                    status="SUCCEEDED",
                    video_url="https://example.com/shot_1.mp4",
                )
            return VideoJob(
                provider="bailian",
                provider_job_id=provider_job_id,
                shot_id=shot_id,
                status="FAILED",
                error="quota exceeded",
            )

    result = refresh_video_run_jobs(
        SimpleNamespace(workspace_repo=repo),
        "video_1",
        provider_factory=lambda: StubProvider(),
        job_store_cls=VideoJobStore,
    )

    assert result["status"] == "partial_failed"
    assert result["summary"] == {"SUCCEEDED": 1, "FAILED": 1}
    assert result["state_summary"]["normalized"] == {"succeeded": 1, "failed": 1}
    assert result["jobs"][0]["normalized_status"] == "succeeded"
    assert result["jobs"][1]["normalized_status"] == "failed"
    assert [job.status for job in VideoJobStore(jobs_path).list()] == ["SUCCEEDED", "FAILED"]
    stored = repo.get_drama_video_run("video_1")
    assert stored.status == "failed"
    assert stored.error == "1 video job(s) failed"


def test_refresh_video_run_jobs_persists_refresh_job(tmp_path):
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-1",
        shot_id="shot_1",
        status="PENDING",
    ))
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_1",
        story_path="故事/小说正文.md",
        shot_limit=1,
        status="running",
        jobs_path=str(jobs_path),
        package_dir=str(jobs_path.parent),
    ))

    class StubProvider:
        def get_job(self, provider_job_id, shot_id=""):
            return VideoJob(
                provider="bailian",
                provider_job_id=provider_job_id,
                shot_id=shot_id,
                status="SUCCEEDED",
                video_url="https://example.com/shot_1.mp4",
            )

    result = refresh_video_run_jobs(
        SimpleNamespace(workspace_repo=repo),
        "video_1",
        provider_factory=lambda: StubProvider(),
        job_store_cls=VideoJobStore,
        job_id_factory=lambda prefix: "refresh_1",
    )

    assert result["status"] == "completed"
    job = repo.get_drama_video_job("refresh_1")
    assert job.kind == "refresh_status"
    assert job.run_id == "video_1"
    assert job.status == "completed"
    assert job.result["summary"] == {"SUCCEEDED": 1}


def test_refresh_video_run_jobs_records_provider_actual_cost_once(tmp_path):
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    VideoJobStore(jobs_path).append(VideoJob(
        provider="bailian",
        provider_job_id="task-1",
        shot_id="shot_1",
        status="PENDING",
    ))
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_1",
        story_path="故事/小说正文.md",
        project_id="project_1",
        shot_limit=1,
        status="running",
        jobs_path=str(jobs_path),
        package_dir=str(jobs_path.parent),
    ))

    class StubProvider:
        def get_job(self, provider_job_id, shot_id=""):
            return VideoJob(
                provider="bailian",
                provider_job_id=provider_job_id,
                shot_id=shot_id,
                status="SUCCEEDED",
                video_url="https://example.com/shot_1.mp4",
                raw_response={
                    "output": {"task_id": provider_job_id, "task_status": "SUCCEEDED"},
                    "billing": {"amount_cny": 2.75},
                },
            )

    deps = SimpleNamespace(workspace_repo=repo)

    first = refresh_video_run_jobs(
        deps,
        "video_1",
        provider_factory=lambda: StubProvider(),
        job_store_cls=VideoJobStore,
        job_id_factory=lambda prefix: "refresh_1",
    )
    second = refresh_video_run_jobs(
        deps,
        "video_1",
        provider_factory=lambda: StubProvider(),
        job_store_cls=VideoJobStore,
        job_id_factory=lambda prefix: "refresh_2",
    )

    entries = repo.list_cost_ledger_entries(project_id="project_1")
    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert len(entries) == 1
    assert entries[0].id == "cost_provider_bailian_task-1"
    assert entries[0].source == "provider_bailian"
    assert entries[0].amount_cny == 2.75
    assert entries[0].estimated is False
    assert entries[0].run_id == "video_1"
    assert entries[0].release_id == "provider_task-1"
    assert entries[0].package_id == "video_1:shot_1"
    assert entries[0].metadata == {
        "provider": "bailian",
        "provider_job_id": "task-1",
        "shot_id": "shot_1",
        "status": "SUCCEEDED",
        "video_url": "https://example.com/shot_1.mp4",
        "billing": {"amount_cny": 2.75},
    }


def test_provider_job_actual_cost_reads_common_provider_shapes():
    assert provider_job_actual_cost_cny(VideoJob(
        provider="bailian",
        provider_job_id="task-1",
        shot_id="shot_1",
        status="SUCCEEDED",
        raw_response={"usage": {"cost_cny": "1.25"}},
    )) == 1.25
    assert provider_job_actual_cost_cny(VideoJob(
        provider="bailian",
        provider_job_id="task-2",
        shot_id="shot_2",
        status="SUCCEEDED",
        raw_response={"cost": {"amount_cny": 2}},
    )) == 2.0
    assert provider_job_actual_cost_cny(VideoJob(
        provider="bailian",
        provider_job_id="task-3",
        shot_id="shot_3",
        status="SUCCEEDED",
    )) == 0.0


def test_retry_video_run_job_resubmits_failed_shot_from_package(tmp_path):
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    shot_table = [
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
            "episode_title": "第一集",
        }
    ]
    (package_dir / "镜头表.json").write_text(
        json.dumps(shot_table, ensure_ascii=False),
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
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_retry",
        story_path="故事/小说正文.md",
        shot_limit=1,
        status="failed",
        submitted_count=1,
        jobs_path=str(jobs_path),
        package_dir=str(package_dir),
        error="1 video job(s) failed",
    ))
    submitted_shots = []

    class StubProvider:
        def submit_shot(self, shot):
            submitted_shots.append(shot)
            return VideoJob(
                provider="bailian",
                provider_job_id="task-retry",
                shot_id=shot.id,
                status="PENDING",
            )

    result = retry_video_run_job(
        SimpleNamespace(workspace_repo=repo),
        "video_retry",
        "shot_1",
        provider_factory=lambda: StubProvider(),
        job_store_cls=VideoJobStore,
    )

    assert result["status"] == "retried"
    assert result["job"]["provider_job_id"] == "task-retry"
    assert result["summary"] == {"PENDING": 1}
    assert [job.provider_job_id for job in VideoJobStore(jobs_path).list()] == ["task-retry"]
    assert submitted_shots[0].id == "shot_1"
    assert submitted_shots[0].visual_prompt == "cinematic room"
    stored = repo.get_drama_video_run("video_retry")
    assert stored.status == "running"
    assert stored.error == ""


def test_execute_video_retry_job_updates_runtime_state(tmp_path):
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
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_retry",
        story_path="故事/小说正文.md",
        shot_limit=1,
        status="failed",
        submitted_count=1,
        jobs_path=str(jobs_path),
        package_dir=str(package_dir),
        error="1 video job(s) failed",
    ))
    state = AppState()
    state.video_retry_jobs["retry_1"] = {
        "id": "retry_1",
        "run_id": "video_retry",
        "shot_id": "shot_1",
        "status": "queued",
    }

    class StubProvider:
        def submit_shot(self, shot):
            return VideoJob(
                provider="bailian",
                provider_job_id="task-retry",
                shot_id=shot.id,
                status="PENDING",
            )

    async def run_once():
        await execute_video_retry_job(
            SimpleNamespace(workspace_repo=repo),
            state,
            "retry_1",
            "video_retry",
            "shot_1",
            provider_factory=lambda: StubProvider(),
            job_store_cls=VideoJobStore,
        )

    __import__("asyncio").run(run_once())

    assert state.video_retry_jobs["retry_1"]["status"] == "completed"
    assert state.video_retry_jobs["retry_1"]["result"]["job"]["provider_job_id"] == "task-retry"
    assert VideoJobStore(jobs_path).list()[0].provider_job_id == "task-retry"


def test_list_video_runs_for_story_returns_runs_with_jobs_and_summary(tmp_path):
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    store = VideoJobStore(jobs_path)
    store.append(VideoJob(
        provider="bailian",
        provider_job_id="task-1",
        shot_id="shot_1",
        status="SUCCEEDED",
        video_url="https://example.com/shot_1.mp4",
    ))
    store.append(VideoJob(
        provider="bailian",
        provider_job_id="task-2",
        shot_id="shot_2",
        status="FAILED",
        error="quota exceeded",
    ))
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_run(DramaVideoRun(
        id="video_new",
        story_path="故事/小说正文.md",
        shot_limit=2,
        status="failed",
        submitted_count=2,
        jobs_path=str(jobs_path),
        package_dir=str(jobs_path.parent),
        updated_at="2026-06-11T10:00:00+00:00",
    ))
    repo.save_drama_video_run(DramaVideoRun(
        id="video_old",
        story_path="故事/小说正文.md",
        shot_limit=1,
        status="queued",
        updated_at="2026-06-10T10:00:00+00:00",
    ))
    repo.save_drama_video_run(DramaVideoRun(
        id="video_other",
        story_path="其他/小说正文.md",
        shot_limit=1,
        status="completed",
        updated_at="2026-06-11T11:00:00+00:00",
    ))

    result = list_video_runs_for_story(
        SimpleNamespace(workspace_repo=repo),
        "故事/小说正文.md",
        job_store_cls=VideoJobStore,
    )

    assert result["story_path"] == "故事/小说正文.md"
    assert [item["run"]["id"] for item in result["runs"]] == ["video_new", "video_old"]
    assert result["latest"]["run"]["id"] == "video_new"
    assert result["latest"]["summary"] == {"SUCCEEDED": 1, "FAILED": 1}
    assert result["latest"]["jobs"][0]["video_url"] == "https://example.com/shot_1.mp4"
    assert result["latest"]["jobs"][1]["error"] == "quota exceeded"


def test_start_video_run_spec_rejects_missing_story(tmp_path, monkeypatch):
    import pytest
    from fastapi import HTTPException
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        start_video_run_spec(AppState(), "missing.md", 1, {})

    assert exc_info.value.status_code == 404


def test_create_video_tasks_payload_submits_selected_shots(monkeypatch, tmp_path):
    story_dir = tmp_path / "测试主题"
    story_dir.mkdir()
    (story_dir / "小说正文.md").write_text("# 测试主题\n\n> 题材：复仇\n\n女主重生反击。", encoding="utf-8")
    import zhihu_fiction.server as server_mod

    monkeypatch.setattr(server_mod, "APP_ROOT", tmp_path)

    shots = [
        DramaShot(
            id=f"shot_{index}",
            episode_index=1,
            scene_index=1,
            shot_index=index,
            duration_seconds=6,
            location_id="room",
            character_ids=["hero"],
            action="反击",
            dialogue="我不会退让。",
            emotion="坚定",
            camera="close up",
            visual_prompt="cinematic room",
            negative_prompt="low quality",
            consistency_refs=["character.hero", "location.room"],
        )
        for index in range(1, 4)
    ]
    project = DramaProject(
        title="测试短剧",
        source_title="测试主题",
        genre="复仇",
        logline="女主反击。",
        audience="短剧观众",
        episode_count=1,
        characters=[
            DramaCharacter(
                id="hero",
                name="林夏",
                role="女主",
                age_range="25-30",
                appearance="黑发",
                costume="白衬衫",
                personality="果断",
                motivation="夺回人生",
                consistency_prompt="林夏，黑发，白衬衫",
            )
        ],
        locations=[
            DramaLocation(
                id="room",
                name="房间",
                visual_style="现代",
                time_period="现代",
                lighting="冷光",
                consistency_prompt="modern room",
            )
        ],
        episodes=[DramaEpisode(index=1, title="第一集", hook="醒来", synopsis="反击", cliffhanger="录音", shots=shots)],
        adaptation_notes=["压缩节奏"],
    )
    submitted = []
    stored = []

    class StubAdapter:
        def __init__(self, llm):
            self.llm = llm

        def adapt_result(self, result):
            assert result.topic == "测试主题"
            assert "确认剧本" in result.synthesis
            return project

    class StubExporter:
        def export(self, exported_project):
            assert exported_project is project
            package_dir = tmp_path / "package"
            package_dir.mkdir()
            return package_dir

    class StubJob:
        def __init__(self, shot_id):
            self.shot_id = shot_id
            self.provider_job_id = f"job_{shot_id}"

        def to_dict(self):
            return {"shot_id": self.shot_id, "provider_job_id": self.provider_job_id}

    class StubProvider:
        def submit_shot(self, shot):
            submitted.append(shot.id)
            return StubJob(shot.id)

    class StubStore:
        def __init__(self, path):
            self.path = path

        def append(self, job):
            stored.append(job.shot_id)

    deps = SimpleNamespace(settings=SimpleNamespace(model="deepseek-v4-pro"))
    payload = create_video_tasks_payload(
        deps,
        "测试主题/小说正文.md",
        2,
        stage_drafts={"script": "确认剧本"},
        llm_factory=lambda settings, temperature=0.3: object(),
        adapter_cls=StubAdapter,
        exporter_cls=StubExporter,
        provider_factory=lambda: StubProvider(),
        job_store_cls=StubStore,
    )

    assert payload["status"] == "submitted"
    assert payload["submitted_count"] == 2
    assert payload["manifest_uri"].startswith("local://drama-video/")
    assert submitted == ["shot_1", "shot_2"]
    assert stored == submitted

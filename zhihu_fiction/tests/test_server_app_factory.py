"""Tests for the industrial FastAPI app skeleton."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from zhihu_fiction.app.state import AppState
from zhihu_fiction.workspace.models import DramaVideoJob, DramaVideoRun
from zhihu_fiction.workspace.repositories import WorkspaceRepository


@pytest.fixture
def isolated_story_roots(monkeypatch, tmp_path):
    app_root = tmp_path / "app"
    output_dir = app_root / "output"
    output_dir.mkdir(parents=True)
    monkeypatch.setitem(
        sys.modules,
        "zhihu_fiction.server",
        SimpleNamespace(APP_ROOT=app_root, OUTPUT_DIR=output_dir),
    )
    return app_root, output_dir


def test_app_state_initializes_runtime_containers():
    state = AppState()

    assert state.run_events == {}
    assert state.run_progress == {}
    assert state.video_events == {}
    assert state.video_progress == {}
    assert state.video_specs == {}
    assert state.video_deepagent_specs == {}
    assert state.video_deepagent_stage_tasks == {}
    assert state.active_run_id is None


def test_app_state_can_store_asyncio_queues():
    state = AppState()
    queue = asyncio.Queue()

    state.run_events["run_1"] = queue

    assert state.run_events["run_1"] is queue


def test_app_dependencies_create_workspace_services():
    from zhihu_fiction.app.dependencies import AppDependencies

    deps = AppDependencies()

    assert deps.settings is not None
    assert deps.skills_store is not None
    assert deps.workspace_repo is not None
    assert deps.workspace_service is not None
    assert deps.workspace_queue is not None
    assert deps.queue_backend is not None
    assert deps.infrastructure_status()["workspace_backend"] in {"jsonl", "sqlite"}


def test_app_dependencies_create_exporter_requires_model_credentials(monkeypatch):
    from zhihu_fiction.app.dependencies import AppDependencies
    from zhihu_fiction.config import Settings

    deps = AppDependencies(settings=Settings(
        api_key="",
        api_base=None,
        model="deepseek-v4-pro",
        temperature=0.7,
    ))

    try:
        deps.create_exporter()
    except RuntimeError as exc:
        assert "Missing DEEPSEEK_API_KEY" in str(exc)
    else:
        raise AssertionError("create_exporter should require model credentials")


def test_app_dependencies_initializes_video_recovery_state(tmp_path):
    from zhihu_fiction.app.dependencies import AppDependencies

    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(DramaVideoJob(
        id="video_stale",
        kind="generate_video",
        run_id="video_stale",
        status="running",
    ))

    deps = AppDependencies(workspace_repo=repo)

    assert deps.video_job_recovery == {"refresh_queued": 0, "failed": 0}
    assert repo.get_drama_video_job("video_stale").status == "running"


def test_create_app_recovers_submitted_video_runs_on_startup(tmp_path):
    from zhihu_fiction.app.dependencies import AppDependencies
    from zhihu_fiction.app.factory import create_app

    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = AppDependencies(workspace_repo=repo)
    jobs_path = tmp_path / "package" / "video_jobs.jsonl"
    jobs_path.parent.mkdir()
    jobs_path.write_text(
        '{"provider":"bailian","provider_job_id":"task-1","shot_id":"shot_1","status":"PENDING"}\n',
        encoding="utf-8",
    )
    repo.save_drama_video_run(DramaVideoRun(
        id="video_submitted",
        story_path="故事/小说正文.md",
        status="running",
        jobs_path=str(jobs_path),
        package_dir=str(jobs_path.parent),
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="video_submitted",
        kind="generate_video",
        run_id="video_submitted",
        status="running",
    ))

    app = create_app(dependencies=deps)
    with TestClient(app) as client:
        response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200
    assert response.json()["video_job_recovery"] == {"refresh_queued": 1, "failed": 0}
    refresh_jobs = [
        job for job in repo.list_drama_video_jobs("video_submitted")
        if job.kind == "refresh_status"
    ]
    assert len(refresh_jobs) == 1
    assert refresh_jobs[0].status == "queued"


def test_create_app_mounts_workspace_router():
    from zhihu_fiction.app.factory import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/workspace/materials")

    assert response.status_code == 200


def test_create_app_serves_static_workbenches():
    from zhihu_fiction.app.factory import create_app

    app = create_app()
    client = TestClient(app)

    index = client.get("/")
    video = client.get("/video")

    assert index.status_code == 200
    assert "Zhihu Fiction Studio" in index.text
    assert video.status_code == 200
    assert "短剧视频生产" in video.text


def test_create_app_serves_story_list_and_story_content(isolated_story_roots):
    from zhihu_fiction.app.factory import create_app

    app = create_app()
    client = TestClient(app)

    stories = client.get("/api/stories")

    assert stories.status_code == 200
    assert isinstance(stories.json(), list)


def test_create_app_serves_run_history():
    from zhihu_fiction.app.factory import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_app_exposes_pipeline_run_endpoint():
    from zhihu_fiction.app.factory import create_app

    app = create_app()
    client = TestClient(app)

    response = client.post("/api/run", json={"topic": "测试主题", "genre": "悬疑"})

    assert response.status_code in {200, 409}


def test_create_app_serves_drama_video_infrastructure():
    from zhihu_fiction.app.factory import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200
    assert response.json()["creative_model"] == "deepseek-v4-pro"


def test_server_module_exports_fastapi_app():
    import zhihu_fiction.server as server_mod

    client = TestClient(server_mod.app)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200
    assert "workspace_backend" in response.json()


def test_video_infrastructure_env_documentation_exists():
    readme = Path("zhihu_fiction/README.md").read_text(encoding="utf-8")
    env_example = Path("zhihu_fiction/.env.example").read_text(encoding="utf-8")

    assert "ZH_VIDEO_QUEUE_BACKEND" in readme
    assert "ZH_OBJECT_STORAGE_BACKEND" in readme
    assert "MINIO_ENDPOINT" in env_example
    assert "REDIS_URL" in env_example

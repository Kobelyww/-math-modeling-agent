# Zhihu Fiction Industrial Backend Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `zhihu_fiction/server.py` into an industrial FastAPI application skeleton while keeping every existing API and web page compatible.

**Architecture:** Introduce `zhihu_fiction/app/` with an app factory, dependency container, runtime state object, route modules, and runtime services. Keep `zhihu_fiction.server:app` as the public compatibility entrypoint until callers and tests can move gradually.

**Tech Stack:** Python 3.11, FastAPI, Starlette middleware, pytest, existing `zhihu_fiction.workspace`, `zhihu_fiction.drama`, `zhihu_fiction.pipeline`, local JSONL/SQLite/Redis/MinIO adapters.

---

## File Structure

Create these files:

- `zhihu_fiction/app/__init__.py`
  Public exports for `create_app`, `AppDependencies`, and `AppState`.

- `zhihu_fiction/app/state.py`
  Holds runtime-only queues, specs, locks, background task registries, and active run state.

- `zhihu_fiction/app/dependencies.py`
  Creates settings, skills store, workspace repository/service/queue, queue backend, pipeline factory, exporter factory, and infrastructure status data.

- `zhihu_fiction/app/factory.py`
  Builds the FastAPI app, installs middleware/exception handler, attaches dependencies and state, and registers route modules.

- `zhihu_fiction/app/routes/__init__.py`
  Exports route factory helpers.

- `zhihu_fiction/app/routes/static.py`
  Owns `GET /` and `GET /video`.

- `zhihu_fiction/app/routes/stories.py`
  Owns story listing, story loading, story path safety, and story file to `WorkflowResult` helpers.

- `zhihu_fiction/app/routes/pipeline.py`
  Owns pipeline run, stream, continue, history, skills, and scheduler endpoints.

- `zhihu_fiction/app/routes/drama_video.py`
  Owns all `/api/drama-video*` endpoints.

- `zhihu_fiction/app/services/__init__.py`
  Empty package marker.

- `zhihu_fiction/app/services/pipeline_runtime.py`
  Owns pipeline execution, SSE queue writing, run history reading, scheduler controls.

- `zhihu_fiction/app/services/drama_video_runtime.py`
  Owns short-drama stage generation, DeepAgent session persistence, video run specs, SSE video execution, infrastructure status, and project package export.

Modify these files:

- `zhihu_fiction/server.py`
  Gradually becomes a thin compatibility module exporting `app` and selected legacy names.

- `zhihu_fiction/tests/test_server_app_factory.py`
  New tests for app factory and route registration.

- `zhihu_fiction/tests/test_server_drama_video.py`
  Keep existing tests green; update monkeypatch target only if a compatibility export is not practical.

- `zhihu_fiction/tests/test_workspace_api.py`
  Keep existing server import compatibility green.

---

## Task 1: Add App State Container

**Files:**
- Create: `zhihu_fiction/app/__init__.py`
- Create: `zhihu_fiction/app/state.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write the failing test**

Add this file:

```python
"""Tests for the industrial FastAPI app skeleton."""
from __future__ import annotations

import asyncio

from zhihu_fiction.app.state import AppState


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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_app_state_initializes_runtime_containers -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'zhihu_fiction.app'`.

- [ ] **Step 3: Implement `AppState`**

Create `zhihu_fiction/app/__init__.py`:

```python
"""FastAPI application package for Zhihu Fiction Studio."""
from .state import AppState

__all__ = ["AppState"]
```

Create `zhihu_fiction/app/state.py`:

```python
"""Runtime-only FastAPI application state."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field

from .typing import AsyncTaskMap


@dataclass
class AppState:
    run_events: dict[str, asyncio.Queue] = field(default_factory=dict)
    run_progress: dict[str, dict] = field(default_factory=dict)
    video_events: dict[str, asyncio.Queue] = field(default_factory=dict)
    video_progress: dict[str, dict] = field(default_factory=dict)
    video_specs: dict[str, dict] = field(default_factory=dict)
    video_deepagent_specs: dict[str, dict] = field(default_factory=dict)
    video_deepagent_stage_tasks: AsyncTaskMap = field(default_factory=dict)
    video_lock: threading.Lock = field(default_factory=threading.Lock)
    video_deepagent_lock: threading.Lock = field(default_factory=threading.Lock)
    active_lock: threading.Lock = field(default_factory=threading.Lock)
    active_run_id: str | None = None
```

Create `zhihu_fiction/app/typing.py`:

```python
"""Small app-layer typing aliases."""
from __future__ import annotations

import asyncio

AsyncTaskMap = dict[str, asyncio.Task]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_app_state_initializes_runtime_containers zhihu_fiction/tests/test_server_app_factory.py::test_app_state_can_store_asyncio_queues -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/__init__.py zhihu_fiction/app/state.py zhihu_fiction/app/typing.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: add zhihu fiction app state container"
```

---

## Task 2: Add Dependency Container

**Files:**
- Create: `zhihu_fiction/app/dependencies.py`
- Modify: `zhihu_fiction/app/__init__.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write the failing test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
from zhihu_fiction.app.dependencies import AppDependencies


def test_app_dependencies_create_workspace_services():
    deps = AppDependencies()

    assert deps.settings is not None
    assert deps.skills_store is not None
    assert deps.workspace_repo is not None
    assert deps.workspace_service is not None
    assert deps.workspace_queue is not None
    assert deps.queue_backend is not None
    assert deps.create_exporter() is not None
    assert deps.infrastructure_status()["workspace_backend"] in {"jsonl", "sqlite"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_app_dependencies_create_workspace_services -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `AppDependencies`.

- [ ] **Step 3: Implement `AppDependencies`**

Create `zhihu_fiction/app/dependencies.py`:

```python
"""Application dependency container."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..config import load_settings
from ..drama.stage_assets import estimate_video_cost
from ..exporter import Exporter
from ..llm import create_llm
from ..pipeline import Pipeline
from ..skills_store import SkillsStore
from ..workspace.queue import WorkspaceQueue
from ..workspace.queue_backends import create_queue_backend
from ..workspace.repositories import WorkspaceRepository
from ..workspace.services import WorkspaceService


class _NoopPublisher:
    def publish(self, title: str, content: str, tags=None, genre: str = "") -> dict:
        return {
            "success": True,
            "url": "",
            "message": "publish skipped (use /autopublish or scheduler)",
        }


@dataclass
class AppDependencies:
    settings: object = field(default_factory=load_settings)
    skills_store: SkillsStore = field(default_factory=SkillsStore)
    workspace_repo: WorkspaceRepository = field(default_factory=WorkspaceRepository)

    def __post_init__(self) -> None:
        self.workspace_service = WorkspaceService(self.workspace_repo)
        self.queue_backend = create_queue_backend()
        self.workspace_queue = WorkspaceQueue(
            self.workspace_repo,
            self.workspace_service,
            pipeline_factory=self.create_pipeline,
        )
        self.workspace_queue.repair_stale_running()

    def create_pipeline(self) -> Pipeline:
        from ..orchestrator import create_orchestrator

        coordinator, reviewer, llm = create_orchestrator(
            self.settings,
            skills_store=self.skills_store,
        )
        return Pipeline(
            coordinator=coordinator,
            reviewer=reviewer,
            llm=llm,
            publisher=_NoopPublisher(),
            quality_threshold=6.0,
            max_rewrites=2,
        )

    def create_exporter(self) -> Exporter:
        return Exporter(create_llm(self.settings, temperature=0.3))

    def infrastructure_status(self) -> dict:
        default_unit_price = float(os.getenv("ZH_VIDEO_UNIT_PRICE_CNY", "0") or "0")
        asset_backend = (os.getenv("ZH_ASSET_BACKEND") or "local").strip().lower() or "local"
        return {
            "workspace_backend": getattr(self.workspace_repo, "backend", "jsonl"),
            "queue_backend": getattr(self.queue_backend, "backend", "local"),
            "asset_backend": asset_backend,
            "video_provider": os.getenv("ZH_VIDEO_PROVIDER", "bailian"),
            "creative_model": "deepseek-v4-pro",
            "video_model": os.getenv("BAILIAN_VIDEO_MODEL", "wanx2.1-t2v-turbo"),
            "cost_guardrail": {
                "shot_limit_default": 1,
                "shot_limit_max": 20,
                "billable_stage": "video",
                "estimate": estimate_video_cost(
                    shot_count=1,
                    seconds_per_shot=6,
                    unit_price_cny=default_unit_price,
                ),
            },
        }
```

Update `zhihu_fiction/app/__init__.py`:

```python
"""FastAPI application package for Zhihu Fiction Studio."""
from .dependencies import AppDependencies
from .state import AppState

__all__ = ["AppDependencies", "AppState"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_app_dependencies_create_workspace_services -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/dependencies.py zhihu_fiction/app/__init__.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: add zhihu fiction app dependencies"
```

---

## Task 3: Add App Factory With Middleware And Workspace Router

**Files:**
- Create: `zhihu_fiction/app/factory.py`
- Modify: `zhihu_fiction/app/__init__.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write the failing test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
from fastapi.testclient import TestClient

from zhihu_fiction.app.factory import create_app


def test_create_app_mounts_workspace_router():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/workspace/materials")

    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_mounts_workspace_router -v
```

Expected: FAIL with `ModuleNotFoundError` for `zhihu_fiction.app.factory`.

- [ ] **Step 3: Implement `create_app()`**

Create `zhihu_fiction/app/factory.py`:

```python
"""FastAPI application factory."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..workspace_routes import create_workspace_router
from .dependencies import AppDependencies
from .state import AppState

logger = logging.getLogger("zhihu_fiction.server")


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(
            "%s %s — %d (%.2fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "path": str(request.url.path)},
    )


def create_app(
    dependencies: AppDependencies | None = None,
    state: AppState | None = None,
) -> FastAPI:
    deps = dependencies or AppDependencies()
    app_state = state or AppState()

    app = FastAPI(title="Zhihu Fiction Studio", version="1.0")
    app.state.dependencies = deps
    app.state.runtime = app_state

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(TimingMiddleware)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(
        create_workspace_router(
            deps.workspace_service,
            deps.workspace_queue,
            deps.create_exporter,
        )
    )
    return app
```

Update `zhihu_fiction/app/__init__.py`:

```python
"""FastAPI application package for Zhihu Fiction Studio."""
from .dependencies import AppDependencies
from .factory import create_app
from .state import AppState

__all__ = ["AppDependencies", "AppState", "create_app"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_mounts_workspace_router -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/factory.py zhihu_fiction/app/__init__.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: add zhihu fiction app factory"
```

---

## Task 4: Move Static Routes

**Files:**
- Create: `zhihu_fiction/app/routes/__init__.py`
- Create: `zhihu_fiction/app/routes/static.py`
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write the failing test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_create_app_serves_static_workbenches():
    app = create_app()
    client = TestClient(app)

    index = client.get("/")
    video = client.get("/video")

    assert index.status_code == 200
    assert "Zhihu Fiction Studio" in index.text
    assert video.status_code == 200
    assert "短剧视频生产" in video.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_static_workbenches -v
```

Expected: FAIL with `404 Not Found`.

- [ ] **Step 3: Implement static router**

Create `zhihu_fiction/app/routes/__init__.py`:

```python
"""FastAPI route modules for Zhihu Fiction Studio."""
```

Create `zhihu_fiction/app/routes/static.py`:

```python
"""Static workbench routes."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ...config import APP_ROOT

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index():
    static_file = APP_ROOT / "static" / "index.html"
    if not static_file.exists():
        return HTMLResponse("<h2>index.html not found. Create static/index.html first.</h2>", status_code=404)
    return HTMLResponse(static_file.read_text(encoding="utf-8"))


@router.get("/video", response_class=HTMLResponse)
async def video_workspace():
    static_file = APP_ROOT / "static" / "video.html"
    if not static_file.exists():
        return HTMLResponse("<h2>video.html not found. Create static/video.html first.</h2>", status_code=404)
    return HTMLResponse(static_file.read_text(encoding="utf-8"))
```

Modify `zhihu_fiction/app/factory.py`:

```python
from .routes import static
```

Inside `create_app()`, before workspace router:

```python
    app.include_router(static.router)
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_static_workbenches zhihu_fiction/tests/test_static_particle_workbench.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/routes/__init__.py zhihu_fiction/app/routes/static.py zhihu_fiction/app/factory.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: move static workbench routes"
```

---

## Task 5: Move Story Routes And Helpers

**Files:**
- Create: `zhihu_fiction/app/routes/stories.py`
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write the failing test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_create_app_serves_story_list_and_story_content():
    app = create_app()
    client = TestClient(app)

    stories = client.get("/api/stories")

    assert stories.status_code == 200
    assert isinstance(stories.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_story_list_and_story_content -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Implement story route module**

Create `zhihu_fiction/app/routes/stories.py` by moving these functions from `server.py` without changing behavior:

```python
"""Story listing and loading routes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...base import extract_story_body
from ...config import APP_ROOT
from ...orchestrator import WorkflowResult

router = APIRouter()
OUTPUT_DIR = APP_ROOT / "output"


def list_story_dirs() -> list[dict]:
    if not OUTPUT_DIR.exists():
        return []
    stories: list[dict] = []
    for directory in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if directory.is_dir() and not directory.name.startswith("."):
            story_file = directory / "小说正文.md"
            if story_file.exists():
                content = story_file.read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                excerpt = next(
                    (line for line in lines if line.strip() and not line.startswith("#") and not line.startswith(">")),
                    "",
                )[:200]
                stories.append({
                    "name": directory.name,
                    "path": str(story_file.relative_to(APP_ROOT)),
                    "excerpt": excerpt,
                    "created_at": datetime.fromtimestamp(story_file.stat().st_mtime).isoformat(),
                })
    return stories


def safe_story_file(story_path: str) -> Path:
    candidate = (APP_ROOT / story_path).resolve()
    app_root = APP_ROOT.resolve()
    if app_root not in candidate.parents and candidate != app_root:
        raise HTTPException(400, "invalid story_path")
    if not candidate.is_file():
        raise HTTPException(404, "story not found")
    return candidate


def story_result_from_file(story_file: Path) -> WorkflowResult:
    text = story_file.read_text(encoding="utf-8")
    topic = story_file.parent.name
    genre = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("> 题材："):
            genre = stripped.replace("> 题材：", "", 1).strip()
            break
    story_body, synthesis = extract_web_story_body(text)
    return WorkflowResult(
        topic=topic,
        genre=genre or "未指定",
        topic_analysis="",
        outline="",
        draft=story_body,
        polished=story_body,
        review="",
        synthesis=synthesis,
    )


def extract_web_story_body(text: str) -> tuple[str, str]:
    body = extract_story_body(text)
    marker = "\n---\n\n# 发布方案"
    if marker in text:
        synthesis = text.split(marker, 1)[1].strip()
    else:
        synthesis = ""
    return body, synthesis


@router.get("/api/stories")
async def list_stories():
    return list_story_dirs()


@router.get("/api/stories/{story_path:path}")
async def get_story(story_path: str):
    full_path = safe_story_file(story_path)
    return {"path": story_path, "content": full_path.read_text(encoding="utf-8")}
```

Modify `zhihu_fiction/app/factory.py`:

```python
from .routes import static, stories
```

Inside `create_app()`:

```python
    app.include_router(stories.router)
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_story_list_and_story_content zhihu_fiction/tests/test_server_drama_video.py::test_drama_video_endpoint_rejects_missing_story -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/routes/stories.py zhihu_fiction/app/factory.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: move story routes"
```

---

## Task 6: Make `server.py` Use `create_app()` While Preserving Legacy App

**Files:**
- Modify: `zhihu_fiction/server.py`
- Test: `zhihu_fiction/tests/test_workspace_api.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write compatibility test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_server_module_exports_fastapi_app():
    import zhihu_fiction.server as server_mod

    client = TestClient(server_mod.app)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200
    assert "workspace_backend" in response.json()
```

- [ ] **Step 2: Run test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_server_module_exports_fastapi_app -v
```

Expected: PASS before refactor. Keep it passing after refactor.

- [ ] **Step 3: Attach app factory without removing old routes**

At this stage do not delete existing `server.py` route definitions. Add this import near the top:

```python
from .app.factory import create_app as create_industrial_app
```

Do not replace `app = FastAPI(...)` yet. This step is a safety bridge so later route modules can be compared without breaking current import-time behavior.

- [ ] **Step 4: Run compatibility tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_workspace_api.py::test_server_mounts_workspace_and_keeps_legacy_routes -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/server.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: add app factory compatibility bridge"
```

---

## Task 7: Move Pipeline Runtime

**Files:**
- Create: `zhihu_fiction/app/services/pipeline_runtime.py`
- Create: `zhihu_fiction/app/routes/pipeline.py`
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`
- Test: `zhihu_fiction/tests/test_pipeline.py`

- [ ] **Step 1: Write route registration test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_create_app_serves_run_history():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/runs")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_run_history -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Implement minimal `pipeline_runtime.py`**

Create `zhihu_fiction/app/services/__init__.py`:

```python
"""Application service modules."""
```

Create `zhihu_fiction/app/services/pipeline_runtime.py` by moving these current `server.py` functions without changing behavior:

```python
"""Runtime service for fiction pipeline API."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ...pipeline import Pipeline, RUN_DIR


def read_runs(limit: int = 50) -> list[dict]:
    runs_file = RUN_DIR / "runs.jsonl"
    if not runs_file.exists():
        return []
    runs: list[dict] = []
    with open(runs_file, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    runs.reverse()
    return runs[:limit]
```

Add `execute_pipeline_in_background(...)` later in Task 8. Keep this task small.

- [ ] **Step 4: Implement run history route**

Create `zhihu_fiction/app/routes/pipeline.py`:

```python
"""Pipeline API routes."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.pipeline_runtime import read_runs

router = APIRouter()


@router.get("/api/runs")
async def list_runs(limit: int = Query(50, ge=1, le=500)):
    return read_runs(limit)


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    from fastapi import HTTPException

    for run in read_runs(500):
        if run.get("run_id") == run_id:
            return run
    raise HTTPException(404, "运行未找到")
```

Modify `zhihu_fiction/app/factory.py`:

```python
from .routes import pipeline, static, stories
```

Inside `create_app()`:

```python
    app.include_router(pipeline.router)
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_run_history zhihu_fiction/tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add zhihu_fiction/app/services/__init__.py zhihu_fiction/app/services/pipeline_runtime.py zhihu_fiction/app/routes/pipeline.py zhihu_fiction/app/factory.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: move run history routes"
```

---

## Task 8: Move Pipeline Run And SSE Routes

**Files:**
- Modify: `zhihu_fiction/app/services/pipeline_runtime.py`
- Modify: `zhihu_fiction/app/routes/pipeline.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write run trigger test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_create_app_exposes_pipeline_run_endpoint():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/run", json={"topic": "测试主题", "genre": "悬疑"})

    assert response.status_code in {200, 409}
```

- [ ] **Step 2: Run test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_exposes_pipeline_run_endpoint -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Move `_execute_in_background` and trigger route**

Move current `server.py` function `_execute_in_background` into `pipeline_runtime.py` as:

```python
async def execute_pipeline_in_background(
    state,
    run_id: str,
    pipeline: Pipeline,
    topic: str | None,
    genre: str | None,
    chapters: int = 1,
) -> None:
    ...
```

Replace all references to `_run_events`, `_run_progress`, `_active_lock`, `_active_run_id` with `state.run_events`, `state.run_progress`, `state.active_lock`, `state.active_run_id`.

In `routes/pipeline.py`, add:

```python
import asyncio
from datetime import datetime
from fastapi import Request
from fastapi.responses import StreamingResponse


@router.post("/api/run")
async def trigger_run(req: Request):
    deps = req.app.state.dependencies
    state = req.app.state.runtime
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    topic = (body.get("topic") or "").strip() or None
    genre = (body.get("genre") or "").strip() or None
    chapters = body.get("chapters", 1)

    with state.active_lock:
        if state.active_run_id:
            raise HTTPException(409, "已有运行正在执行，请等待完成")
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        state.active_run_id = run_id

    pipeline = deps.create_pipeline()
    state.run_events[run_id] = asyncio.Queue()
    state.run_progress[run_id] = {"status": "starting"}
    asyncio.create_task(execute_pipeline_in_background(state, run_id, pipeline, topic, genre, chapters))
    return {"run_id": run_id, "status": "started"}
```

Also add current `/api/stream/{run_id}` logic, replacing `_run_events` with `state.run_events`.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_exposes_pipeline_run_endpoint zhihu_fiction/tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/services/pipeline_runtime.py zhihu_fiction/app/routes/pipeline.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: move pipeline run routes"
```

---

## Task 9: Move Drama Video Runtime And Routes

**Files:**
- Create: `zhihu_fiction/app/services/drama_video_runtime.py`
- Create: `zhihu_fiction/app/routes/drama_video.py`
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write route registration test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_create_app_serves_drama_video_infrastructure():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200
    assert response.json()["creative_model"] == "deepseek-v4-pro"
```

- [ ] **Step 2: Run test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_drama_video_infrastructure -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Move runtime helpers**

Create `zhihu_fiction/app/services/drama_video_runtime.py` by moving these helpers from `server.py` without changing behavior:

- `_parse_shot_limit` -> `parse_shot_limit`
- `_parse_video_stage_drafts` -> `parse_video_stage_drafts`
- `_merge_video_stage_drafts` -> `merge_video_stage_drafts`
- `_deepseek_v4pro_settings` -> `deepseek_v4pro_settings`
- `_format_video_stage_context` -> `format_video_stage_context`
- `_run_video_stage_deepagent` -> `run_video_stage_deepagent`
- `_generate_video_stage_draft` -> `generate_video_stage_draft`
- `_new_video_run_id` -> `new_video_run_id`
- `_start_drama_video_spec` -> `start_drama_video_spec`
- `_next_video_deepagent_stage` -> `next_video_deepagent_stage`
- `_assert_video_deepagent_previous_stages_confirmed` -> `assert_video_deepagent_previous_stages_confirmed`
- `_session_to_spec` -> `session_to_spec`
- `_persist_video_deepagent_session` -> `persist_video_deepagent_session`
- `_record_drama_stage_version` -> `record_drama_stage_version`
- `_get_video_deepagent_spec` -> `get_video_deepagent_spec`
- `_generate_video_deepagent_stage_in_background` -> `generate_video_deepagent_stage_in_background`
- `_drama_video_payload` -> `drama_video_payload`
- `_execute_drama_video_in_background` -> `execute_drama_video_in_background`

The moved functions must accept explicit `deps` and `state` parameters when they need shared objects. Example:

```python
def infrastructure_status(deps) -> dict:
    return deps.infrastructure_status()
```

Example for stateful spec access:

```python
def get_video_deepagent_spec(deps, state, run_id: str) -> dict | None:
    spec = state.video_deepagent_specs.get(run_id)
    if spec is not None:
        return spec
    session = deps.workspace_repo.get_drama_session(run_id)
    if session is None:
        return None
    spec = session_to_spec(session)
    state.video_deepagent_specs[run_id] = spec
    return spec
```

- [ ] **Step 4: Move minimal infrastructure route**

Create `zhihu_fiction/app/routes/drama_video.py`:

```python
"""Short-drama video routes."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/drama-video/infrastructure")
async def get_drama_video_infrastructure(req: Request):
    return req.app.state.dependencies.infrastructure_status()
```

Modify `zhihu_fiction/app/factory.py`:

```python
from .routes import drama_video, pipeline, static, stories
```

Inside `create_app()`:

```python
    app.include_router(drama_video.router)
```

- [ ] **Step 5: Run route registration test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_create_app_serves_drama_video_infrastructure -v
```

Expected: PASS.

- [ ] **Step 6: Move all drama video routes**

Move the current route bodies from `server.py` into `app/routes/drama_video.py`, replacing global references:

- `workspace_repo` -> `req.app.state.dependencies.workspace_repo`
- `_video_events` -> `req.app.state.runtime.video_events`
- `_video_specs` -> `req.app.state.runtime.video_specs`
- `_video_lock` -> `req.app.state.runtime.video_lock`
- `_video_deepagent_specs` -> `req.app.state.runtime.video_deepagent_specs`
- `_video_deepagent_stage_tasks` -> `req.app.state.runtime.video_deepagent_stage_tasks`
- `_safe_story_file` -> `stories.safe_story_file`
- `_story_result_from_file` -> `stories.story_result_from_file`

Keep behavior and response shapes byte-for-byte equivalent where practical.

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py zhihu_fiction/tests/test_drama_video.py zhihu_fiction/tests/test_drama_infrastructure.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add zhihu_fiction/app/services/drama_video_runtime.py zhihu_fiction/app/routes/drama_video.py zhihu_fiction/app/factory.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: move drama video routes"
```

---

## Task 10: Thin `server.py` Compatibility Module

**Files:**
- Modify: `zhihu_fiction/server.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`
- Test: `zhihu_fiction/tests/test_workspace_api.py`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write thin-server line count test**

Append to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
from pathlib import Path


def test_server_module_is_thin_compatibility_entrypoint():
    server_path = Path("zhihu_fiction/server.py")
    line_count = len(server_path.read_text(encoding="utf-8").splitlines())

    assert line_count < 300
```

- [ ] **Step 2: Run test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_server_module_is_thin_compatibility_entrypoint -v
```

Expected: FAIL because `server.py` is currently around 1400 lines.

- [ ] **Step 3: Replace `server.py` with compatibility exports**

After Tasks 1-9 are green, replace `zhihu_fiction/server.py` with:

```python
"""Compatibility entrypoint for Zhihu Fiction Studio Web server."""
from __future__ import annotations

from .app.dependencies import AppDependencies
from .app.factory import create_app
from .app.state import AppState

dependencies = AppDependencies()
state = AppState()
app = create_app(dependencies=dependencies, state=state)

settings = dependencies.settings
skills_store = dependencies.skills_store
workspace_repo = dependencies.workspace_repo
workspace_service = dependencies.workspace_service
workspace_queue = dependencies.workspace_queue
queue_backend = dependencies.queue_backend

_run_events = state.run_events
_run_progress = state.run_progress
_video_events = state.video_events
_video_progress = state.video_progress
_video_specs = state.video_specs
_video_deepagent_specs = state.video_deepagent_specs
_video_deepagent_stage_tasks = state.video_deepagent_stage_tasks
_video_lock = state.video_lock
_video_deepagent_lock = state.video_deepagent_lock
_active_lock = state.active_lock

from .app.routes.stories import (  # noqa: E402
    OUTPUT_DIR,
    extract_web_story_body as _extract_web_story_body,
    list_story_dirs as _list_story_dirs,
    safe_story_file as _safe_story_file,
    story_result_from_file as _story_result_from_file,
)
from .app.services.pipeline_runtime import read_runs as _read_runs  # noqa: E402
from .app.services.drama_video_runtime import (  # noqa: E402
    assert_video_deepagent_previous_stages_confirmed as _assert_video_deepagent_previous_stages_confirmed,
    deepseek_v4pro_settings as _deepseek_v4pro_settings,
    drama_video_payload as _drama_video_payload,
    execute_drama_video_in_background as _execute_drama_video_in_background,
    format_video_stage_context as _format_video_stage_context,
    generate_video_deepagent_stage_in_background as _generate_video_deepagent_stage_in_background,
    generate_video_stage_draft as _generate_video_stage_draft,
    get_video_deepagent_spec as _get_video_deepagent_spec,
    infrastructure_status as _infrastructure_status,
    merge_video_stage_drafts as _merge_video_stage_drafts,
    new_video_run_id as _new_video_run_id,
    next_video_deepagent_stage as _next_video_deepagent_stage,
    parse_shot_limit as _parse_shot_limit,
    parse_video_stage_drafts as _parse_video_stage_drafts,
    persist_video_deepagent_session as _persist_video_deepagent_session,
    record_drama_stage_version as _record_drama_stage_version,
    run_video_stage_deepagent as _run_video_stage_deepagent,
    session_to_spec as _session_to_spec,
    start_drama_video_spec as _start_drama_video_spec,
)
from .drama import DramaAdapter, DramaAdapterError, DramaExporter  # noqa: E402,F401
from .drama.video import BailianVideoProvider, DramaVideoError, VideoJobStore, create_video_provider  # noqa: E402,F401
from .llm import create_llm  # noqa: E402,F401
from .orchestrator import create_drama_video_coordinator, create_orchestrator, run_drama_video_coordinator  # noqa: E402,F401
```

If any existing tests monkeypatch old `server_mod._generate_video_stage_draft`, route modules will not automatically see that patched alias. Prefer updating tests to patch `zhihu_fiction.app.services.drama_video_runtime.generate_video_stage_draft`. If preserving monkeypatch compatibility is mandatory, add indirection functions in `drama_video_runtime` that can be dependency-injected.

- [ ] **Step 4: Run compatibility tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_server_drama_video.py zhihu_fiction/tests/test_workspace_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full tests**

Run:

```bash
python -m pytest zhihu_fiction/tests -q
git diff --check
```

Expected: `128 passed` or higher if new tests were added, and clean diff check.

- [ ] **Step 6: Commit**

```bash
git add zhihu_fiction/server.py zhihu_fiction/tests/test_server_app_factory.py
git commit -m "refactor: thin zhihu fiction server entrypoint"
```

---

## Task 11: Local Service Smoke Test

**Files:**
- No code files unless smoke test exposes a bug.

- [ ] **Step 1: Start service**

Run:

```bash
python -m uvicorn zhihu_fiction.server:app --host 127.0.0.1 --port 8010
```

Expected: server starts on `http://127.0.0.1:8010`.

- [ ] **Step 2: Verify key endpoints**

Run in another shell:

```bash
curl -s http://127.0.0.1:8010/api/drama-video/infrastructure
curl -s http://127.0.0.1:8010/video | rg "background: true|pollDeepAgentSession"
curl -s http://127.0.0.1:8010/api/stories
```

Expected:

- infrastructure JSON contains `workspace_backend`
- `/video` contains background DeepAgent polling markers
- `/api/stories` returns a JSON list

- [ ] **Step 3: Stop service**

Use `Ctrl-C` in the uvicorn shell.

- [ ] **Step 4: Commit if smoke test required code changes**

If a bug was fixed:

```bash
git add zhihu_fiction
git commit -m "fix: stabilize industrial app smoke test"
```

---

## Self-Review Checklist

- Spec coverage: this plan implements app factory, dependency container, state container, static/story/pipeline/drama route separation, compatibility server entrypoint, and testing.
- Scope control: frontend framework migration, SQL migration, Redis workers, and UI redesign are explicitly excluded.
- Type consistency: the shared runtime container is always `AppState`; shared dependency container is always `AppDependencies`; new app factory is always `create_app`.
- Compatibility risk: tests may need monkeypatch target updates after Task 10 because route modules no longer read old `server_mod` function aliases.

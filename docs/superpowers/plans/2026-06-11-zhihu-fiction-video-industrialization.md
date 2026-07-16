# Zhihu Fiction Video Industrialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the short-drama video workflow from a demo-like flow into a recoverable, auditable, queue-ready production workflow.

**Architecture:** Keep the existing FastAPI + Alpine frontend structure, but make `DramaVideoJob` the single execution record for video generation, refresh, retry, and future LoopAgent stages. Add API and frontend visibility first, then introduce queue/storage abstractions behind stable service interfaces so local JSONL/SQLite behavior remains the default and Redis/MinIO can be enabled by configuration.

**Tech Stack:** FastAPI, pytest, Alpine.js, JSONL/SQLite workspace repository, optional Redis queue backend, optional MinIO/S3-compatible object storage, Aliyun Bailian/DashScope video provider.

---

## File Structure

- `zhihu_fiction/workspace/models.py`: existing `DramaVideoJob` model; extend only if a later task proves a field is missing.
- `zhihu_fiction/workspace/repositories.py`: job listing/filtering already exists; add narrowly scoped helpers only when tests require them.
- `zhihu_fiction/app/routes/drama_video.py`: HTTP API surface for video job listing and job actions.
- `zhihu_fiction/app/services/drama_video_execution.py`: synchronous execution logic for video run, refresh, retry, and provider interaction.
- `zhihu_fiction/app/services/drama_video_runtime.py`: request-time orchestration, background task creation, and runtime state bridge.
- `zhihu_fiction/app/services/drama_video_jobs.py`: create this file for reusable job query/status mapping helpers once route logic grows beyond trivial pass-through.
- `zhihu_fiction/app/services/drama_video_queue.py`: create this file for queue backend abstraction.
- `zhihu_fiction/app/services/object_storage.py`: create this file for local filesystem and MinIO-compatible storage abstraction.
- `zhihu_fiction/static/video.html`: single-workspace frontend; add unified task timeline, job polling, and recovery UI.
- `zhihu_fiction/tests/test_server_drama_video.py`: API contract tests.
- `zhihu_fiction/tests/test_drama_video_execution.py`: service behavior tests with fake providers.
- `zhihu_fiction/tests/test_drama_video_queue.py`: create for queue backend tests.
- `zhihu_fiction/tests/test_object_storage.py`: create for storage backend tests.

---

### Task 1: Add Unified Video Job Listing API

**Files:**
- Modify: `zhihu_fiction/app/routes/drama_video.py`
- Create: `zhihu_fiction/app/services/drama_video_jobs.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`

- [ ] **Step 1: Write the failing API test**

Add this test to `zhihu_fiction/tests/test_server_drama_video.py`:

```python
def test_drama_video_jobs_api_lists_jobs_for_run(tmp_path):
    from zhihu_fiction.workspace.models import DramaVideoJob

    client, server_mod = make_test_client(tmp_path)
    repo = server_mod.workspace_repo
    repo.save_drama_video_job(DramaVideoJob(
        id="video_1",
        kind="generate_video",
        run_id="video_1",
        status="completed",
        payload={"story_path": "故事/小说正文.md"},
        result={"submitted_count": 2},
        updated_at="2026-06-11T10:00:00+00:00",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="retry_1",
        kind="retry_shot",
        run_id="video_1",
        shot_id="shot_1",
        status="queued",
        updated_at="2026-06-11T11:00:00+00:00",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="video_other",
        kind="generate_video",
        run_id="video_other",
        status="completed",
    ))

    response = client.get("/api/drama-video/jobs", params={"run_id": "video_1"})

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "video_1"
    assert [job["id"] for job in data["jobs"]] == ["retry_1", "video_1"]
    assert data["summary"] == {"queued": 1, "completed": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py::test_drama_video_jobs_api_lists_jobs_for_run -q
```

Expected: FAIL with HTTP 404 for `/api/drama-video/jobs`.

- [ ] **Step 3: Add service helper**

Create `zhihu_fiction/app/services/drama_video_jobs.py`:

```python
"""Unified short-drama video job query helpers."""
from __future__ import annotations

from fastapi import HTTPException


def list_drama_video_jobs(dependencies, run_id: str | None = None) -> dict:
    repo = getattr(dependencies, "workspace_repo", None)
    if repo is None:
        raise HTTPException(500, "workspace repository is not configured")

    jobs = repo.list_drama_video_jobs(run_id)
    summary: dict[str, int] = {}
    for job in jobs:
        summary[job.status] = summary.get(job.status, 0) + 1

    return {
        "run_id": run_id or "",
        "summary": summary,
        "jobs": [job.to_dict() for job in jobs],
    }
```

- [ ] **Step 4: Add route**

In `zhihu_fiction/app/routes/drama_video.py`, import the helper:

```python
from ..services import drama_video_jobs
```

Add route before `/api/drama-video/run/{run_id}/refresh`:

```python
@router.get("/api/drama-video/jobs")
async def list_drama_video_jobs(req: Request, run_id: str | None = None):
    deps = get_dependencies(req)
    return drama_video_jobs.list_drama_video_jobs(deps, run_id)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py::test_drama_video_jobs_api_lists_jobs_for_run -q
```

Expected: PASS.

- [ ] **Step 6: Run video API regression**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py zhihu_fiction/tests/test_drama_video_execution.py -q
```

Expected: all tests pass.

---

### Task 2: Show Unified Job Timeline In Video Workspace

**Files:**
- Modify: `zhihu_fiction/static/video.html`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`

- [ ] **Step 1: Write static contract test**

Add this test to `zhihu_fiction/tests/test_server_drama_video.py`:

```python
def test_video_page_contains_unified_job_timeline_controls(tmp_path):
    client, _server_mod = make_test_client(tmp_path)

    response = client.get("/video")

    assert response.status_code == 200
    assert "loadVideoRunJobs" in response.text
    assert "/api/drama-video/jobs" in response.text
    assert "videoJobs" in response.text
    assert "任务时间线" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py::test_video_page_contains_unified_job_timeline_controls -q
```

Expected: FAIL because `loadVideoRunJobs` or timeline text is missing.

- [ ] **Step 3: Add frontend state and loader**

In `zhihu_fiction/static/video.html`, add Alpine state:

```javascript
videoJobs: [],
videoJobSummary: {},
videoJobsLoading: false,
```

Add method:

```javascript
async loadVideoRunJobs() {
  if (!this.runId) return;
  this.videoJobsLoading = true;
  try {
    const res = await fetch('/api/drama-video/jobs?run_id=' + encodeURIComponent(this.runId));
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    this.videoJobs = data.jobs || [];
    this.videoJobSummary = data.summary || {};
  } finally {
    this.videoJobsLoading = false;
  }
},
```

Call `await this.loadVideoRunJobs()` after these existing methods update `runId` or jobs:

```javascript
loadVideoRunHistory()
refreshVideoRunJobs()
retryVideoRunJob(job)
startVideoRun()
```

- [ ] **Step 4: Add timeline markup**

Add a compact section near the existing video job list:

```html
<section class="workspace-panel">
  <div class="section-heading">
    <h2>任务时间线</h2>
    <button @click="loadVideoRunJobs()" :disabled="!runId || videoJobsLoading">
      <span x-show="!videoJobsLoading">刷新</span>
      <span x-show="videoJobsLoading">加载中...</span>
    </button>
  </div>
  <template x-if="videoJobs.length === 0">
    <p class="muted">暂无视频任务</p>
  </template>
  <div class="job-timeline" x-show="videoJobs.length">
    <template x-for="job in videoJobs" :key="job.id">
      <div class="job-row">
        <div>
          <strong x-text="job.kind"></strong>
          <span x-text="job.shot_id || job.run_id"></span>
        </div>
        <span class="status-pill" x-text="job.status"></span>
        <p x-show="job.error" x-text="job.error"></p>
      </div>
    </template>
  </div>
</section>
```

- [ ] **Step 5: Run static test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py::test_video_page_contains_unified_job_timeline_controls -q
```

Expected: PASS.

- [ ] **Step 6: Browser QA**

Start the app using the repo's normal command, then open `/video` and verify:

```bash
python -m uvicorn zhihu_fiction.server:app --port 8023
```

Expected: the page renders, opening a story workspace shows “任务时间线”, and there is no visible overlap at desktop width.

---

### Task 3: Register Refresh Operations As `refresh_status` Jobs

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_execution.py`
- Modify: `zhihu_fiction/app/services/drama_video_runtime.py`
- Test: `zhihu_fiction/tests/test_drama_video_execution.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`

- [ ] **Step 1: Write failing service test**

Add this test to `zhihu_fiction/tests/test_drama_video_execution.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_execution.py::test_refresh_video_run_jobs_persists_refresh_job -q
```

Expected: FAIL because `refresh_video_run_jobs()` does not accept `job_id_factory`.

- [ ] **Step 3: Extend refresh signature and save job**

Change `refresh_video_run_jobs()` signature:

```python
def refresh_video_run_jobs(
    dependencies,
    run_id: str,
    *,
    provider_factory=create_video_provider,
    job_store_cls=VideoJobStore,
    job_id_factory=new_id,
) -> dict:
```

At the start after loading `run`, create queued job:

```python
job_id = job_id_factory("video_refresh")
save_video_job(
    dependencies,
    DramaVideoJob(
        id=job_id,
        kind="refresh_status",
        run_id=run_id,
        status="running",
        payload={"run_id": run_id, "jobs_path": run.jobs_path},
    ),
)
```

Before return, build `response` and update job:

```python
response = {
    "run_id": run_id,
    "status": response_status,
    "run": updated.to_dict() if updated is not None else None,
    "summary": summary,
    "jobs": [job.to_dict() for job in refreshed],
}
update_video_job(
    dependencies,
    job_id,
    {
        "status": "completed" if response_status in {"completed", "running", "partial_failed"} else "failed",
        "result": response,
        "error": error,
    },
)
return response
```

- [ ] **Step 4: Run focused service test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_execution.py::test_refresh_video_run_jobs_persists_refresh_job -q
```

Expected: PASS.

- [ ] **Step 5: Run video regression**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_execution.py zhihu_fiction/tests/test_server_drama_video.py -q
```

Expected: all tests pass.

---

### Task 4: Add Recoverable Job Status On Startup

**Files:**
- Create: `zhihu_fiction/app/services/drama_video_recovery.py`
- Modify: `zhihu_fiction/app/server_factory.py` or the app factory file that wires runtime state
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write recovery helper test**

Create `zhihu_fiction/tests/test_drama_video_recovery.py`:

```python
from zhihu_fiction.app.services.drama_video_recovery import mark_stale_video_jobs
from zhihu_fiction.workspace.models import DramaVideoJob
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_mark_stale_video_jobs_marks_running_jobs_failed(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_video_job(DramaVideoJob(
        id="video_1",
        kind="generate_video",
        run_id="video_1",
        status="running",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="retry_1",
        kind="retry_shot",
        run_id="video_1",
        status="queued",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="done_1",
        kind="refresh_status",
        run_id="video_1",
        status="completed",
    ))

    result = mark_stale_video_jobs(repo)

    assert result == {"failed": 2}
    assert repo.get_drama_video_job("video_1").status == "failed"
    assert repo.get_drama_video_job("retry_1").status == "failed"
    assert repo.get_drama_video_job("done_1").status == "completed"
    assert "service restarted" in repo.get_drama_video_job("video_1").error
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_recovery.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement recovery helper**

Create `zhihu_fiction/app/services/drama_video_recovery.py`:

```python
"""Recovery helpers for persisted video jobs."""
from __future__ import annotations

from ...workspace.models import utc_now_iso


RECOVERABLE_STATUSES = {"queued", "running"}


def mark_stale_video_jobs(repo) -> dict[str, int]:
    failed = 0
    now = utc_now_iso()
    for job in repo.list_drama_video_jobs():
        if job.status not in RECOVERABLE_STATUSES:
            continue
        repo.update_drama_video_job(job.id, {
            "status": "failed",
            "error": "video job was interrupted because the service restarted",
            "updated_at": now,
        })
        failed += 1
    return {"failed": failed}
```

- [ ] **Step 4: Run recovery test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_recovery.py -q
```

Expected: PASS.

- [ ] **Step 5: Wire startup recovery**

In the app factory, after `workspace_repo` is initialized and before serving requests:

```python
from .services.drama_video_recovery import mark_stale_video_jobs

mark_stale_video_jobs(workspace_repo)
```

If the existing app factory has a startup hook pattern, call it there instead of module import time.

- [ ] **Step 6: Run app factory and video tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_server_drama_video.py -q
```

Expected: all tests pass.

---

### Task 5: Introduce Queue Backend Interface

**Files:**
- Create: `zhihu_fiction/app/services/drama_video_queue.py`
- Modify: `zhihu_fiction/app/services/drama_video_runtime.py`
- Test: `zhihu_fiction/tests/test_drama_video_queue.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`

- [ ] **Step 1: Write queue tests**

Create `zhihu_fiction/tests/test_drama_video_queue.py`:

```python
from zhihu_fiction.app.services.drama_video_queue import InMemoryVideoQueue, create_video_queue


def test_in_memory_video_queue_records_submitted_jobs():
    queue = InMemoryVideoQueue()

    queue.enqueue("job_1", lambda: "done")

    assert queue.enqueued_job_ids == ["job_1"]


def test_create_video_queue_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("ZH_VIDEO_QUEUE_BACKEND", raising=False)

    queue = create_video_queue()

    assert isinstance(queue, InMemoryVideoQueue)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_queue.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement memory queue**

Create `zhihu_fiction/app/services/drama_video_queue.py`:

```python
"""Queue abstraction for short-drama video background jobs."""
from __future__ import annotations

import os
from collections.abc import Callable


class InMemoryVideoQueue:
    def __init__(self) -> None:
        self.enqueued_job_ids: list[str] = []

    def enqueue(self, job_id: str, submit: Callable[[], object]) -> object:
        self.enqueued_job_ids.append(job_id)
        return submit()


def create_video_queue():
    backend = os.getenv("ZH_VIDEO_QUEUE_BACKEND", "memory").strip().lower()
    if backend == "memory":
        return InMemoryVideoQueue()
    if backend == "redis":
        raise RuntimeError("Redis video queue backend is configured but not installed in this build")
    raise RuntimeError(f"Unsupported video queue backend: {backend}")
```

- [ ] **Step 4: Run queue tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_queue.py -q
```

Expected: PASS.

- [ ] **Step 5: Route runtime through queue interface**

In `zhihu_fiction/app/services/drama_video_runtime.py`, replace direct background task creation for video generation and retry with a queue object only if this can be done without changing API response shape:

```python
from .drama_video_queue import create_video_queue

queue = create_video_queue()
queue.enqueue(run_id, lambda: create_background_task(...))
```

Keep returned fields unchanged:

```python
{
    "run_id": run_id,
    "stream_url": f"/api/drama-video/stream/{run_id}",
}
```

- [ ] **Step 6: Run regression**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_queue.py zhihu_fiction/tests/test_server_drama_video.py -q
```

Expected: all tests pass.

---

### Task 6: Add Object Storage Interface For Packages And Assets

**Files:**
- Create: `zhihu_fiction/app/services/object_storage.py`
- Modify: `zhihu_fiction/app/services/drama_video_execution.py`
- Test: `zhihu_fiction/tests/test_object_storage.py`

- [ ] **Step 1: Write local storage tests**

Create `zhihu_fiction/tests/test_object_storage.py`:

```python
from zhihu_fiction.app.services.object_storage import LocalObjectStorage, create_object_storage


def test_local_object_storage_puts_and_reads_text(tmp_path):
    storage = LocalObjectStorage(tmp_path / "objects")

    uri = storage.put_text("packages/video_1/manifest.json", '{"ok": true}')

    assert uri == "local://packages/video_1/manifest.json"
    assert storage.read_text(uri) == '{"ok": true}'


def test_create_object_storage_defaults_to_local(monkeypatch, tmp_path):
    monkeypatch.delenv("ZH_OBJECT_STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("ZH_OBJECT_STORAGE_ROOT", str(tmp_path / "objects"))

    storage = create_object_storage()

    assert isinstance(storage, LocalObjectStorage)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_object_storage.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement local storage**

Create `zhihu_fiction/app/services/object_storage.py`:

```python
"""Object storage abstraction for generated drama assets."""
from __future__ import annotations

import os
from pathlib import Path


class LocalObjectStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_text(self, key: str, content: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"local://{key}"

    def read_text(self, uri: str) -> str:
        if not uri.startswith("local://"):
            raise ValueError(f"Unsupported local object URI: {uri}")
        return (self.root / uri.removeprefix("local://")).read_text(encoding="utf-8")


def create_object_storage():
    backend = os.getenv("ZH_OBJECT_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalObjectStorage(Path(os.getenv("ZH_OBJECT_STORAGE_ROOT", "zhihu_fiction/data/objects")))
    if backend == "minio":
        raise RuntimeError("MinIO object storage backend is configured but not installed in this build")
    raise RuntimeError(f"Unsupported object storage backend: {backend}")
```

- [ ] **Step 4: Run storage tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_object_storage.py -q
```

Expected: PASS.

- [ ] **Step 5: Add package manifest write**

In `create_video_tasks_payload()` after the package output is created, write a manifest through local storage:

```python
storage = create_object_storage()
manifest_uri = storage.put_text(
    f"drama-video/{output_dir.name}/manifest.json",
    json.dumps({
        "story_path": story_path,
        "package_dir": str(output_dir),
        "jobs_path": str(jobs_path),
        "submitted_count": len(jobs),
    }, ensure_ascii=False),
)
```

Add `"manifest_uri": manifest_uri` to the returned payload.

- [ ] **Step 6: Add execution test assertion**

In `test_create_video_tasks_payload_submits_selected_shots`, assert:

```python
assert result["manifest_uri"].startswith("local://drama-video/")
```

- [ ] **Step 7: Run execution tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_object_storage.py zhihu_fiction/tests/test_drama_video_execution.py -q
```

Expected: all tests pass.

---

### Task 7: Convert DeepAgent Video Stage To One-Click Loop With Confirm Checkpoints

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_deepagent_flow.py`
- Modify: `zhihu_fiction/app/services/drama_video_runtime.py`
- Modify: `zhihu_fiction/app/routes/drama_video.py`
- Modify: `zhihu_fiction/static/video.html`
- Test: `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`

- [ ] **Step 1: Write flow test for auto-advance until confirmation**

Add this test to `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`:

```python
def test_deepagent_auto_loop_stops_at_confirmation_checkpoint(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = SimpleNamespace(workspace_repo=repo)

    result = start_deepagent_video_loop(
        deps,
        story_path="故事/小说正文.md",
        shot_limit=2,
        model_runner=lambda stage, context: f"{stage} draft",
        id_factory=lambda prefix: "deepagent_1",
    )

    session = repo.get_drama_session("deepagent_1")
    assert result["run_id"] == "deepagent_1"
    assert result["status"] == "awaiting_confirmation"
    assert session.pending_stage == "script"
    assert session.drafts["script"] == "script draft"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py::test_deepagent_auto_loop_stops_at_confirmation_checkpoint -q
```

Expected: FAIL because `start_deepagent_video_loop` does not exist.

- [ ] **Step 3: Implement loop entrypoint**

In `zhihu_fiction/app/services/drama_video_deepagent_flow.py`, add:

```python
def start_deepagent_video_loop(
    dependencies,
    story_path: str,
    shot_limit: int,
    *,
    model_runner,
    id_factory=default_video_run_id,
) -> dict:
    run_id = id_factory("drama")
    session = persist_session(
        dependencies,
        run_id=run_id,
        story_path=story_path,
        shot_limit=shot_limit,
        status="generating",
    )
    draft = model_runner("script", {"story_path": story_path, "shot_limit": shot_limit})
    session.drafts["script"] = draft
    session.pending_stage = "script"
    session.status = "awaiting_confirmation"
    dependencies.workspace_repo.save_drama_session(session)
    return {
        "run_id": run_id,
        "status": "awaiting_confirmation",
        "pending_stage": "script",
        "draft": draft,
    }
```

If `persist_session()` has a different signature, adapt the implementation to the existing helper while preserving the returned contract above.

- [ ] **Step 4: Run flow test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py::test_deepagent_auto_loop_stops_at_confirmation_checkpoint -q
```

Expected: PASS.

- [ ] **Step 5: Add API endpoint**

Add route:

```python
@router.post("/api/drama-video/deepagent/loop")
async def start_deepagent_video_loop(req: Request):
    payload = await req.json()
    deps = get_dependencies(req)
    return runtime.start_deepagent_video_loop(
        deps,
        get_state(req),
        str(payload.get("story_path") or ""),
        int(payload.get("shot_limit") or 1),
    )
```

- [ ] **Step 6: Add frontend one-click button**

In `video.html`, add a primary action:

```html
<button @click="startDeepAgentLoop()" :disabled="!selectedStory || deepAgentLoading">
  一键生成短剧流程
</button>
```

Add method:

```javascript
async startDeepAgentLoop() {
  if (!this.selectedStory) return;
  this.deepAgentLoading = true;
  try {
    const res = await fetch('/api/drama-video/deepagent/loop', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        story_path: this.selectedStory.path,
        shot_limit: this.shotLimit,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    this.deepAgentRunId = data.run_id;
    await this.loadDeepAgentSession(data.run_id);
  } finally {
    this.deepAgentLoading = false;
  }
},
```

- [ ] **Step 7: Run API/static tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_server_drama_video.py -q
```

Expected: all tests pass.

---

### Task 8: Add Redis And MinIO Configuration Documentation

**Files:**
- Modify: `zhihu_fiction/README.md`
- Modify: `.env.example` if present; otherwise create `zhihu_fiction/.env.example`
- Test: `zhihu_fiction/tests/test_server_app_factory.py`

- [ ] **Step 1: Write documentation contract test**

Add this test to `zhihu_fiction/tests/test_server_app_factory.py`:

```python
def test_video_infrastructure_env_documentation_exists():
    readme = Path("zhihu_fiction/README.md").read_text(encoding="utf-8")
    env_example = Path("zhihu_fiction/.env.example").read_text(encoding="utf-8")

    assert "ZH_VIDEO_QUEUE_BACKEND" in readme
    assert "ZH_OBJECT_STORAGE_BACKEND" in readme
    assert "MINIO_ENDPOINT" in env_example
    assert "REDIS_URL" in env_example
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_video_infrastructure_env_documentation_exists -q
```

Expected: FAIL until docs are updated.

- [ ] **Step 3: Update env example**

Create or update `zhihu_fiction/.env.example`:

```bash
EMBEDDING_API_KEY=
DASHSCOPE_API_KEY=
BAILIAN_API_KEY=
BAILIAN_VIDEO_MODEL=wanx2.1-t2v-turbo
ZH_VIDEO_PROVIDER=bailian
ZH_VIDEO_QUEUE_BACKEND=memory
REDIS_URL=redis://localhost:6379/0
ZH_OBJECT_STORAGE_BACKEND=local
ZH_OBJECT_STORAGE_ROOT=zhihu_fiction/data/objects
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=zhihu-fiction
ZH_WORKSPACE_BACKEND=jsonl
ZH_WORKSPACE_SQLITE_PATH=zhihu_fiction/data/workspace/workspace.sqlite3
```

- [ ] **Step 4: Update README infrastructure section**

Add a section to `zhihu_fiction/README.md`:

```markdown
## 短剧视频生产基础设施

默认开发环境使用本地内存队列、本地文件对象存储、JSONL workspace 持久化：

- `ZH_VIDEO_QUEUE_BACKEND=memory`
- `ZH_OBJECT_STORAGE_BACKEND=local`
- `ZH_WORKSPACE_BACKEND=jsonl`

生产环境可以逐步切换：

- Redis 队列：设置 `ZH_VIDEO_QUEUE_BACKEND=redis` 和 `REDIS_URL`
- MinIO 对象存储：设置 `ZH_OBJECT_STORAGE_BACKEND=minio`、`MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET`
- SQLite workspace：设置 `ZH_WORKSPACE_BACKEND=sqlite` 和 `ZH_WORKSPACE_SQLITE_PATH`

当前视频模型默认使用阿里云百炼/DashScope，可用 `EMBEDDING_API_KEY`、`DASHSCOPE_API_KEY` 或 `BAILIAN_API_KEY` 提供 API Key。
```

- [ ] **Step 5: Run documentation test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py::test_video_infrastructure_env_documentation_exists -q
```

Expected: PASS.

---

### Task 9: Full Verification And Browser QA

**Files:**
- No production edits unless tests or QA reveal defects.

- [ ] **Step 1: Run full backend tests**

Run:

```bash
python -m pytest zhihu_fiction/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Start local server**

Run:

```bash
python -m uvicorn zhihu_fiction.server:app --port 8023
```

Expected: server starts without import errors.

- [ ] **Step 3: Browser check video workspace**

Open:

```text
http://127.0.0.1:8023/video
```

Verify:

- The main video workspace renders.
- Selecting a story opens the single-work workspace.
- The unified task timeline is visible.
- Existing DeepAgent controls still render.
- Refresh/retry buttons are still present.
- No text overlap appears at desktop width.

- [ ] **Step 4: Browser check mobile width**

Set viewport around 390px wide and verify:

- Timeline rows wrap cleanly.
- Buttons do not overflow.
- Workspace panels remain readable.

- [ ] **Step 5: Stop server**

Stop the uvicorn process cleanly from the terminal session.

---

## Execution Order

1. Task 1: job listing API.
2. Task 2: frontend timeline.
3. Task 3: refresh job persistence.
4. Task 4: stale job recovery.
5. Task 5: queue backend interface.
6. Task 6: object storage interface.
7. Task 7: one-click LoopAgent flow.
8. Task 8: infrastructure docs.
9. Task 9: full verification and browser QA.

## Self-Review

- The plan covers unified job visibility, frontend task timeline, refresh/retry/generate job unification, recovery, queue abstraction, object storage abstraction, LoopAgent one-click flow, Redis/MinIO configuration, and final QA.
- No task requires real Aliyun Bailian, Redis, or MinIO calls; tests use local fakes or local filesystem.
- The plan keeps local JSONL/SQLite and in-memory behavior as the default so existing development workflows continue to work.
- Each implementation task starts with a failing test and includes exact verification commands.

# Industrialized Short Drama Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V1 local single-machine small-team short drama factory described in `zhihu_fiction/docs/superpowers/specs/2026-06-15-industrialized-short-drama-factory-design.md`.

**Architecture:** Keep the current FastAPI + workspace repository architecture. Add the missing production contracts around consistency profiles, operation logs, stage state, recovery visibility, cost explanations, and single-project workspace UX without rewriting the existing DeepAgent/video pipeline. SQLite-backed stores remain the production metadata path; JSONL remains compatibility storage.

**Tech Stack:** Python dataclasses, FastAPI, pytest, SQLite/JSONL repository abstraction, static HTML/CSS/JS, existing DeepAgent drama-video services, local filesystem object storage.

---

## File Structure Map

### Existing Files To Modify

- `zhihu_fiction/workspace/models.py`
  - Add `ConsistencyProfile`, `OperationLog`, stage state constants, and any missing fields needed by tests.
- `zhihu_fiction/workspace/repositories.py`
  - Add stores and repository methods for consistency profiles and operation logs.
  - Keep existing `SQLiteStore` and `JsonlStore` behavior.
- `zhihu_fiction/app/services/drama_video_deepagent_flow.py`
  - Persist stage state transitions and operation logs around start, draft, confirm, revise, and video start.
  - Feed consistency profile references into later stages.
- `zhihu_fiction/app/services/drama_video_sessions.py`
  - Centralize session/spec persistence helpers for stage state, stage versions, and consistency updates.
- `zhihu_fiction/app/services/drama_video_stage_generation.py`
  - Include consistency context in stage generation input.
  - Emit structured consistency metadata for generated stages.
- `zhihu_fiction/app/services/drama_video_recovery.py`
  - Extend recovery summaries to expose pending/running sessions and stuck tasks.
- `zhihu_fiction/app/routes/drama_video.py`
  - Add or extend endpoints for stage revision, consistency profile, operation logs, and recovery status.
- `zhihu_fiction/app/routes/projects.py`
  - Include consistency profile, operation log, stage status summary, and actionable next step in the project workspace payload.
- `zhihu_fiction/app/routes/costs.py`
  - Add explicit covered-estimate explanation fields to cost summary.
- `zhihu_fiction/static/video.html`
  - Surface stage state, consistency profile, human-loop dialog, task status, and cost explanations in the single-project video workspace.
- `zhihu_fiction/static/index.html`
  - Keep project list links and status badges aligned with the new workspace payload.
- `zhihu_fiction/README.md`
  - Document V1 local production startup and main workflow.
- `zhihu_fiction/.env.example`
  - Ensure local SQLite, storage, budget, DeepSeek, and Bailian settings are documented.

### Existing Tests To Extend

- `zhihu_fiction/tests/test_workspace_models.py`
- `zhihu_fiction/tests/test_workspace_repositories.py`
- `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`
- `zhihu_fiction/tests/test_drama_video_sessions.py`
- `zhihu_fiction/tests/test_drama_video_stage_generation.py`
- `zhihu_fiction/tests/test_drama_video_recovery.py`
- `zhihu_fiction/tests/test_server_drama_video.py`
- `zhihu_fiction/tests/test_project_workspace_api.py`
- `zhihu_fiction/tests/test_cost_center.py`
- `zhihu_fiction/tests/test_static_video_workspace.py`
- `zhihu_fiction/tests/test_static_project_dashboard.py`
- `zhihu_fiction/tests/test_release_artifacts.py`

### New Files To Create

- `zhihu_fiction/tests/test_operation_logs.py`
  - Focused tests for operation log persistence and project filtering.
- `zhihu_fiction/tests/test_consistency_profiles.py`
  - Focused tests for consistency profile model, repository behavior, and stage reference updates.
- `zhihu_fiction/RELEASE_CHECKLIST.md`
  - V1 release gate checklist.

---

## Task 1: Add Consistency Profile And Operation Log Data Contracts

**Files:**
- Modify: `zhihu_fiction/workspace/models.py`
- Modify: `zhihu_fiction/workspace/repositories.py`
- Test: `zhihu_fiction/tests/test_consistency_profiles.py`
- Test: `zhihu_fiction/tests/test_operation_logs.py`
- Test: `zhihu_fiction/tests/test_workspace_repositories.py`

- [ ] **Step 1: Write failing model tests for consistency profiles**

Create `zhihu_fiction/tests/test_consistency_profiles.py`:

```python
from zhihu_fiction.workspace.models import ConsistencyProfile


def test_consistency_profile_round_trips_structured_constraints():
    profile = ConsistencyProfile(
        id="consistency_1",
        project_id="project_1",
        session_id="deepagent_1",
        source_version_ids=["version_script", "version_style"],
        characters=[{
            "id": "char_hero",
            "name": "林晚",
            "appearance": "黑色短发，白衬衫",
            "forbidden_changes": ["不能突然变成长发"],
        }],
        world_facts=[{"id": "fact_city", "text": "故事发生在运城"}],
        visual_style={"palette": "冷暖对比", "camera": "手持纪实"},
        narrative_constraints=["女主不能提前知道真相"],
        asset_bindings={"char_hero": ["asset_ref_1"]},
        created_at="2026-06-15T01:00:00+00:00",
        updated_at="2026-06-15T01:01:00+00:00",
    )

    loaded = ConsistencyProfile.from_dict(profile.to_dict())

    assert loaded == profile
    assert loaded.characters[0]["name"] == "林晚"
    assert loaded.asset_bindings == {"char_hero": ["asset_ref_1"]}
```

- [ ] **Step 2: Write failing model tests for operation logs**

Create `zhihu_fiction/tests/test_operation_logs.py`:

```python
from zhihu_fiction.workspace.models import OperationLog


def test_operation_log_round_trips_actor_target_and_metadata():
    log = OperationLog(
        id="op_1",
        project_id="project_1",
        actor="human",
        action="confirm_stage",
        target_kind="stage_version",
        target_id="version_1",
        message="确认剧本阶段",
        metadata={"stage": "script", "run_id": "deepagent_1"},
        created_at="2026-06-15T01:00:00+00:00",
    )

    loaded = OperationLog.from_dict(log.to_dict())

    assert loaded == log
    assert loaded.metadata["stage"] == "script"
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_consistency_profiles.py zhihu_fiction/tests/test_operation_logs.py -q
```

Expected: fail with `ImportError` or `AttributeError` because `ConsistencyProfile` and `OperationLog` do not exist yet.

- [ ] **Step 4: Add dataclasses and constants**

Modify `zhihu_fiction/workspace/models.py`:

```python
OPERATION_ACTIONS = {
    "start_session",
    "generate_stage",
    "confirm_stage",
    "request_revision",
    "retry_task",
    "cancel_task",
    "recover_task",
    "submit_video",
    "confirm_cost",
    "export_package",
}
OPERATION_TARGET_KINDS = {
    "project",
    "drama_session",
    "stage_version",
    "consistency_profile",
    "video_run",
    "video_job",
    "asset",
    "cost_ledger",
}
```

Add dataclasses near the other workspace models:

```python
@dataclass
class ConsistencyProfile:
    id: str
    project_id: str
    session_id: str
    source_version_ids: list[str] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    world_facts: list[dict] = field(default_factory=list)
    visual_style: dict = field(default_factory=dict)
    narrative_constraints: list[str] = field(default_factory=list)
    asset_bindings: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("ConsistencyProfile.project_id is required")
        if not self.session_id:
            raise ValueError("ConsistencyProfile.session_id is required")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConsistencyProfile":
        return cls(**data)
```

```python
@dataclass
class OperationLog:
    id: str
    project_id: str
    actor: str
    action: str
    target_kind: str
    target_id: str
    message: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("OperationLog.project_id is required")
        if not self.actor:
            raise ValueError("OperationLog.actor is required")
        _validate_choice("OperationLog.action", self.action, OPERATION_ACTIONS)
        _validate_choice("OperationLog.target_kind", self.target_kind, OPERATION_TARGET_KINDS)
        if not self.target_id:
            raise ValueError("OperationLog.target_id is required")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OperationLog":
        return cls(**data)
```

- [ ] **Step 5: Run model tests and verify they pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_consistency_profiles.py zhihu_fiction/tests/test_operation_logs.py -q
```

Expected: both tests pass.

- [ ] **Step 6: Write failing repository tests**

Append to `zhihu_fiction/tests/test_consistency_profiles.py`:

```python
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_repository_lists_latest_consistency_profile_for_session(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    repo.save_consistency_profile(ConsistencyProfile(
        id="consistency_old",
        project_id="project_1",
        session_id="deepagent_1",
        updated_at="2026-06-15T01:00:00+00:00",
    ))
    latest = repo.save_consistency_profile(ConsistencyProfile(
        id="consistency_new",
        project_id="project_1",
        session_id="deepagent_1",
        updated_at="2026-06-15T02:00:00+00:00",
        narrative_constraints=["女主不能提前知道真相"],
    ))
    repo.save_consistency_profile(ConsistencyProfile(
        id="consistency_other",
        project_id="project_2",
        session_id="deepagent_other",
        updated_at="2026-06-15T03:00:00+00:00",
    ))

    assert repo.list_consistency_profiles("project_1") == [latest, repo.get_consistency_profile("consistency_old")]
    assert repo.latest_consistency_profile_for_session("deepagent_1") == latest
```

Append to `zhihu_fiction/tests/test_operation_logs.py`:

```python
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_repository_lists_operation_logs_by_project_newest_first(tmp_path):
    repo = WorkspaceRepository(tmp_path)
    old_log = repo.save_operation_log(OperationLog(
        id="op_old",
        project_id="project_1",
        actor="human",
        action="start_session",
        target_kind="drama_session",
        target_id="deepagent_1",
        created_at="2026-06-15T01:00:00+00:00",
    ))
    new_log = repo.save_operation_log(OperationLog(
        id="op_new",
        project_id="project_1",
        actor="human",
        action="confirm_stage",
        target_kind="stage_version",
        target_id="version_1",
        created_at="2026-06-15T02:00:00+00:00",
    ))
    repo.save_operation_log(OperationLog(
        id="op_other",
        project_id="project_2",
        actor="human",
        action="start_session",
        target_kind="drama_session",
        target_id="deepagent_other",
        created_at="2026-06-15T03:00:00+00:00",
    ))

    assert repo.list_operation_logs("project_1") == [new_log, old_log]
```

- [ ] **Step 7: Run repository tests and verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_consistency_profiles.py zhihu_fiction/tests/test_operation_logs.py -q
```

Expected: fail because repository methods are missing.

- [ ] **Step 8: Add repository stores and methods**

Modify imports in `zhihu_fiction/workspace/repositories.py`:

```python
from .models import (
    ConsistencyProfile,
    OperationLog,
    ...
)
```

In `WorkspaceRepository.__init__`, add:

```python
self.consistency_profiles = self._store(
    "consistency_profiles",
    ConsistencyProfile.from_dict,
)
self.operation_logs = self._store(
    "operation_logs",
    OperationLog.from_dict,
)
```

Add methods:

```python
def save_consistency_profile(self, profile: ConsistencyProfile) -> ConsistencyProfile:
    return self.consistency_profiles.save(profile)

def get_consistency_profile(self, profile_id: str) -> ConsistencyProfile | None:
    return self.consistency_profiles.get(profile_id)

def list_consistency_profiles(self, project_id: str | None = None) -> list[ConsistencyProfile]:
    profiles = self.consistency_profiles.list()
    if project_id is not None:
        profiles = [profile for profile in profiles if profile.project_id == project_id]
    return sorted(profiles, key=lambda item: item.updated_at, reverse=True)

def latest_consistency_profile_for_session(self, session_id: str) -> ConsistencyProfile | None:
    profiles = [
        profile
        for profile in self.consistency_profiles.list()
        if profile.session_id == session_id
    ]
    if not profiles:
        return None
    return sorted(profiles, key=lambda item: item.updated_at, reverse=True)[0]

def save_operation_log(self, log: OperationLog) -> OperationLog:
    return self.operation_logs.save(log)

def list_operation_logs(self, project_id: str | None = None) -> list[OperationLog]:
    logs = self.operation_logs.list()
    if project_id is not None:
        logs = [log for log in logs if log.project_id == project_id]
    return sorted(logs, key=lambda item: item.created_at, reverse=True)
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_consistency_profiles.py zhihu_fiction/tests/test_operation_logs.py zhihu_fiction/tests/test_workspace_repositories.py -q
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add zhihu_fiction/workspace/models.py zhihu_fiction/workspace/repositories.py zhihu_fiction/tests/test_consistency_profiles.py zhihu_fiction/tests/test_operation_logs.py zhihu_fiction/tests/test_workspace_repositories.py
git commit -m "feat: add consistency profiles and operation logs"
```

---

## Task 2: Record Operation Logs For DeepAgent Stage Actions

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_sessions.py`
- Modify: `zhihu_fiction/app/services/drama_video_deepagent_flow.py`
- Modify: `zhihu_fiction/app/routes/projects.py`
- Test: `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`
- Test: `zhihu_fiction/tests/test_project_workspace_api.py`

- [ ] **Step 1: Write failing test for start and confirm operation logs**

Append to `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`:

```python
def test_deepagent_start_and_confirm_record_operation_logs(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = AppDependencies(workspace_repo=repo)
    state = AppState()

    result = start_deepagent_run(
        deps,
        state,
        story_path="output/story/小说正文.md",
        project_id="project_1",
        shot_limit=1,
        stage_drafts={},
        id_factory=lambda prefix: "deepagent_logs",
    )
    confirm_stage(
        deps,
        state,
        "deepagent_logs",
        "script",
        "第一版剧本",
        video_starter=lambda *args, **kwargs: "video_1",
    )

    logs = repo.list_operation_logs("project_1")
    assert [log.action for log in logs] == ["confirm_stage", "start_session"]
    assert logs[0].metadata["stage"] == "script"
    assert logs[0].target_kind == "stage_version"
    assert logs[1].target_kind == "drama_session"
```

If this test file uses different fixture names, import from existing tests:

```python
from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.state import AppState
from zhihu_fiction.app.services.drama_video_deepagent_flow import start_deepagent_run, confirm_stage
from zhihu_fiction.workspace.repositories import WorkspaceRepository
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py -q -k operation_logs
```

Expected: fail because operation logs are not recorded.

- [ ] **Step 3: Add helper to record logs**

In `zhihu_fiction/app/services/drama_video_sessions.py`, add:

```python
from ...workspace.models import OperationLog, new_id
```

Add helper:

```python
def record_operation_log(
    dependencies,
    *,
    project_id: str,
    actor: str,
    action: str,
    target_kind: str,
    target_id: str,
    message: str = "",
    metadata: dict | None = None,
) -> OperationLog | None:
    if not project_id:
        return None
    return dependencies.workspace_repo.save_operation_log(OperationLog(
        id=new_id("op"),
        project_id=project_id,
        actor=actor or "human",
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        message=message,
        metadata=metadata or {},
    ))
```

- [ ] **Step 4: Log DeepAgent start**

In `start_deepagent_run()` and `start_deepagent_video_loop()` after `store_session_spec(...)`, call:

```python
record_operation_log(
    dependencies,
    project_id=project_id,
    actor="system",
    action="start_session",
    target_kind="drama_session",
    target_id=run_id,
    message="短剧生产会话已启动",
    metadata={"story_path": story_path, "shot_limit": shot_limit},
)
```

- [ ] **Step 5: Log stage confirmation**

In `confirm_stage()`, capture the version returned by `record_stage_version()`:

```python
version = record_stage_version(
    dependencies,
    run_id,
    stage,
    content,
    "confirmation",
    project_id=spec.get("project_id") or "",
)
record_operation_log(
    dependencies,
    project_id=spec.get("project_id") or "",
    actor="human",
    action="confirm_stage",
    target_kind="stage_version",
    target_id=version.id,
    message=f"确认短剧阶段：{stage}",
    metadata={"run_id": run_id, "stage": stage},
)
```

- [ ] **Step 6: Run focused test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py -q -k operation_logs
```

Expected: pass.

- [ ] **Step 7: Write failing project payload test for operation logs**

Append to `zhihu_fiction/tests/test_project_workspace_api.py`:

```python
def test_project_workspace_payload_includes_operation_logs(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    project = repo.save_project(Project(id="project_1", title="项目"))
    repo.save_operation_log(OperationLog(
        id="op_1",
        project_id=project.id,
        actor="human",
        action="confirm_stage",
        target_kind="stage_version",
        target_id="version_1",
        message="确认剧本",
        created_at="2026-06-15T01:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["operation_logs"][0]["id"] == "op_1"
```

Required imports if missing:

```python
from fastapi.testclient import TestClient
from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.workspace.models import OperationLog, Project
from zhihu_fiction.workspace.repositories import WorkspaceRepository
```

- [ ] **Step 8: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_project_workspace_api.py -q -k operation_logs
```

Expected: fail because `operation_logs` is absent from payload.

- [ ] **Step 9: Add operation logs to workspace payload**

In `_workspace_payload()` in `zhihu_fiction/app/routes/projects.py`, add:

```python
"operation_logs": [
    log.to_dict() for log in repo.list_operation_logs(project_id)
],
```

- [ ] **Step 10: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_project_workspace_api.py -q
```

Expected: pass.

- [ ] **Step 11: Commit**

```bash
git add zhihu_fiction/app/services/drama_video_sessions.py zhihu_fiction/app/services/drama_video_deepagent_flow.py zhihu_fiction/app/routes/projects.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_project_workspace_api.py
git commit -m "feat: log deepagent production actions"
```

---

## Task 3: Generate And Persist Consistency Profiles

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_sessions.py`
- Modify: `zhihu_fiction/app/services/drama_video_deepagent_flow.py`
- Modify: `zhihu_fiction/app/services/drama_video_stage_generation.py`
- Modify: `zhihu_fiction/app/routes/projects.py`
- Test: `zhihu_fiction/tests/test_drama_video_sessions.py`
- Test: `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`
- Test: `zhihu_fiction/tests/test_project_workspace_api.py`

- [ ] **Step 1: Write failing test for consistency profile creation after stage confirmation**

Append to `zhihu_fiction/tests/test_drama_video_deepagent_flow.py`:

```python
def test_confirm_stage_updates_consistency_profile(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    deps = AppDependencies(workspace_repo=repo)
    state = AppState()
    start_deepagent_run(
        deps,
        state,
        story_path="output/story/小说正文.md",
        project_id="project_1",
        shot_limit=1,
        stage_drafts={},
        id_factory=lambda prefix: "deepagent_consistency",
    )

    confirm_stage(
        deps,
        state,
        "deepagent_consistency",
        "script",
        "角色：林晚。地点：运城。限制：女主不能提前知道真相。",
        video_starter=lambda *args, **kwargs: "video_1",
    )

    profile = repo.latest_consistency_profile_for_session("deepagent_consistency")
    assert profile is not None
    assert profile.project_id == "project_1"
    assert "女主不能提前知道真相" in profile.narrative_constraints
    assert profile.source_version_ids
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py -q -k consistency_profile
```

Expected: fail because confirmations do not update consistency profiles.

- [ ] **Step 3: Add deterministic extraction helper**

In `zhihu_fiction/app/services/drama_video_sessions.py`, add:

```python
from ...workspace.models import ConsistencyProfile
```

Add helper:

```python
def update_consistency_profile_from_stage(
    dependencies,
    *,
    project_id: str,
    session_id: str,
    stage: str,
    content: str,
    source_version_id: str,
) -> ConsistencyProfile | None:
    if not project_id:
        return None
    previous = dependencies.workspace_repo.latest_consistency_profile_for_session(session_id)
    source_version_ids = list(getattr(previous, "source_version_ids", []) or [])
    if source_version_id and source_version_id not in source_version_ids:
        source_version_ids.append(source_version_id)
    constraints = list(getattr(previous, "narrative_constraints", []) or [])
    for marker in ("限制：", "约束：", "不能"):
        if marker in content:
            extracted = content.split(marker, 1)[1].strip().split("\n", 1)[0].strip(" 。")
            if extracted and extracted not in constraints:
                constraints.append(extracted)
            break
    world_facts = list(getattr(previous, "world_facts", []) or [])
    if "地点：" in content:
        place = content.split("地点：", 1)[1].strip().split("。", 1)[0]
        fact = {"id": f"fact_{len(world_facts) + 1}", "text": f"地点：{place}"}
        if fact not in world_facts:
            world_facts.append(fact)
    characters = list(getattr(previous, "characters", []) or [])
    if "角色：" in content:
        name = content.split("角色：", 1)[1].strip().split("。", 1)[0]
        if name and not any(item.get("name") == name for item in characters):
            characters.append({"id": f"char_{len(characters) + 1}", "name": name})
    profile_id = previous.id if previous is not None else new_id("consistency")
    created_at = previous.created_at if previous is not None else utc_now_iso()
    return dependencies.workspace_repo.save_consistency_profile(ConsistencyProfile(
        id=profile_id,
        project_id=project_id,
        session_id=session_id,
        source_version_ids=source_version_ids,
        characters=characters,
        world_facts=world_facts,
        visual_style=getattr(previous, "visual_style", {}) or {},
        narrative_constraints=constraints,
        asset_bindings=getattr(previous, "asset_bindings", {}) or {},
        created_at=created_at,
        updated_at=utc_now_iso(),
    ))
```

If `utc_now_iso` is not imported, import it from `zhihu_fiction.workspace.models`.

- [ ] **Step 4: Call helper from confirm_stage**

In `confirm_stage()`, after confirmation `record_stage_version()` returns `version`, call:

```python
update_consistency_profile_from_stage(
    dependencies,
    project_id=spec.get("project_id") or "",
    session_id=run_id,
    stage=stage,
    content=content,
    source_version_id=version.id,
)
```

- [ ] **Step 5: Run focused test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py -q -k consistency_profile
```

Expected: pass.

- [ ] **Step 6: Write failing project payload test**

Append to `zhihu_fiction/tests/test_project_workspace_api.py`:

```python
def test_project_workspace_payload_includes_latest_consistency_profile(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    project = repo.save_project(Project(id="project_1", title="项目"))
    repo.save_consistency_profile(ConsistencyProfile(
        id="consistency_1",
        project_id=project.id,
        session_id="deepagent_1",
        narrative_constraints=["女主不能提前知道真相"],
        updated_at="2026-06-15T01:00:00+00:00",
    ))
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/projects/project_1")

    assert response.status_code == 200
    assert response.json()["consistency_profiles"][0]["id"] == "consistency_1"
    assert response.json()["latest_consistency_profile"]["narrative_constraints"] == ["女主不能提前知道真相"]
```

- [ ] **Step 7: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_project_workspace_api.py -q -k consistency_profile
```

Expected: fail because payload does not include consistency profiles.

- [ ] **Step 8: Add consistency profile payload**

In `_workspace_payload()` in `zhihu_fiction/app/routes/projects.py`, compute:

```python
consistency_profiles = repo.list_consistency_profiles(project_id)
```

Return:

```python
"consistency_profiles": [profile.to_dict() for profile in consistency_profiles],
"latest_consistency_profile": consistency_profiles[0].to_dict() if consistency_profiles else None,
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_project_workspace_api.py -q -k "consistency_profile or consistency"
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add zhihu_fiction/app/services/drama_video_sessions.py zhihu_fiction/app/services/drama_video_deepagent_flow.py zhihu_fiction/app/services/drama_video_stage_generation.py zhihu_fiction/app/routes/projects.py zhihu_fiction/tests/test_drama_video_sessions.py zhihu_fiction/tests/test_drama_video_deepagent_flow.py zhihu_fiction/tests/test_project_workspace_api.py
git commit -m "feat: persist drama consistency profiles"
```

---

## Task 4: Expose Effective Cost Coverage In Cost Center

**Files:**
- Modify: `zhihu_fiction/workspace/repositories.py`
- Modify: `zhihu_fiction/app/routes/costs.py`
- Test: `zhihu_fiction/tests/test_workspace_repositories.py`
- Test: `zhihu_fiction/tests/test_cost_center.py`

- [ ] **Step 1: Write failing repository test for covered estimates**

Append to `zhihu_fiction/tests/test_workspace_repositories.py`:

```python
def test_cost_ledger_covered_video_estimates_for_day(tmp_path):
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

    covered = repo.list_covered_video_estimate_entries_for_day("2026-06-15")

    assert covered == [estimate]
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_repositories.py -q -k covered_video_estimates
```

Expected: fail because method is missing.

- [ ] **Step 3: Add repository method**

In `zhihu_fiction/workspace/repositories.py`, add:

```python
def list_covered_video_estimate_entries_for_day(
    self,
    date_iso: str,
    project_id: str | None = None,
) -> list[CostLedgerEntry]:
    day = str(date_iso or "")[:10]
    if not day:
        return []
    entries = [
        entry
        for entry in self.list_cost_ledger_entries(project_id=project_id)
        if str(entry.created_at or "")[:10] == day
    ]
    runs_with_provider_actual = {
        entry.run_id
        for entry in entries
        if not entry.estimated and str(entry.source or "").startswith("provider_")
    }
    return [
        entry
        for entry in entries
        if (
            entry.run_id in runs_with_provider_actual
            and entry.estimated
            and entry.source in {"video_run_estimate", "video_retry_estimate"}
        )
    ]
```

- [ ] **Step 4: Run repository test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_workspace_repositories.py -q -k "covered_video_estimates or cost_ledger"
```

Expected: pass.

- [ ] **Step 5: Write failing cost summary API test**

Append to `zhihu_fiction/tests/test_cost_center.py`:

```python
def test_cost_center_summary_explains_covered_video_estimates(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
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
    client = TestClient(create_app(dependencies=AppDependencies(workspace_repo=repo)))

    response = client.get("/api/costs/summary", params={"date": "2026-06-15"})

    assert response.status_code == 200
    data = response.json()
    assert data["covered_estimate_total_cny"] == 3.0
    assert data["covered_estimate_count"] == 1
    assert data["covered_estimates"][0]["id"] == "cost_video_run_estimate_video_1"
```

- [ ] **Step 6: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_cost_center.py -q -k covered_video_estimates
```

Expected: fail because fields are absent.

- [ ] **Step 7: Add coverage fields to cost summary**

In `get_cost_summary()` in `zhihu_fiction/app/routes/costs.py`, add:

```python
covered_estimates = repo.list_covered_video_estimate_entries_for_day(
    day,
    project_id=project_id,
)
covered_estimate_total = _money(_sum_amounts(covered_estimates))
```

Return:

```python
"covered_estimate_total_cny": covered_estimate_total,
"covered_estimate_count": len(covered_estimates),
"covered_estimates": [entry.to_dict() for entry in covered_estimates],
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_cost_center.py zhihu_fiction/tests/test_workspace_repositories.py -q -k "cost_center or cost_ledger or covered"
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add zhihu_fiction/workspace/repositories.py zhihu_fiction/app/routes/costs.py zhihu_fiction/tests/test_workspace_repositories.py zhihu_fiction/tests/test_cost_center.py
git commit -m "feat: explain covered video cost estimates"
```

---

## Task 5: Add Recovery Visibility For Stuck Sessions And Jobs

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_recovery.py`
- Modify: `zhihu_fiction/app/routes/drama_video.py`
- Test: `zhihu_fiction/tests/test_drama_video_recovery.py`
- Test: `zhihu_fiction/tests/test_server_drama_video.py`

- [ ] **Step 1: Write failing recovery summary test**

Append to `zhihu_fiction/tests/test_drama_video_recovery.py`:

```python
def test_recovery_summary_reports_awaiting_and_running_sessions(tmp_path):
    repo = WorkspaceRepository(tmp_path / "workspace")
    repo.save_drama_session(DramaProjectSession(
        id="deepagent_waiting",
        project_id="project_1",
        story_path="story.md",
        status="awaiting_confirmation",
        pending_stage="script",
        updated_at="2026-06-15T01:00:00+00:00",
    ))
    repo.save_drama_video_job(DramaVideoJob(
        id="job_running",
        kind="generate_video",
        run_id="video_1",
        status="running",
        shot_id="shot_1",
        updated_at="2026-06-15T01:01:00+00:00",
    ))

    summary = drama_video_recovery_summary(repo)

    assert summary["awaiting_confirmation_sessions"][0]["id"] == "deepagent_waiting"
    assert summary["running_jobs"][0]["id"] == "job_running"
```

If the module exposes a different function, add a new function named `drama_video_recovery_summary(repo)` and test that.

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_recovery.py -q -k recovery_summary_reports
```

Expected: fail because the summary does not expose these fields.

- [ ] **Step 3: Implement recovery summary**

In `zhihu_fiction/app/services/drama_video_recovery.py`, add:

```python
def drama_video_recovery_summary(repo) -> dict:
    sessions = repo.list_drama_sessions()
    jobs = repo.list_drama_video_jobs()
    awaiting = [
        session.to_dict()
        for session in sessions
        if session.status == "awaiting_confirmation"
    ]
    generating = [
        session.to_dict()
        for session in sessions
        if session.status == "generating"
    ]
    running_jobs = [
        job.to_dict()
        for job in jobs
        if job.status in {"queued", "running"}
    ]
    failed_jobs = [
        job.to_dict()
        for job in jobs
        if job.status == "failed"
    ]
    return {
        "awaiting_confirmation_sessions": awaiting,
        "generating_sessions": generating,
        "running_jobs": running_jobs,
        "failed_jobs": failed_jobs,
        "needs_attention_count": len(awaiting) + len(generating) + len(failed_jobs),
    }
```

- [ ] **Step 4: Run recovery test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_recovery.py -q -k recovery_summary_reports
```

Expected: pass.

- [ ] **Step 5: Write failing route test**

Append to `zhihu_fiction/tests/test_server_drama_video.py`:

```python
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
```

- [ ] **Step 6: Run route test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_drama_video.py -q -k recovery_endpoint_reports
```

Expected: fail because endpoint is absent or does not include fields.

- [ ] **Step 7: Add recovery endpoint**

In `zhihu_fiction/app/routes/drama_video.py`, import:

```python
from ..services.drama_video_recovery import drama_video_recovery_summary
```

Add route:

```python
@router.get("/api/drama-video/recovery")
async def get_drama_video_recovery(req: Request):
    repo = req.app.state.dependencies.workspace_repo
    return drama_video_recovery_summary(repo)
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_recovery.py zhihu_fiction/tests/test_server_drama_video.py -q -k "recovery"
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add zhihu_fiction/app/services/drama_video_recovery.py zhihu_fiction/app/routes/drama_video.py zhihu_fiction/tests/test_drama_video_recovery.py zhihu_fiction/tests/test_server_drama_video.py
git commit -m "feat: expose drama video recovery state"
```

---

## Task 6: Upgrade Single-Project Workspace Payload And Static UI

**Files:**
- Modify: `zhihu_fiction/app/routes/projects.py`
- Modify: `zhihu_fiction/static/video.html`
- Modify: `zhihu_fiction/static/index.html`
- Test: `zhihu_fiction/tests/test_project_workspace_api.py`
- Test: `zhihu_fiction/tests/test_static_video_workspace.py`
- Test: `zhihu_fiction/tests/test_static_project_dashboard.py`

- [ ] **Step 1: Write failing API test for actionable next step**

Append to `zhihu_fiction/tests/test_project_workspace_api.py`:

```python
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
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_project_workspace_api.py -q -k next_action
```

Expected: fail because fields are absent.

- [ ] **Step 3: Implement next action helper**

In `zhihu_fiction/app/routes/projects.py`, add:

```python
def _project_stage_summary(drama_sessions: list[dict]) -> dict:
    if not drama_sessions:
        return {"pending_stage": "", "status": "not_started"}
    session = drama_sessions[0]
    return {
        "pending_stage": session.get("pending_stage") or "",
        "status": session.get("status") or "",
        "session_id": session.get("id") or "",
    }


def _project_next_action(stage_summary: dict) -> dict:
    status = stage_summary.get("status") or ""
    stage = stage_summary.get("pending_stage") or ""
    session_id = stage_summary.get("session_id") or ""
    if status == "awaiting_confirmation" and stage and session_id:
        return {
            "kind": "confirm_stage",
            "label": f"确认 {stage} 阶段",
            "target_id": session_id,
            "stage": stage,
        }
    if status in {"generating", "running"}:
        return {
            "kind": "wait",
            "label": "等待生成完成",
            "target_id": session_id,
            "stage": stage,
        }
    return {
        "kind": "none",
        "label": "暂无待处理动作",
        "target_id": session_id,
        "stage": stage,
    }
```

In `_workspace_payload()`:

```python
stage_summary = _project_stage_summary(drama_sessions)
```

Return:

```python
"stage_summary": stage_summary,
"next_action": _project_next_action(stage_summary),
```

- [ ] **Step 4: Run API test**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_project_workspace_api.py -q -k next_action
```

Expected: pass.

- [ ] **Step 5: Write failing static UI tests**

Append to `zhihu_fiction/tests/test_static_video_workspace.py`:

```python
def test_video_workspace_mentions_consistency_and_human_loop_controls():
    html = Path("zhihu_fiction/static/video.html").read_text(encoding="utf-8")

    assert "一致性档案" in html
    assert "确认并继续" in html
    assert "要求修改" in html
    assert "操作日志" in html
    assert "成本覆盖" in html
```

Append to `zhihu_fiction/tests/test_static_project_dashboard.py`:

```python
def test_project_dashboard_links_to_short_drama_workspace_and_next_action():
    html = Path("zhihu_fiction/static/index.html").read_text(encoding="utf-8")

    assert "next_action" in html
    assert "/video" in html
    assert "待确认" in html
```

- [ ] **Step 6: Run static tests and verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_static_video_workspace.py zhihu_fiction/tests/test_static_project_dashboard.py -q
```

Expected: fail until HTML contains the required markers.

- [ ] **Step 7: Update `video.html`**

In `zhihu_fiction/static/video.html`, add visible sections or existing panel labels:

```html
<section class="panel" id="consistency-panel">
  <h2>一致性档案</h2>
  <div id="consistencyProfile"></div>
</section>

<section class="panel" id="human-loop-panel">
  <h2>阶段确认</h2>
  <textarea id="revisionInstruction" placeholder="输入修改意见"></textarea>
  <button id="confirmStageButton">确认并继续</button>
  <button id="requestRevisionButton">要求修改</button>
</section>

<section class="panel" id="operation-log-panel">
  <h2>操作日志</h2>
  <div id="operationLogs"></div>
</section>

<section class="panel" id="cost-coverage-panel">
  <h2>成本覆盖</h2>
  <div id="costCoverage"></div>
</section>
```

Wire these elements to the existing project payload fetch if that code already exists. If not, render empty states:

```javascript
function renderConsistencyProfile(profile) {
  const target = document.getElementById('consistencyProfile');
  if (!target) return;
  if (!profile) {
    target.textContent = '暂无一致性档案';
    return;
  }
  target.textContent = JSON.stringify(profile, null, 2);
}
```

- [ ] **Step 8: Update `index.html`**

Ensure project cards or rows include `next_action` rendering and a link to `/video`:

```javascript
const nextAction = project.next_action || {};
const actionText = nextAction.label || '暂无待处理动作';
```

Ensure visible text includes:

```html
<span>待确认</span>
```

- [ ] **Step 9: Run focused UI/API tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_project_workspace_api.py zhihu_fiction/tests/test_static_video_workspace.py zhihu_fiction/tests/test_static_project_dashboard.py -q
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add zhihu_fiction/app/routes/projects.py zhihu_fiction/static/video.html zhihu_fiction/static/index.html zhihu_fiction/tests/test_project_workspace_api.py zhihu_fiction/tests/test_static_video_workspace.py zhihu_fiction/tests/test_static_project_dashboard.py
git commit -m "feat: surface project workspace next actions"
```

---

## Task 7: Add Release Checklist And Local Production Documentation

**Files:**
- Create: `zhihu_fiction/RELEASE_CHECKLIST.md`
- Modify: `zhihu_fiction/README.md`
- Modify: `zhihu_fiction/.env.example`
- Test: `zhihu_fiction/tests/test_release_artifacts.py`

- [ ] **Step 1: Write failing release artifact tests**

Append to `zhihu_fiction/tests/test_release_artifacts.py`:

```python
def test_release_checklist_documents_industrial_v1_gates():
    checklist = Path("zhihu_fiction/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    assert "SQLite" in checklist
    assert "一致性" in checklist
    assert "成本确认" in checklist
    assert "服务重启恢复" in checklist
    assert "Web QA" in checklist


def test_env_example_documents_local_production_settings():
    env_example = Path("zhihu_fiction/.env.example").read_text(encoding="utf-8")

    assert "ZH_WORKSPACE_BACKEND=sqlite" in env_example
    assert "ZH_WORKSPACE_SQLITE_PATH" in env_example
    assert "ZH_OBJECT_STORAGE_BACKEND" in env_example
    assert "ZH_DAILY_BUDGET_CNY" in env_example
    assert "EMBEDDING_API_KEY" in env_example
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q -k "industrial_v1 or local_production"
```

Expected: fail because checklist or env keys are missing.

- [ ] **Step 3: Create release checklist**

Create `zhihu_fiction/RELEASE_CHECKLIST.md`:

```markdown
# zhihu_fiction V1 Release Checklist

## Data And Storage

- [ ] SQLite is enabled with `ZH_WORKSPACE_BACKEND=sqlite`.
- [ ] SQLite path is outside temporary directories.
- [ ] Object storage directory or MinIO bucket is configured.
- [ ] Runtime data, `.env`, auth files, and generated objects are ignored by git.

## Production Reliability

- [ ] DeepAgent sessions survive service restart.
- [ ] VideoRun and VideoJob records survive service restart.
- [ ] Failed stages show readable errors.
- [ ] Failed video shots can retry without resubmitting successful shots.
- [ ] Operation logs record confirm, revise, retry, cancel, recover, and export.
- [ ] 服务重启恢复 has been tested on one active project.

## Consistency

- [ ] 一致性 profile is generated for a project.
- [ ] Character, world, visual style, and narrative constraints are visible in the workspace.
- [ ] Storyboard and video prompts reference the consistency profile.

## Cost Control

- [ ] 成本确认 is required before every video API call.
- [ ] Daily budget is configured.
- [ ] Cost center explains estimated, actual, and covered estimate entries.
- [ ] Retry also requires cost confirmation.

## Web QA

- [ ] Project list shows status and pending action.
- [ ] Single-project workspace shows stage, human-loop controls, consistency, assets, costs, and logs.
- [ ] Task center shows running, failed, and waiting tasks.
- [ ] Cost center shows budget and coverage explanation.
```

- [ ] **Step 4: Update env example**

Ensure `zhihu_fiction/.env.example` contains:

```env
ZH_WORKSPACE_BACKEND=sqlite
ZH_WORKSPACE_SQLITE_PATH=zhihu_fiction/data/workspace/workspace.sqlite3
ZH_OBJECT_STORAGE_BACKEND=local
ZH_OBJECT_STORAGE_DIR=zhihu_fiction/data/objects
ZH_DAILY_BUDGET_CNY=50
ZH_VIDEO_UNIT_PRICE_CNY=1
EMBEDDING_API_KEY=your_bailian_or_dashscope_api_key
```

- [ ] **Step 5: Update README local production section**

In `zhihu_fiction/README.md`, add this section:

    ## 本地单机生产模式

    V1 推荐使用 SQLite 作为工作台主存储，本地对象目录保存图片、视频和发布包。

    ```bash
    cp zhihu_fiction/.env.example .env
    python -m pytest zhihu_fiction/tests -q
    uvicorn zhihu_fiction.server:app --reload
    ```

    打开：

    ```text
    http://127.0.0.1:8000/
    http://127.0.0.1:8000/video
    ```

    视频生成前会展示成本估算并要求人工确认。

- [ ] **Step 6: Run release tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add zhihu_fiction/RELEASE_CHECKLIST.md zhihu_fiction/README.md zhihu_fiction/.env.example zhihu_fiction/tests/test_release_artifacts.py
git commit -m "docs: add local production release checklist"
```

---

## Task 8: Full Verification And Two-Round Review

**Files:**
- No required code files.
- Review all files changed by Tasks 1-7.

- [ ] **Step 1: Run full test suite**

Run:

```bash
python -m pytest zhihu_fiction/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run release hygiene tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Spec review**

Compare implementation against:

```text
zhihu_fiction/docs/superpowers/specs/2026-06-15-industrialized-short-drama-factory-design.md
```

Checklist:
- [ ] Consistency profile is first-class and visible in project payload.
- [ ] Operation logs exist and record start/confirm actions.
- [ ] Cost center explains covered estimates.
- [ ] Recovery endpoint exposes waiting/running/failed work.
- [ ] Single-project workspace exposes human-loop controls, consistency, logs, and cost coverage.
- [ ] Release checklist and env example document local production mode.

- [ ] **Step 5: Quality review**

Checklist:
- [ ] No unrelated files were reverted.
- [ ] No API keys, auth state, object files, or runtime data were staged.
- [ ] New helpers are small and named by domain behavior.
- [ ] Route payloads are backward-compatible unless tests intentionally changed them.
- [ ] Tests isolate temp repositories and do not touch real workspace data.
- [ ] Static UI tests assert product-critical markers, not brittle layout details.

- [ ] **Step 6: Commit review fixes if needed**

If review finds fixes, make them with TDD when behavior changes, run focused tests, then commit:

```bash
git add <changed-files>
git commit -m "fix: address short drama factory review"
```

- [ ] **Step 7: Final status**

Report:
- full test result
- review result
- commit list
- any remaining known risk

---

## Execution Notes

- The repository currently has many dirty and untracked files. Do not reset or clean them.
- Stage only the files for the current task.
- Use TDD for every behavior change.
- After each implementation task, perform the required AGENTS.md two-round review:
  1. Spec review
  2. Quality review
- Prefer subagent-driven execution for isolated tasks.
- Do not implement V2 or V3 features in this plan unless a V1 task explicitly requires a compatibility seam.

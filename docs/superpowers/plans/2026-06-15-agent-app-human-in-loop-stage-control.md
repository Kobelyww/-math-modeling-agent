# Agent App Human-In-Loop Stage Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add checkpoint-based human approval, revision, pause, and resume control to the DeepAgent paper workflow.

**Architecture:** Add a small checkpoint control plane around the existing runner instead of replacing the paper workflow. Domain models and `CheckpointService` own persistence and transition rules; `CompetitionPaperRunner`, stage middleware, Web routes, and Web UI consume that service through explicit APIs and events.

**Tech Stack:** Python dataclasses, JSON-on-disk stores, FastAPI, WebSocket event replay, vanilla JavaScript, pytest.

---

## Source Spec

Implement this plan against:

- `docs/superpowers/specs/2026-06-15-agent-app-human-in-loop-stage-control-design.md`

## Working Tree Safety

Before implementation:

- Run `git status --short`.
- Confirm whether work should happen in the main project directory or the existing worktree `.worktrees/deepagent-paper-industrial`.
- Preserve unrelated user changes. The current repository may contain many modified and untracked files outside this feature.
- Keep commits focused by task. Do not mix checkpoint work with unrelated DeepAgent, Zhihu, Werewolf, or infrastructure changes.

## Required Review Loop

After each task:

1. **Spec review:** Check the task against the source spec and this plan. Confirm implemented scope, no missing requirements, and no extra behavior.
2. **Quality review:** Check naming, boundaries, edge cases, tests, and regression risk.

Only proceed to the next task after both reviews pass.

## File Structure Map

Create:

- `agent_app/services/checkpoint_service.py`
  - Owns checkpoint persistence, decision persistence, transition validation, active checkpoint lookup, and resume-plan creation.
- `agent_app/tests/test_checkpoint_service.py`
  - Unit tests for checkpoint lifecycle and service persistence.
- `agent_app/tests/test_checkpoint_runner.py`
  - Runner-level tests for pause, approve, revise, stop, and resume behavior.
- `agent_app/tests/test_web_checkpoints.py`
  - API route tests for checkpoint endpoints.

Modify:

- `agent_app/domain/models.py`
  - Add checkpoint enums and dataclasses. Extend `RunOptions` with checkpoint configuration.
- `agent_app/domain/serialization.py`
  - Existing dataclass/enum/path handling should cover new models. Add tests only if a union or nested payload issue appears.
- `agent_app/services/run_store.py`
  - Use existing `run_dir`, `create_run`, `save_state`, and `load_state`; do not add checkpoint transition logic here.
- `agent_app/deepagent/runner.py`
  - Add checkpoint-aware run methods and resume payload construction while preserving `run(spec)`.
- `agent_app/deepagent/middleware.py`
  - Add stage gate support for awaiting checkpoint decisions.
- `agent_app/deepagent/coordinator.py`
  - Pass checkpoint-aware middleware/service dependencies where needed.
- `agent_app/web/paper_stream.py`
  - Emit checkpoint events and route Web runs through checkpoint mode.
- `agent_app/web/routes.py`
  - Add checkpoint APIs and resume task creation.
- `agent_app/web/templates/index.html`
  - Add checkpoint panel/control surface.
- `agent_app/web/static/app.js`
  - Render checkpoint events, submit decisions, reconnect/resume from history.
- `agent_app/web/static/style.css`
  - Add compact checkpoint UI styles consistent with the existing work surface.
- Existing tests:
  - `agent_app/tests/test_domain_models.py`
  - `agent_app/tests/test_stage_middleware.py`
  - `agent_app/tests/test_paper_chat_stream.py`

## Implementation Decisions

- Web default checkpoint mode: `key_stages`.
- CLI/autonomous default checkpoint mode: `none`.
- Checkpoint pause happens at stage boundaries, not by interrupting an in-flight LLM call.
- Resume starts a new coordinator invocation scoped to the next stage or the current revision stage.
- Revision invokes the responsible stage agent/tool with prior stage outputs and user feedback.
- Editable payloads use structured JSON-compatible dictionaries; the first UI may render known fields plus a natural-language instruction box.

---

## Task 1: Add Checkpoint Domain Models

**Files:**

- Modify: `agent_app/domain/models.py`
- Modify: `agent_app/tests/test_domain_models.py`

- [ ] **Step 1: Write failing serialization tests**

Add tests to `agent_app/tests/test_domain_models.py`:

```python
def test_stage_checkpoint_round_trips_through_json():
    from pathlib import Path

    from agent_app.domain.models import (
        ArtifactRef,
        CheckpointStatus,
        RunStage,
        StageCheckpoint,
    )
    from agent_app.domain.serialization import from_json_dict, to_json_dict

    checkpoint = StageCheckpoint(
        checkpoint_id="checkpoint_understand_problem_001",
        run_id="run_20260615_120000_abcdef",
        stage=RunStage.UNDERSTAND_PROBLEM,
        status=CheckpointStatus.AWAITING_USER,
        title="确认赛题理解",
        summary="需要确认目标函数和约束。",
        editable_payload={"objectives": ["预测需求"], "assumptions": ["数据完整"]},
        artifacts=[ArtifactRef(name="problem_brief.md", path=Path("problem_brief.md"), kind="markdown")],
        created_at="2026-06-15T12:00:00",
    )

    payload = to_json_dict(checkpoint)
    restored = from_json_dict(StageCheckpoint, payload)

    assert payload["stage"] == "understand_problem"
    assert payload["status"] == "awaiting_user"
    assert payload["artifacts"][0]["path"] == "problem_brief.md"
    assert restored == checkpoint
```

```python
def test_checkpoint_decision_and_resume_plan_round_trip():
    from agent_app.domain.models import (
        CheckpointAction,
        CheckpointDecision,
        ResumeMode,
        ResumePlan,
        RunStage,
    )
    from agent_app.domain.serialization import from_json_dict, to_json_dict

    decision = CheckpointDecision(
        decision_id="decision_001",
        checkpoint_id="checkpoint_plan_modeling_001",
        run_id="run_20260615_120000_abcdef",
        stage=RunStage.PLAN_MODELING,
        action=CheckpointAction.REVISE,
        instruction="加入灵敏度分析和基准模型。",
        payload_patch={"evaluation_metrics": ["RMSE", "MAE"]},
        created_at="2026-06-15T12:05:00",
    )
    plan = ResumePlan(
        run_id=decision.run_id,
        from_stage=RunStage.PLAN_MODELING,
        decision_id=decision.decision_id,
        resume_mode=ResumeMode.REVISE_STAGE,
        reason="用户要求修改模型计划",
    )

    assert from_json_dict(CheckpointDecision, to_json_dict(decision)) == decision
    assert from_json_dict(ResumePlan, to_json_dict(plan)) == plan
```

```python
def test_run_options_checkpoint_defaults_preserve_autonomous_mode():
    from agent_app.domain.models import CheckpointMode, RunOptions

    options = RunOptions()

    assert options.checkpoint_mode == CheckpointMode.NONE
    assert options.auto_approve_timeout_seconds is None
    assert options.require_user_approval_for_execution is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_domain_models.py::test_stage_checkpoint_round_trips_through_json agent_app/tests/test_domain_models.py::test_checkpoint_decision_and_resume_plan_round_trip agent_app/tests/test_domain_models.py::test_run_options_checkpoint_defaults_preserve_autonomous_mode -q
```

Expected: fail because checkpoint model names are not defined.

- [ ] **Step 3: Add enums and dataclasses**

Add to `agent_app/domain/models.py` after `RunStage`:

```python
class CheckpointMode(str, Enum):
    NONE = "none"
    KEY_STAGES = "key_stages"
    ALL_STAGES = "all_stages"


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    APPROVED = "approved"
    REVISING = "revising"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CheckpointAction(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    STOP = "stop"


class ResumeMode(str, Enum):
    CONTINUE = "continue"
    REVISE_STAGE = "revise_stage"
    REPLAY_FROM_CHECKPOINT = "replay_from_checkpoint"
```

Extend `RunOptions`:

```python
@dataclass
class RunOptions:
    top_k: int = 6
    max_repair_attempts: int = 2
    compile_pdf: bool = True
    allow_online_search: bool = False
    checkpoint_mode: CheckpointMode = CheckpointMode.NONE
    auto_approve_timeout_seconds: int | None = None
    require_user_approval_for_execution: bool = False
```

Add after `QualityReport` or before `RunState`:

```python
@dataclass
class StageCheckpoint:
    checkpoint_id: str
    run_id: str
    stage: RunStage
    status: CheckpointStatus
    title: str
    summary: str = ""
    editable_payload: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    quality_reports: list[QualityReport] = field(default_factory=list)
    created_at: str = ""
    resolved_at: str = ""


@dataclass
class CheckpointDecision:
    decision_id: str
    checkpoint_id: str
    run_id: str
    stage: RunStage
    action: CheckpointAction
    instruction: str = ""
    payload_patch: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class ResumePlan:
    run_id: str
    from_stage: RunStage
    decision_id: str
    resume_mode: ResumeMode
    reason: str = ""
```

- [ ] **Step 4: Run domain tests**

Run:

```bash
pytest agent_app/tests/test_domain_models.py -q
```

Expected: pass.

- [ ] **Step 5: Review**

Spec review:

- Confirm all models from the spec exist.
- Confirm `RunOptions` defaults keep existing CLI/autonomous behavior.

Quality review:

- Confirm enum values match API/event strings.
- Confirm no mutable dataclass defaults are used.

- [ ] **Step 6: Commit**

```bash
git add agent_app/domain/models.py agent_app/tests/test_domain_models.py
git commit -m "feat: add checkpoint domain models"
```

---

## Task 2: Implement Checkpoint Service Persistence

**Files:**

- Create: `agent_app/services/checkpoint_service.py`
- Create: `agent_app/tests/test_checkpoint_service.py`

- [ ] **Step 1: Write failing service tests**

Create `agent_app/tests/test_checkpoint_service.py`:

```python
from pathlib import Path

import pytest

from agent_app.domain.models import (
    CheckpointAction,
    CheckpointStatus,
    ResumeMode,
    RunSpec,
    RunStage,
)
from agent_app.services.checkpoint_service import CheckpointConflictError, CheckpointService
from agent_app.services.run_store import RunStore


def _create_run(tmp_path: Path):
    store = RunStore(tmp_path)
    state = store.create_run(RunSpec(question="测试赛题"))
    return store, state


def test_create_and_load_active_checkpoint(tmp_path):
    store, state = _create_run(tmp_path)
    service = CheckpointService(store)

    checkpoint = service.create_checkpoint(
        run_id=state.run_id,
        stage=RunStage.UNDERSTAND_PROBLEM,
        title="确认赛题理解",
        summary="目标和约束已提取。",
        editable_payload={"objectives": ["最小化成本"]},
    )

    loaded = service.get_active_checkpoint(state.run_id)

    assert checkpoint.status == CheckpointStatus.AWAITING_USER
    assert loaded == checkpoint
    assert (store.run_dir(state.run_id) / "checkpoints" / f"{checkpoint.checkpoint_id}.json").exists()
```

```python
def test_approve_checkpoint_resolves_and_builds_continue_plan(tmp_path):
    store, state = _create_run(tmp_path)
    service = CheckpointService(store)
    checkpoint = service.create_checkpoint(
        run_id=state.run_id,
        stage=RunStage.PLAN_MODELING,
        title="确认模型计划",
    )

    decision = service.record_decision(
        run_id=state.run_id,
        checkpoint_id=checkpoint.checkpoint_id,
        action=CheckpointAction.APPROVE,
        instruction="同意",
    )
    plan = service.build_resume_plan(state.run_id, decision.decision_id)

    resolved = service.load_checkpoint(state.run_id, checkpoint.checkpoint_id)
    assert resolved.status == CheckpointStatus.APPROVED
    assert resolved.resolved_at
    assert decision.action == CheckpointAction.APPROVE
    assert plan.resume_mode == ResumeMode.CONTINUE
    assert plan.from_stage == RunStage.PLAN_MODELING
```

```python
def test_revise_checkpoint_creates_revise_stage_plan(tmp_path):
    store, state = _create_run(tmp_path)
    service = CheckpointService(store)
    checkpoint = service.create_checkpoint(
        run_id=state.run_id,
        stage=RunStage.DRAFT_PAPER,
        title="确认论文初稿",
    )

    decision = service.record_decision(
        run_id=state.run_id,
        checkpoint_id=checkpoint.checkpoint_id,
        action=CheckpointAction.REVISE,
        instruction="摘要更学术，增加符号说明。",
        payload_patch={"missing_sections": ["符号说明"]},
    )
    plan = service.build_resume_plan(state.run_id, decision.decision_id)

    resolved = service.load_checkpoint(state.run_id, checkpoint.checkpoint_id)
    assert resolved.status == CheckpointStatus.REVISING
    assert plan.resume_mode == ResumeMode.REVISE_STAGE
    assert "摘要" in decision.instruction
```

```python
def test_duplicate_decision_is_rejected(tmp_path):
    store, state = _create_run(tmp_path)
    service = CheckpointService(store)
    checkpoint = service.create_checkpoint(
        run_id=state.run_id,
        stage=RunStage.AUDIT_DATA,
        title="确认数据审计",
    )

    service.record_decision(state.run_id, checkpoint.checkpoint_id, CheckpointAction.APPROVE)

    with pytest.raises(CheckpointConflictError):
        service.record_decision(state.run_id, checkpoint.checkpoint_id, CheckpointAction.REVISE)
```

```python
def test_stop_checkpoint_keeps_run_paused_without_resume_plan(tmp_path):
    store, state = _create_run(tmp_path)
    service = CheckpointService(store)
    checkpoint = service.create_checkpoint(
        run_id=state.run_id,
        stage=RunStage.RUN_EXPERIMENTS,
        title="确认实验执行",
    )

    decision = service.record_decision(
        run_id=state.run_id,
        checkpoint_id=checkpoint.checkpoint_id,
        action=CheckpointAction.STOP,
        instruction="稍后再继续",
    )

    resolved = service.load_checkpoint(state.run_id, checkpoint.checkpoint_id)
    assert resolved.status == CheckpointStatus.AWAITING_USER
    assert service.get_active_checkpoint(state.run_id) == resolved
    assert service.build_resume_plan(state.run_id, decision.decision_id).resume_mode == ResumeMode.REPLAY_FROM_CHECKPOINT
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_checkpoint_service.py -q
```

Expected: fail because `checkpoint_service.py` does not exist.

- [ ] **Step 3: Implement service**

Create `agent_app/services/checkpoint_service.py`:

```python
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from agent_app.domain.models import (
    CheckpointAction,
    CheckpointDecision,
    CheckpointStatus,
    ResumeMode,
    ResumePlan,
    RunStage,
    StageCheckpoint,
)
from agent_app.domain.serialization import from_json_dict, to_json_dict
from agent_app.services.run_store import RunStore


class CheckpointError(RuntimeError):
    pass


class CheckpointNotFoundError(CheckpointError):
    pass


class CheckpointConflictError(CheckpointError):
    pass


class CheckpointService:
    def __init__(self, run_store: RunStore) -> None:
        self.run_store = run_store

    def create_checkpoint(
        self,
        run_id: str,
        stage: RunStage,
        title: str,
        summary: str = "",
        editable_payload: dict | None = None,
    ) -> StageCheckpoint:
        active = self.get_active_checkpoint(run_id)
        if active is not None:
            raise CheckpointConflictError(f"Run {run_id} already has active checkpoint {active.checkpoint_id}")
        checkpoint_id = f"checkpoint_{stage.value}_{self._compact_now()}_{uuid4().hex[:6]}"
        checkpoint = StageCheckpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            stage=stage,
            status=CheckpointStatus.AWAITING_USER,
            title=title,
            summary=summary,
            editable_payload=editable_payload or {},
            created_at=self._now(),
        )
        self._write_checkpoint(checkpoint)
        return checkpoint

    def load_checkpoint(self, run_id: str, checkpoint_id: str) -> StageCheckpoint:
        path = self._checkpoint_path(run_id, checkpoint_id)
        if not path.exists():
            raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")
        return from_json_dict(StageCheckpoint, json.loads(path.read_text(encoding="utf-8")))

    def get_active_checkpoint(self, run_id: str) -> StageCheckpoint | None:
        for checkpoint in reversed(self.list_checkpoints(run_id)):
            if checkpoint.status in {CheckpointStatus.AWAITING_USER, CheckpointStatus.REVISING}:
                return checkpoint
        return None

    def list_checkpoints(self, run_id: str) -> list[StageCheckpoint]:
        checkpoint_dir = self._checkpoint_dir(run_id)
        if not checkpoint_dir.exists():
            return []
        checkpoints = []
        for path in sorted(checkpoint_dir.glob("checkpoint_*.json")):
            checkpoints.append(from_json_dict(StageCheckpoint, json.loads(path.read_text(encoding="utf-8"))))
        return checkpoints

    def record_decision(
        self,
        run_id: str,
        checkpoint_id: str,
        action: CheckpointAction,
        instruction: str = "",
        payload_patch: dict | None = None,
    ) -> CheckpointDecision:
        checkpoint = self.load_checkpoint(run_id, checkpoint_id)
        if checkpoint.status not in {CheckpointStatus.AWAITING_USER, CheckpointStatus.REVISING}:
            raise CheckpointConflictError(f"Checkpoint {checkpoint_id} is not active")
        if self._has_resolving_decision(run_id, checkpoint_id):
            raise CheckpointConflictError(f"Checkpoint {checkpoint_id} already has a decision")

        decision = CheckpointDecision(
            decision_id=f"decision_{self._compact_now()}_{uuid4().hex[:6]}",
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            stage=checkpoint.stage,
            action=action,
            instruction=instruction,
            payload_patch=payload_patch or {},
            created_at=self._now(),
        )
        if action == CheckpointAction.APPROVE:
            checkpoint = replace(checkpoint, status=CheckpointStatus.APPROVED, resolved_at=self._now())
        elif action == CheckpointAction.REVISE:
            checkpoint = replace(checkpoint, status=CheckpointStatus.REVISING)
        elif action == CheckpointAction.STOP:
            checkpoint = replace(checkpoint, status=CheckpointStatus.AWAITING_USER)
        self._write_checkpoint(checkpoint)
        self._append_decision(decision)
        return decision

    def list_decisions(self, run_id: str) -> list[CheckpointDecision]:
        path = self._decisions_path(run_id)
        if not path.exists():
            return []
        decisions = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                decisions.append(from_json_dict(CheckpointDecision, json.loads(line)))
        return decisions

    def build_resume_plan(self, run_id: str, decision_id: str) -> ResumePlan:
        decision = next((item for item in self.list_decisions(run_id) if item.decision_id == decision_id), None)
        if decision is None:
            raise CheckpointNotFoundError(f"Decision {decision_id} not found")
        if decision.action == CheckpointAction.APPROVE:
            mode = ResumeMode.CONTINUE
            reason = "checkpoint approved"
        elif decision.action == CheckpointAction.REVISE:
            mode = ResumeMode.REVISE_STAGE
            reason = decision.instruction or "checkpoint revision requested"
        else:
            mode = ResumeMode.REPLAY_FROM_CHECKPOINT
            reason = decision.instruction or "checkpoint stopped"
        return ResumePlan(
            run_id=run_id,
            from_stage=decision.stage,
            decision_id=decision.decision_id,
            resume_mode=mode,
            reason=reason,
        )

    def _has_resolving_decision(self, run_id: str, checkpoint_id: str) -> bool:
        return any(
            decision.checkpoint_id == checkpoint_id and decision.action in {CheckpointAction.APPROVE, CheckpointAction.REVISE}
            for decision in self.list_decisions(run_id)
        )

    def _checkpoint_dir(self, run_id: str) -> Path:
        path = self.run_store.run_dir(run_id) / "checkpoints"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _checkpoint_path(self, run_id: str, checkpoint_id: str) -> Path:
        if "/" in checkpoint_id or "\\" in checkpoint_id or not checkpoint_id.startswith("checkpoint_"):
            raise CheckpointNotFoundError(f"Invalid checkpoint id {checkpoint_id}")
        return self._checkpoint_dir(run_id) / f"{checkpoint_id}.json"

    def _decisions_path(self, run_id: str) -> Path:
        return self._checkpoint_dir(run_id) / "decisions.jsonl"

    def _write_checkpoint(self, checkpoint: StageCheckpoint) -> None:
        path = self._checkpoint_path(checkpoint.run_id, checkpoint.checkpoint_id)
        path.write_text(json.dumps(to_json_dict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_decision(self, decision: CheckpointDecision) -> None:
        path = self._decisions_path(decision.run_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_json_dict(decision), ensure_ascii=False) + "\n")

    @staticmethod
    def _now() -> str:
        return datetime.now().replace(microsecond=0).isoformat()

    @classmethod
    def _compact_now(cls) -> str:
        return cls._now().replace("-", "").replace(":", "").replace("T", "_")
```

- [ ] **Step 4: Run service tests**

Run:

```bash
pytest agent_app/tests/test_checkpoint_service.py -q
```

Expected: pass.

- [ ] **Step 5: Run focused regression**

Run:

```bash
pytest agent_app/tests/test_domain_models.py agent_app/tests/test_run_store.py agent_app/tests/test_checkpoint_service.py -q
```

Expected: pass.

- [ ] **Step 6: Review**

Spec review:

- Confirm persistence layout matches the spec: `checkpoints/*.json`, `decisions.jsonl`.
- Confirm approve/revise/stop are supported.

Quality review:

- Confirm ID validation prevents path traversal.
- Confirm duplicate resolving decisions are rejected.
- Confirm service owns transition logic.

- [ ] **Step 7: Commit**

```bash
git add agent_app/services/checkpoint_service.py agent_app/tests/test_checkpoint_service.py
git commit -m "feat: persist paper workflow checkpoints"
```

---

## Task 3: Add Checkpoint-Aware Stage Gate To Middleware

**Files:**

- Modify: `agent_app/deepagent/middleware.py`
- Modify: `agent_app/tests/test_stage_middleware.py`

- [ ] **Step 1: Write failing middleware tests**

Add tests to `agent_app/tests/test_stage_middleware.py`:

```python
def test_checkpoint_blocks_future_stage_until_approved():
    from agent_app.deepagent.middleware import CompetitionStageMiddleware

    middleware = CompetitionStageMiddleware()
    middleware.record_tool_result("ingest_inputs", {"ok": True})
    assert middleware.current_stage == "understand_problem"

    middleware.record_tool_result("analyze_problem", {"problem_brief": {"objectives": ["x"]}})
    middleware.pause_for_checkpoint("understand_problem")

    assert middleware.current_stage == "understand_problem"
    assert middleware.is_awaiting_checkpoint

    try:
        middleware.validate_tool("audit_data")
    except PermissionError as exc:
        assert "awaiting checkpoint approval" in str(exc)
    else:
        raise AssertionError("future-stage tool should be blocked")

    middleware.approve_checkpoint("understand_problem")
    assert middleware.current_stage == "audit_data"
    middleware.validate_tool("audit_data")
```

```python
def test_checkpoint_revision_keeps_same_stage_active():
    from agent_app.deepagent.middleware import CompetitionStageMiddleware

    middleware = CompetitionStageMiddleware()
    middleware.record_tool_result("ingest_inputs", {"ok": True})
    middleware.record_tool_result("analyze_problem", {"problem_brief": {"objectives": ["x"]}})
    middleware.pause_for_checkpoint("understand_problem")

    middleware.revise_checkpoint("understand_problem")

    assert middleware.current_stage == "understand_problem"
    assert middleware.is_revising_checkpoint
    middleware.validate_tool("analyze_problem")
```

```python
def test_checkpoint_failure_latches_stage():
    from agent_app.deepagent.middleware import CompetitionStageMiddleware

    middleware = CompetitionStageMiddleware()
    middleware.record_tool_result("ingest_inputs", {"ok": True})
    middleware.record_tool_result("analyze_problem", {"problem_brief": {"objectives": ["x"]}})
    middleware.pause_for_checkpoint("understand_problem")

    middleware.fail_checkpoint("understand_problem", "revision failed")

    try:
        middleware.validate_tool("audit_data")
    except PermissionError as exc:
        assert "revision failed" in str(exc)
    else:
        raise AssertionError("future-stage tool should be blocked after checkpoint failure")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_stage_middleware.py::test_checkpoint_blocks_future_stage_until_approved agent_app/tests/test_stage_middleware.py::test_checkpoint_revision_keeps_same_stage_active agent_app/tests/test_stage_middleware.py::test_checkpoint_failure_latches_stage -q
```

Expected: fail because checkpoint methods do not exist.

- [ ] **Step 3: Implement stage gate state**

Modify `CompetitionStageMiddleware.__init__`:

```python
self.checkpoint_stage: str | None = None
self.checkpoint_status: str | None = None
self.checkpoint_error: str = ""
```

Add properties and methods:

```python
@property
def is_awaiting_checkpoint(self) -> bool:
    return self.checkpoint_status == "awaiting_user"


@property
def is_revising_checkpoint(self) -> bool:
    return self.checkpoint_status == "revising"


def pause_for_checkpoint(self, stage_name: str) -> None:
    self._ensure_known_stage(stage_name)
    self.checkpoint_stage = stage_name
    self.checkpoint_status = "awaiting_user"
    self.checkpoint_error = ""
    self.stage_index = self._stage_index_for(stage_name)


def approve_checkpoint(self, stage_name: str) -> None:
    if self.checkpoint_stage != stage_name:
        raise PermissionError(f"Checkpoint for {stage_name!r} is not active")
    self.checkpoint_stage = None
    self.checkpoint_status = None
    self.checkpoint_error = ""
    self._advance_if_ready()


def revise_checkpoint(self, stage_name: str) -> None:
    if self.checkpoint_stage != stage_name:
        raise PermissionError(f"Checkpoint for {stage_name!r} is not active")
    self.checkpoint_status = "revising"
    self.stage_index = self._stage_index_for(stage_name)
    self.completed_required_tools[stage_name].clear()


def fail_checkpoint(self, stage_name: str, message: str) -> None:
    if self.checkpoint_stage != stage_name:
        raise PermissionError(f"Checkpoint for {stage_name!r} is not active")
    self.checkpoint_status = "failed"
    self.checkpoint_error = message


def _stage_index_for(self, stage_name: str) -> int:
    for index, stage in enumerate(self.stages):
        if stage.name == stage_name:
            return index
    raise ValueError(f"Unknown stage {stage_name!r}")


def _ensure_known_stage(self, stage_name: str) -> None:
    self._stage_index_for(stage_name)
```

Modify `validate_tool` so checkpoint state blocks future tools:

```python
def validate_tool(self, tool_name: str) -> None:
    if self.checkpoint_status == "failed":
        raise PermissionError(self.checkpoint_error or "checkpoint failed")
    if self.checkpoint_status == "awaiting_user":
        raise PermissionError(f"Stage {self.checkpoint_stage!r} is awaiting checkpoint approval")
    if tool_name not in self.available_tools():
        raise PermissionError(f"Tool {tool_name!r} is not available during stage {self.current_stage!r}")
```

Modify `_advance_if_ready`:

```python
if self.checkpoint_status in {"awaiting_user", "revising", "failed"}:
    return
```

During revision, allow current-stage tools. `validate_tool` must block only `awaiting_user` and `failed`; `revising` remains open for the active stage's tools.

- [ ] **Step 4: Run middleware tests**

Run:

```bash
pytest agent_app/tests/test_stage_middleware.py -q
```

Expected: pass.

- [ ] **Step 5: Review**

Spec review:

- Confirm future-stage tools cannot advance while awaiting user.
- Confirm revision keeps the same stage active.

Quality review:

- Confirm existing tool ordering tests still pass.
- Confirm failure state blocks later tools with a clear error.

- [ ] **Step 6: Commit**

```bash
git add agent_app/deepagent/middleware.py agent_app/tests/test_stage_middleware.py
git commit -m "feat: gate stages on checkpoint decisions"
```

---

## Task 4: Add Runner Pause And Resume Contracts

**Files:**

- Modify: `agent_app/deepagent/runner.py`
- Create: `agent_app/tests/test_checkpoint_runner.py`

- [ ] **Step 1: Write failing runner tests with fake coordinator**

Create `agent_app/tests/test_checkpoint_runner.py`:

```python
from pathlib import Path

from agent_app.deepagent.runner import CompetitionPaperRunner
from agent_app.domain.models import CheckpointAction, CheckpointMode, RunOptions, RunSpec, RunStatus


class RecordingCoordinator:
    def __init__(self, calls):
        self.calls = calls

    def invoke(self, payload):
        self.calls.append(payload)
        run_dir = Path(payload["run_dir"])
        if payload.get("stop_after_stage") == "understand_problem":
            (run_dir / "problem_brief.md").write_text("# Problem brief", encoding="utf-8")
            return {"messages": [{"content": "paused after understand_problem"}]}
        if payload.get("resume_mode") == "continue":
            (run_dir / "modeling_report.md").write_text("# Model", encoding="utf-8")
            (run_dir / "solve.py").write_text("print('ok')", encoding="utf-8")
            (run_dir / "paper.tex").write_text("\\\\section{Paper}", encoding="utf-8")
            return {"messages": [{"content": "continued"}]}
        if payload.get("resume_mode") == "revise_stage":
            (run_dir / "problem_brief.md").write_text("# Revised problem brief", encoding="utf-8")
            return {"messages": [{"content": "revised"}]}
        return {"messages": [{"content": "autonomous"}]}


def _factory(calls):
    def create(**kwargs):
        return RecordingCoordinator(calls)
    return create


def test_run_until_checkpoint_pauses_and_persists_checkpoint(tmp_path):
    calls = []
    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=_factory(calls))
    spec = RunSpec(
        question="测试赛题",
        options=RunOptions(checkpoint_mode=CheckpointMode.KEY_STAGES),
    )

    result = runner.run_until_checkpoint(spec)

    assert result.status == RunStatus.PARTIAL
    assert result.stage.value == "understand_problem"
    assert calls[0]["stop_after_stage"] == "understand_problem"
    checkpoint = runner.checkpoint_service.get_active_checkpoint(result.run_id)
    assert checkpoint is not None
    assert checkpoint.stage.value == "understand_problem"
```

```python
def test_resume_approved_checkpoint_continues_run(tmp_path):
    calls = []
    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=_factory(calls))
    result = runner.run_until_checkpoint(
        RunSpec(question="测试赛题", options=RunOptions(checkpoint_mode=CheckpointMode.KEY_STAGES))
    )
    checkpoint = runner.checkpoint_service.get_active_checkpoint(result.run_id)
    decision = runner.checkpoint_service.record_decision(
        result.run_id,
        checkpoint.checkpoint_id,
        CheckpointAction.APPROVE,
    )

    resumed = runner.resume(result.run_id, decision.decision_id)

    assert resumed.status == RunStatus.COMPLETED
    assert calls[-1]["resume_mode"] == "continue"
    assert calls[-1]["from_stage"] == "understand_problem"
```

```python
def test_resume_revision_keeps_run_partial_at_checkpoint_stage(tmp_path):
    calls = []
    runner = CompetitionPaperRunner(output_root=tmp_path, coordinator_factory=_factory(calls))
    result = runner.run_until_checkpoint(
        RunSpec(question="测试赛题", options=RunOptions(checkpoint_mode=CheckpointMode.KEY_STAGES))
    )
    checkpoint = runner.checkpoint_service.get_active_checkpoint(result.run_id)
    decision = runner.checkpoint_service.record_decision(
        result.run_id,
        checkpoint.checkpoint_id,
        CheckpointAction.REVISE,
        instruction="重新解释约束",
    )

    resumed = runner.resume(result.run_id, decision.decision_id)

    assert resumed.status == RunStatus.PARTIAL
    assert resumed.stage.value == "understand_problem"
    assert calls[-1]["resume_mode"] == "revise_stage"
    assert calls[-1]["checkpoint_instruction"] == "重新解释约束"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_checkpoint_runner.py -q
```

Expected: fail because runner methods and `checkpoint_service` do not exist.

- [ ] **Step 3: Add runner checkpoint dependencies**

Modify `CompetitionPaperRunner.__init__`:

```python
from agent_app.domain.models import CheckpointMode, ResumeMode, RunStage
from agent_app.services.checkpoint_service import CheckpointService

self.checkpoint_service = CheckpointService(self.run_store)
```

- [ ] **Step 4: Add checkpoint stage policy helper**

Add to `CompetitionPaperRunner`:

```python
KEY_CHECKPOINT_STAGES = (
    RunStage.UNDERSTAND_PROBLEM,
    RunStage.AUDIT_DATA,
    RunStage.PLAN_MODELING,
    RunStage.RUN_EXPERIMENTS,
    RunStage.DRAFT_PAPER,
    RunStage.PACKAGE_SUBMISSION,
)


def _first_checkpoint_stage(self, spec: RunSpec) -> RunStage | None:
    if spec.options.checkpoint_mode == CheckpointMode.NONE:
        return None
    if spec.options.checkpoint_mode == CheckpointMode.ALL_STAGES:
        return RunStage.INGEST_INPUTS
    return self.KEY_CHECKPOINT_STAGES[0]
```

- [ ] **Step 5: Add `run_until_checkpoint`**

Implement as a wrapper around a new shared `_run_with_payload` helper:

```python
def run_until_checkpoint(self, spec: RunSpec) -> RunResult:
    checkpoint_stage = self._first_checkpoint_stage(spec)
    if checkpoint_stage is None:
        return self.run(spec)
    state = self.run_store.create_run(spec)
    run_dir = self.run_store.run_dir(state.run_id)
    state.status = RunStatus.RUNNING
    state.stage = checkpoint_stage
    self.run_store.save_state(state)
    payload = self._build_coordinator_payload(state.run_id, run_dir, spec)
    payload["stop_after_stage"] = checkpoint_stage.value
    summary = self._invoke_coordinator(payload, state)
    state = self._load_latest_state(state)
    state.status = RunStatus.PARTIAL
    state.stage = checkpoint_stage
    state.artifacts = self._collect_artifacts(run_dir)
    self.checkpoint_service.create_checkpoint(
        run_id=state.run_id,
        stage=checkpoint_stage,
        title=self._checkpoint_title(checkpoint_stage),
        summary=summary,
        editable_payload=self._checkpoint_payload_for_stage(checkpoint_stage, run_dir),
    )
    self.run_store.save_state(state)
    self._emit({"type": "checkpoint_created", "run_id": state.run_id, "stage": checkpoint_stage.value})
    return self._result_from_state(state, summary)
```

Add helpers:

```python
def _invoke_coordinator(self, payload: dict[str, Any], state: Any) -> str:
    coordinator = self._create_coordinator()
    response = coordinator.invoke(payload)
    return self._summarize_response(response)


def _result_from_state(self, state: Any, summary: str) -> RunResult:
    return RunResult(
        run_id=state.run_id,
        status=state.status,
        stage=state.stage,
        artifacts=state.artifacts,
        quality_reports=state.quality_reports,
        summary=summary,
    )


def _emit(self, event: dict[str, Any]) -> None:
    if self.event_handler is not None:
        self.event_handler(event)
```

Use existing `_collect_artifacts`, `_checkpoint_title`, and `_checkpoint_payload_for_stage` as small deterministic helpers. Start with simple payload extraction based on known artifact filenames:

```python
def _checkpoint_title(self, stage: RunStage) -> str:
    return {
        RunStage.UNDERSTAND_PROBLEM: "确认赛题理解",
        RunStage.AUDIT_DATA: "确认数据审计",
        RunStage.PLAN_MODELING: "确认模型计划",
        RunStage.RUN_EXPERIMENTS: "确认实验执行",
        RunStage.DRAFT_PAPER: "确认论文初稿",
        RunStage.PACKAGE_SUBMISSION: "确认最终提交包",
    }.get(stage, f"确认阶段 {stage.value}")


def _checkpoint_payload_for_stage(self, stage: RunStage, run_dir: Path) -> dict[str, Any]:
    return {
        "stage": stage.value,
        "artifacts": [str(path.relative_to(run_dir)) for path in sorted(run_dir.glob("*")) if path.is_file()],
    }
```

- [ ] **Step 6: Add `resume`**

Add:

```python
def resume(self, run_id: str, decision_id: str) -> RunResult:
    state = self.run_store.load_state(run_id)
    run_dir = self.run_store.run_dir(run_id)
    plan = self.checkpoint_service.build_resume_plan(run_id, decision_id)
    decision = next(item for item in self.checkpoint_service.list_decisions(run_id) if item.decision_id == decision_id)
    payload = self._build_coordinator_payload(run_id, run_dir, state.spec)
    payload.update(
        {
            "resume_mode": plan.resume_mode.value,
            "from_stage": plan.from_stage.value,
            "checkpoint_decision_id": decision_id,
            "checkpoint_instruction": decision.instruction,
            "checkpoint_payload_patch": decision.payload_patch,
        }
    )
    self._emit({"type": "resume_started", "run_id": run_id, "stage": plan.from_stage.value})
    try:
        summary = self._invoke_coordinator(payload, state)
    except Exception as exc:
        state = self._load_latest_state(state)
        state.status = RunStatus.FAILED
        state.stage = plan.from_stage
        self.run_store.save_state(state)
        self._emit({"type": "resume_failed", "run_id": run_id, "stage": plan.from_stage.value, "message": str(exc)})
        return self._result_from_state(state, str(exc))

    state = self._load_latest_state(state)
    state.artifacts = self._collect_artifacts(run_dir)
    if plan.resume_mode == ResumeMode.REVISE_STAGE:
        state.status = RunStatus.PARTIAL
        state.stage = plan.from_stage
    else:
        state.status = RunStatus.COMPLETED
    if state.status == RunStatus.COMPLETED and not self._has_core_submission_artifacts(state.artifacts):
        state.status = RunStatus.PARTIAL
    self.run_store.save_state(state)
    self._emit({"type": "resume_completed", "run_id": run_id, "stage": state.stage.value, "status": state.status.value})
    return self._result_from_state(state, summary)
```

- [ ] **Step 7: Keep `run(spec)` compatible**

Refactor `run(spec)` only enough to share helpers. The observable behavior for existing tests must remain:

- creates a run;
- invokes coordinator once;
- collects artifacts;
- marks completed or partial based on required artifacts;
- returns `RunResult`.

- [ ] **Step 8: Run runner tests**

Run:

```bash
pytest agent_app/tests/test_checkpoint_runner.py agent_app/tests/test_competition_runner.py agent_app/tests/test_competition_smoke.py -q
```

Expected: pass.

- [ ] **Step 9: Review**

Spec review:

- Confirm pause and resume operate at stage boundaries.
- Confirm autonomous `run(spec)` still works.

Quality review:

- Confirm runner does not duplicate checkpoint persistence rules.
- Confirm failed resume leaves readable prior checkpoint state.

- [ ] **Step 10: Commit**

```bash
git add agent_app/deepagent/runner.py agent_app/tests/test_checkpoint_runner.py
git commit -m "feat: add resumable paper checkpoint runner"
```

---

## Task 5: Emit And Persist Checkpoint Events In Paper Stream

**Files:**

- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/tests/test_paper_chat_stream.py`

- [ ] **Step 1: Write failing stream tests**

Add to `agent_app/tests/test_paper_chat_stream.py`:

```python
def test_paper_stream_uses_checkpoint_mode_for_web_runs(tmp_path):
    from agent_app.domain.models import CheckpointMode
    from agent_app.web.paper_stream import PaperChatStreamer

    captured = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_until_checkpoint(self, spec):
            captured["checkpoint_mode"] = spec.options.checkpoint_mode
            from agent_app.domain.models import RunResult, RunStage, RunStatus
            return RunResult(run_id="run_1", status=RunStatus.PARTIAL, stage=RunStage.UNDERSTAND_PROBLEM, summary="paused")

    events = []
    streamer = PaperChatStreamer(output_root=tmp_path, runner_cls=FakeRunner)

    streamer.run_checkpointed("测试赛题", emit=events.append)

    assert captured["checkpoint_mode"] == CheckpointMode.KEY_STAGES
    assert any(event["type"] == "done" and event["status"] == "partial" for event in events)
```

```python
def test_paper_stream_forwards_checkpoint_created_event(tmp_path):
    from agent_app.web.paper_stream import PaperChatStreamer

    class FakeRunner:
        def __init__(self, event_handler=None, **kwargs):
            self.event_handler = event_handler

        def run_until_checkpoint(self, spec):
            from agent_app.domain.models import RunResult, RunStage, RunStatus
            self.event_handler(
                {
                    "type": "checkpoint_created",
                    "run_id": "run_1",
                    "checkpoint_id": "checkpoint_understand_problem_1",
                    "stage": "understand_problem",
                    "status": "awaiting_user",
                    "summary": "确认赛题理解",
                }
            )
            return RunResult(run_id="run_1", status=RunStatus.PARTIAL, stage=RunStage.UNDERSTAND_PROBLEM, summary="paused")

    events = []
    PaperChatStreamer(output_root=tmp_path, runner_cls=FakeRunner).run_checkpointed("测试赛题", events.append)

    assert any(event["type"] == "checkpoint_created" for event in events)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py::test_paper_stream_uses_checkpoint_mode_for_web_runs agent_app/tests/test_paper_chat_stream.py::test_paper_stream_forwards_checkpoint_created_event -q
```

Expected: fail because `runner_cls` or `run_checkpointed` does not exist.

- [ ] **Step 3: Add injectable runner class and checkpointed stream method**

Modify `PaperChatStreamer.__init__`:

```python
def __init__(..., runner_cls: type[CompetitionPaperRunner] = CompetitionPaperRunner) -> None:
    ...
    self.runner_cls = runner_cls
```

Add:

```python
def run_checkpointed(self, question: str, emit: PaperEventHandler, **spec_kwargs: Any) -> Any:
    from agent_app.domain.models import CheckpointMode, RunOptions

    options = spec_kwargs.pop("options", RunOptions())
    options.checkpoint_mode = CheckpointMode.KEY_STAGES
    options.require_user_approval_for_execution = True
    spec = RunSpec(question=question, options=options, **spec_kwargs)
    emit({"type": "start", "question": spec.question})
    runner = self.runner_cls(
        output_root=self.output_root,
        settings=self.settings,
        coordinator_factory=self.coordinator_factory,
        event_handler=emit,
    )
    result = runner.run_until_checkpoint(spec)
    self._emit_result(result, emit)
    return result
```

Extract result emission from `run()` into:

```python
def _emit_result(self, result: Any, emit: PaperEventHandler) -> None:
    for artifact in result.artifacts:
        emit({"type": "artifact", **to_json_dict(artifact)})
    emit(
        {
            "type": "done",
            "run_id": result.run_id,
            "status": result.status.value,
            "stage": result.stage.value,
            "summary": result.summary,
            "artifacts": [to_json_dict(artifact) for artifact in result.artifacts],
            "quality_reports": [to_json_dict(report) for report in result.quality_reports],
        }
    )
    if result.status == RunStatus.FAILED:
        emit({"type": "error", "message": result.summary})
```

- [ ] **Step 4: Run stream tests**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py -q
```

Expected: pass.

- [ ] **Step 5: Review**

Spec review:

- Confirm Web stream defaults to checkpointed mode.
- Confirm checkpoint events can be replayed by the UI.

Quality review:

- Confirm existing `run(spec, emit)` behavior remains available for non-checkpoint clients.
- Confirm runner injection is test-only friendly and does not change production defaults.

- [ ] **Step 6: Commit**

```bash
git add agent_app/web/paper_stream.py agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: stream paper checkpoints"
```

---

## Task 6: Add Checkpoint API Routes

**Files:**

- Modify: `agent_app/web/routes.py`
- Create: `agent_app/tests/test_web_checkpoints.py`

- [ ] **Step 1: Write failing route tests**

Create `agent_app/tests/test_web_checkpoints.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_app.domain.models import CheckpointAction, RunSpec, RunStage
from agent_app.services.checkpoint_service import CheckpointService
from agent_app.services.run_store import RunStore
from agent_app.web.routes import router


def _client_with_run(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    store = RunStore(tmp_path)
    state = store.create_run(RunSpec(question="测试赛题"))
    service = CheckpointService(store)
    checkpoint = service.create_checkpoint(state.run_id, RunStage.UNDERSTAND_PROBLEM, "确认赛题理解")
    monkeypatch.setattr("agent_app.web.routes._checkpoint_run_store", store)
    monkeypatch.setattr("agent_app.web.routes._checkpoint_service", service)
    return TestClient(app), state, checkpoint


def test_get_active_checkpoint_route(tmp_path, monkeypatch):
    client, state, checkpoint = _client_with_run(tmp_path, monkeypatch)

    resp = client.get(f"/api/runs/{state.run_id}/checkpoint")

    assert resp.status_code == 200
    body = resp.json()
    assert body["checkpoint_id"] == checkpoint.checkpoint_id
    assert body["status"] == "awaiting_user"
```

```python
def test_approve_checkpoint_route_records_decision(tmp_path, monkeypatch):
    client, state, checkpoint = _client_with_run(tmp_path, monkeypatch)

    resp = client.post(
        f"/api/runs/{state.run_id}/checkpoints/{checkpoint.checkpoint_id}/approve",
        json={"instruction": "同意"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"]["action"] == CheckpointAction.APPROVE.value
    assert body["resume_plan"]["resume_mode"] == "continue"
```

```python
def test_duplicate_checkpoint_decision_returns_conflict(tmp_path, monkeypatch):
    client, state, checkpoint = _client_with_run(tmp_path, monkeypatch)

    client.post(f"/api/runs/{state.run_id}/checkpoints/{checkpoint.checkpoint_id}/approve", json={})
    resp = client.post(f"/api/runs/{state.run_id}/checkpoints/{checkpoint.checkpoint_id}/revise", json={})

    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest agent_app/tests/test_web_checkpoints.py -q
```

Expected: fail because routes/globals are missing.

- [ ] **Step 3: Add route-level checkpoint service**

In `agent_app/web/routes.py`, add imports:

```python
from fastapi import HTTPException
from agent_app.domain.models import CheckpointAction
from agent_app.domain.serialization import to_json_dict
from agent_app.services.checkpoint_service import CheckpointConflictError, CheckpointNotFoundError, CheckpointService
from agent_app.services.run_store import RunStore
```

Add globals near other route state:

```python
_checkpoint_run_store = RunStore(APP_ROOT / "output" / "runs")
_checkpoint_service = CheckpointService(_checkpoint_run_store)
```

- [ ] **Step 4: Add helper**

```python
def _checkpoint_error_response(exc: Exception):
    if isinstance(exc, CheckpointConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, CheckpointNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    raise exc
```

- [ ] **Step 5: Add routes**

```python
@router.get("/api/runs/{run_id}/checkpoint")
async def get_active_checkpoint(run_id: str):
    checkpoint = _checkpoint_service.get_active_checkpoint(run_id)
    if checkpoint is None:
        return JSONResponse({}, status_code=404)
    return to_json_dict(checkpoint)


@router.get("/api/runs/{run_id}/checkpoints")
async def list_checkpoints(run_id: str):
    return {
        "checkpoints": [to_json_dict(item) for item in _checkpoint_service.list_checkpoints(run_id)],
        "decisions": [to_json_dict(item) for item in _checkpoint_service.list_decisions(run_id)],
    }


def _record_checkpoint_decision(run_id: str, checkpoint_id: str, action: CheckpointAction, data: dict):
    try:
        decision = _checkpoint_service.record_decision(
            run_id=run_id,
            checkpoint_id=checkpoint_id,
            action=action,
            instruction=str(data.get("instruction", "")),
            payload_patch=data.get("payload_patch") or {},
        )
        plan = _checkpoint_service.build_resume_plan(run_id, decision.decision_id)
        return {"decision": to_json_dict(decision), "resume_plan": to_json_dict(plan)}
    except (CheckpointConflictError, CheckpointNotFoundError) as exc:
        return _checkpoint_error_response(exc)


@router.post("/api/runs/{run_id}/checkpoints/{checkpoint_id}/approve")
async def approve_checkpoint(run_id: str, checkpoint_id: str, data: dict):
    return _record_checkpoint_decision(run_id, checkpoint_id, CheckpointAction.APPROVE, data)


@router.post("/api/runs/{run_id}/checkpoints/{checkpoint_id}/revise")
async def revise_checkpoint(run_id: str, checkpoint_id: str, data: dict):
    return _record_checkpoint_decision(run_id, checkpoint_id, CheckpointAction.REVISE, data)


@router.post("/api/runs/{run_id}/checkpoints/{checkpoint_id}/stop")
async def stop_checkpoint(run_id: str, checkpoint_id: str, data: dict):
    return _record_checkpoint_decision(run_id, checkpoint_id, CheckpointAction.STOP, data)
```

- [ ] **Step 6: Add resume task route**

Add a paper resume task store or reuse `_paper_tasks` with explicit resume fields. Minimal route:

```python
@router.post("/api/runs/{run_id}/resume")
async def resume_checkpoint_run(run_id: str, data: dict):
    decision_id = str(data.get("decision_id", "")).strip()
    if not decision_id:
        return JSONResponse({"error": "decision_id required"}, status_code=400)
    task_id = uuid.uuid4().hex[:12]
    async with _paper_tasks_lock:
        _paper_tasks[task_id] = PaperChatRequest(
            question=str(data.get("instruction", "继续执行 checkpoint 后续任务")),
            messages=[],
        )
        _paper_tasks[task_id].resume_run_id = run_id
        _paper_tasks[task_id].resume_decision_id = decision_id
    return {"task_id": task_id, "status": "started"}
```

Extend `PaperChatRequest` with explicit resume fields before using them in `_paper_tasks`:

```python
resume_run_id: str = ""
resume_decision_id: str = ""
```

- [ ] **Step 7: Run route tests**

Run:

```bash
pytest agent_app/tests/test_web_checkpoints.py -q
```

Expected: pass.

- [ ] **Step 8: Review**

Spec review:

- Confirm all required APIs exist except any intentionally deferred UI-only helper.
- Confirm illegal transitions return conflict.

Quality review:

- Confirm route helpers do not duplicate service transition logic.
- Confirm run/checkpoint ownership is validated through `CheckpointService`.

- [ ] **Step 9: Commit**

```bash
git add agent_app/web/routes.py agent_app/tests/test_web_checkpoints.py
git commit -m "feat: expose checkpoint control APIs"
```

---

## Task 7: Wire WebSocket Resume Flow

**Files:**

- Modify: `agent_app/web/paper_stream.py`
- Modify: `agent_app/web/routes.py`
- Modify: `agent_app/tests/test_paper_chat_stream.py`
- Modify: `agent_app/tests/test_web_checkpoints.py`

- [ ] **Step 1: Write failing resume stream test**

Add to `agent_app/tests/test_paper_chat_stream.py`:

```python
def test_paper_stream_resumes_existing_run(tmp_path):
    from agent_app.web.paper_stream import PaperChatStreamer

    captured = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def resume(self, run_id, decision_id):
            captured["run_id"] = run_id
            captured["decision_id"] = decision_id
            from agent_app.domain.models import RunResult, RunStage, RunStatus
            return RunResult(run_id=run_id, status=RunStatus.COMPLETED, stage=RunStage.PACKAGE_SUBMISSION, summary="resumed")

    events = []
    streamer = PaperChatStreamer(output_root=tmp_path, runner_cls=FakeRunner)
    result = streamer.resume("run_1", "decision_1", events.append)

    assert result.status.value == "completed"
    assert captured == {"run_id": "run_1", "decision_id": "decision_1"}
    assert any(event["type"] == "resume_started" for event in events)
    assert any(event["type"] == "done" and event["run_id"] == "run_1" for event in events)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py::test_paper_stream_resumes_existing_run -q
```

Expected: fail because streamer resume method does not exist.

- [ ] **Step 3: Add stream resume method**

Add to `PaperChatStreamer`:

```python
def resume(self, run_id: str, decision_id: str, emit: PaperEventHandler) -> Any:
    emit({"type": "resume_started", "run_id": run_id, "decision_id": decision_id})
    runner = self.runner_cls(
        output_root=self.output_root,
        settings=self.settings,
        coordinator_factory=self.coordinator_factory,
        event_handler=emit,
    )
    result = runner.resume(run_id, decision_id)
    self._emit_result(result, emit)
    return result
```

- [ ] **Step 4: Update websocket handler**

In `ws_paper`, after loading request:

```python
if request.resume_run_id and request.resume_decision_id:
    await asyncio.wait_for(
        asyncio.to_thread(streamer.resume, request.resume_run_id, request.resume_decision_id, emit),
        timeout=SOLVE_TASK_TIMEOUT,
    )
else:
    await asyncio.wait_for(asyncio.to_thread(streamer.run_checkpointed, build_followup_question(request), emit, data_files=request.data_files, reference_files=request.reference_files), timeout=SOLVE_TASK_TIMEOUT)
```

Keep existing non-checkpoint `run` method available for tests and API clients.

- [ ] **Step 5: Run stream and route tests**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py agent_app/tests/test_web_checkpoints.py -q
```

Expected: pass.

- [ ] **Step 6: Review**

Spec review:

- Confirm resume starts a new coordinator invocation via runner.
- Confirm WebSocket events include `resume_started` and final `done`.

Quality review:

- Confirm WebSocket disconnect does not delete persisted checkpoint data.
- Confirm resume route stores enough request state to reconnect.

- [ ] **Step 7: Commit**

```bash
git add agent_app/web/paper_stream.py agent_app/web/routes.py agent_app/tests/test_paper_chat_stream.py agent_app/tests/test_web_checkpoints.py
git commit -m "feat: resume checkpoint runs over paper stream"
```

---

## Task 8: Add Web UI Checkpoint Controls

**Files:**

- Modify: `agent_app/web/templates/index.html`
- Modify: `agent_app/web/static/app.js`
- Modify: `agent_app/web/static/style.css`
- Modify: `agent_app/tests/test_paper_chat_stream.py` or add lightweight static assertions where existing project patterns place them

- [ ] **Step 1: Add static UI assertions**

Add to `agent_app/tests/test_paper_chat_stream.py`:

```python
def test_index_contains_checkpoint_controls():
    from pathlib import Path

    html = Path("agent_app/web/templates/index.html").read_text(encoding="utf-8")
    js = Path("agent_app/web/static/app.js").read_text(encoding="utf-8")

    assert "checkpoint-panel" in html
    assert "approveCheckpoint" in js
    assert "reviseCheckpoint" in js
    assert "stopCheckpoint" in js
```

- [ ] **Step 2: Run static test and verify failure**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py::test_index_contains_checkpoint_controls -q
```

Expected: fail because checkpoint controls are absent.

- [ ] **Step 3: Add checkpoint panel HTML**

In `agent_app/web/templates/index.html`, add a panel in the right rail above artifacts:

```html
<div class="panel checkpoint-panel" id="checkpoint-panel" hidden>
  <div class="panel-label">Checkpoint</div>
  <h3 id="checkpoint-title">等待确认</h3>
  <p id="checkpoint-summary" class="checkpoint-summary"></p>
  <div id="checkpoint-payload" class="checkpoint-payload"></div>
  <textarea id="checkpoint-instruction" rows="4" placeholder="给当前阶段的修改意见，例如：补充约束、替换模型、增强灵敏度分析"></textarea>
  <div class="button-row">
    <button id="btn-checkpoint-approve" onclick="approveCheckpoint()">批准继续</button>
    <button id="btn-checkpoint-revise" class="btn-secondary" onclick="reviseCheckpoint()">要求修改</button>
    <button id="btn-checkpoint-stop" class="btn-secondary" onclick="stopCheckpoint()">稍后处理</button>
  </div>
</div>
```

- [ ] **Step 4: Add JS checkpoint state**

At top of `app.js`:

```javascript
let activeRunId = '';
let activeCheckpoint = null;
```

In `handlePaperEvent`, add cases:

```javascript
case 'checkpoint_created':
case 'checkpoint_updated':
  showCheckpoint(msg);
  break;
case 'checkpoint_decision':
  appendEvent('Checkpoint 决策：' + (msg.action || msg.status), msg.stage);
  break;
case 'resume_started':
  setRunState('Resuming');
  appendEvent('正在从 checkpoint 继续...', msg.stage);
  break;
case 'resume_completed':
  appendEvent('Checkpoint 后续执行完成：' + (msg.status || ''), msg.stage);
  break;
```

In `done` case:

```javascript
activeRunId = msg.run_id || activeRunId;
```

Add functions:

```javascript
function showCheckpoint(event) {
  activeRunId = event.run_id || activeRunId;
  activeCheckpoint = event;
  const panel = document.getElementById('checkpoint-panel');
  if (!panel) return;
  panel.hidden = false;
  document.getElementById('checkpoint-title').textContent = event.title || STAGE_LABELS[event.stage] || 'Checkpoint';
  document.getElementById('checkpoint-summary').textContent = event.summary || '当前阶段需要确认后才能继续。';
  renderCheckpointPayload(event.editable_payload || {});
  setRunState('Needs input', 'var(--orange)');
  setStatus('等待 checkpoint 确认', 'var(--orange)');
}

function renderCheckpointPayload(payload) {
  const el = document.getElementById('checkpoint-payload');
  if (!el) return;
  const keys = Object.keys(payload || {});
  if (!keys.length) {
    el.innerHTML = '<div class="artifact-note">暂无结构化字段，可直接填写修改意见。</div>';
    return;
  }
  el.innerHTML = keys.map(key => {
    const value = Array.isArray(payload[key]) ? payload[key].join('\\n') : JSON.stringify(payload[key], null, 2);
    return '<label>' + key + '</label><textarea data-checkpoint-field="' + key + '" rows="3">' + escapeText(value) + '</textarea>';
  }).join('');
}

function escapeText(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function collectCheckpointPatch() {
  const patch = {};
  document.querySelectorAll('[data-checkpoint-field]').forEach(el => {
    patch[el.getAttribute('data-checkpoint-field')] = el.value;
  });
  return patch;
}

async function checkpointDecision(action) {
  if (!activeRunId || !activeCheckpoint || !activeCheckpoint.checkpoint_id) return;
  const instruction = document.getElementById('checkpoint-instruction').value.trim();
  const resp = await fetch('/api/runs/' + activeRunId + '/checkpoints/' + activeCheckpoint.checkpoint_id + '/' + action, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction, payload_patch: collectCheckpointPatch() }),
  });
  const data = await resp.json();
  if (!resp.ok) {
    setStatus('Checkpoint 操作失败: ' + (data.detail || data.error || resp.status), 'var(--red)');
    return;
  }
  appendEvent('已提交 checkpoint 决策：' + action, activeCheckpoint.stage);
  if (action === 'approve' || action === 'revise') {
    await resumeCheckpoint(data.decision.decision_id, instruction);
  }
}

function approveCheckpoint() {
  checkpointDecision('approve');
}

function reviseCheckpoint() {
  checkpointDecision('revise');
}

function stopCheckpoint() {
  checkpointDecision('stop');
}

async function resumeCheckpoint(decisionId, instruction) {
  const resp = await fetch('/api/runs/' + activeRunId + '/resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision_id: decisionId, instruction: instruction || '继续执行' }),
  });
  const data = await resp.json();
  if (!resp.ok || data.error) {
    setStatus('恢复失败: ' + (data.error || resp.status), 'var(--red)');
    return;
  }
  connectPaperWS(data.task_id);
}
```

- [ ] **Step 5: Add CSS**

Add to `agent_app/web/static/style.css`:

```css
.checkpoint-panel {
  border-color: rgba(245, 158, 11, 0.45);
}

.checkpoint-summary {
  color: var(--text-dim);
  line-height: 1.5;
}

.checkpoint-payload {
  display: grid;
  gap: 8px;
  margin: 10px 0;
}

.checkpoint-payload label {
  font-size: 12px;
  color: var(--text-dim);
}

.checkpoint-payload textarea,
#checkpoint-instruction {
  width: 100%;
  resize: vertical;
}
```

- [ ] **Step 6: Run static and route tests**

Run:

```bash
pytest agent_app/tests/test_paper_chat_stream.py::test_index_contains_checkpoint_controls agent_app/tests/test_web_checkpoints.py -q
```

Expected: pass.

- [ ] **Step 7: Review**

Spec review:

- Confirm UI exposes approve, revise, and stop.
- Confirm user can submit natural-language instruction and payload patch.

Quality review:

- Confirm text fits inside panels on narrow widths.
- Confirm no nested card structure is added.
- Confirm buttons are disabled or harmless when no active checkpoint exists.

- [ ] **Step 8: Commit**

```bash
git add agent_app/web/templates/index.html agent_app/web/static/app.js agent_app/web/static/style.css agent_app/tests/test_paper_chat_stream.py
git commit -m "feat: add checkpoint controls to paper UI"
```

---

## Task 9: Browser QA And Regression

**Files:**

- No code files unless QA finds defects.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
pytest agent_app/tests/test_checkpoint_service.py agent_app/tests/test_checkpoint_runner.py agent_app/tests/test_stage_middleware.py agent_app/tests/test_paper_chat_stream.py agent_app/tests/test_web_checkpoints.py -q
```

Expected: all pass.

- [ ] **Step 2: Run full agent_app regression**

Run:

```bash
pytest agent_app/tests -q
```

Expected: all pass. Investigate any failures before continuing.

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Start local service**

Run:

```bash
uvicorn agent_app.web.main:app --host 127.0.0.1 --port 8001
```

Expected: service starts on port 8001.

- [ ] **Step 5: Browser QA**

Use Browser plugin against `http://127.0.0.1:8001`:

- Start a short paper run.
- Confirm progress events stream.
- Confirm checkpoint card appears at the first key stage.
- Click approve.
- Confirm resume starts and events continue.
- Start or reload a paused run if run history is available and confirm checkpoint state is recoverable.
- Click revise on another run or mocked checkpoint if real model cost/time is high.
- Confirm UI remains readable on desktop and mobile widths.

- [ ] **Step 6: Stop local service**

Stop the uvicorn session before final response.

- [ ] **Step 7: Final two reviews**

Spec review:

- Check every Acceptance Criteria bullet in the spec.
- Record any intentional deferrals.

Quality review:

- Check code ownership boundaries.
- Check tests cover success, conflict, and failure paths.
- Check no unrelated files were modified.

- [ ] **Step 8: Commit QA fixes**

When QA required code changes, stage the exact changed feature files and commit:

```bash
git status --short
git add agent_app
git commit -m "fix: polish checkpoint workflow qa"
```

---

## Final Acceptance Checklist

- [ ] `RunOptions` supports checkpoint configuration with autonomous defaults.
- [ ] Checkpoint domain models serialize and deserialize.
- [ ] `CheckpointService` persists checkpoints and decisions under each run.
- [ ] Duplicate and illegal decisions return clear conflicts.
- [ ] Stage middleware blocks advancement while awaiting user.
- [ ] Runner can pause at a key checkpoint.
- [ ] Runner can resume from approval.
- [ ] Runner can re-enter a stage from revision.
- [ ] Web APIs expose active checkpoint, history, approve, revise, stop, and resume.
- [ ] WebSocket stream emits checkpoint and resume events.
- [ ] Web UI renders checkpoint controls and submits decisions.
- [ ] Paused runs remain recoverable after WebSocket disconnect.
- [ ] Existing autonomous paper runs remain available.
- [ ] Full `agent_app/tests` passes.
- [ ] Browser QA passes.
- [ ] Service is stopped after QA.

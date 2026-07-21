# DeepAgent Native Runtime Foundation Implementation Plan

> **Execution policy:** Implement inline on
> `codex/deepagent-native-rearchitecture`. Do not invoke Superpowers-prefixed skills or
> development subagents. Complete tasks in order and use the checkboxes for tracking.

**Goal:** Build the durable, testable control-plane foundation required by the native
DeepAgent loop while leaving the current paper runner behavior available and unchanged by
default.

**Architecture:** Add a run-scoped SQLite/WAL runtime database under `.runtime/` and
focused services for events, artifacts, budgets, steering, tool execution, and completion.
`run.json` remains a compatibility projection. This phase does not yet change the default
coordinator or expose new Web views; Phase 2 connects these services to native DeepAgent.

**Tech stack:** Python 3.13, stdlib `sqlite3`, dataclasses, SHA-256, DeepAgents 0.6.8,
LangChain middleware contracts, pytest.

**Source spec:**
`docs/superpowers/specs/2026-07-21-deepagent-native-paper-factory-design.md`

---

## Baseline And Scope

Verified before writing this plan:

```text
python -m pytest \
  agent_app/tests/test_deepagent_coordinator.py \
  agent_app/tests/test_competition_runner.py \
  agent_app/tests/test_run_store.py \
  agent_app/tests/test_stage_middleware.py \
  agent_app/tests/test_paper_chat_stream.py -q

40 passed, 9 warnings
```

Included:

- runtime contracts and native runtime statuses;
- schema-versioned SQLite runtime storage;
- append-only events and deterministic status projection;
- versioned artifact graph with transitive invalidation;
- budget reservations, steering inbox, and compact context manifests;
- tool policy, idempotency, prepared execution records, and reconciliation;
- deterministic completion supervision and no-progress detection;
- standalone runtime bootstrap and recovery projection;
- compatibility and recovery tests.

Excluded from this phase:

- changing the default coordinator prompt or tool order;
- modifying `RunStore`, `CompetitionPaperRunner`, `RunStatus`, or current Web behavior;
- registering native DeepAgent subagents;
- SQLite LangGraph checkpoint wiring;
- AutoSOTA trials, reviewers, paper revisions, and new Web panels;
- deleting `CompetitionStageMiddleware`, `EventDrivingCoordinator`, or the legacy
  `agent_loop` path.

### Dirty-work boundary

At plan time, `.gitignore`, `agent_app/.env.example`, `agent_app/README.md`,
`agent_app/config.py`, `agent_app/deepagent/runner.py`, domain model/serialization files,
RAG and competition services, Web routes, and several tests already contain uncommitted
work. Phase 1 deliberately avoids those tracked paths. Before modifying
`agent_app/services/run_trace.py` and `agent_app/tests/test_run_trace.py`, verify they are
still clean; if they changed, preserve the new work and reconcile before editing.

## File Layout

Create:

- `agent_app/runtime/__init__.py`: exported runtime surface.
- `agent_app/runtime/contracts.py`: immutable runtime value objects and enums.
- `agent_app/runtime/database.py`: SQLite connection, migrations, and transactions.
- `agent_app/runtime/event_ledger.py`: append, replay, idempotency, and status projection.
- `agent_app/runtime/artifact_graph.py`: artifact versions, dependencies, and invalidation.
- `agent_app/runtime/budget.py`: atomic reserve, settle, and release operations.
- `agent_app/runtime/steering.py`: ordered user command inbox.
- `agent_app/runtime/context.py`: bounded context-manifest construction.
- `agent_app/runtime/tool_policy.py`: tool contracts and preflight decisions.
- `agent_app/runtime/tool_execution.py`: prepared/committed execution records.
- `agent_app/runtime/completion.py`: completion verdicts and continuation tracking.
- `agent_app/runtime/bootstrap.py`: one run's runtime service bundle.
- `agent_app/infra/redaction.py`: shared secret redaction for trace and event persistence.
- `agent_app/tests/test_native_runtime_contracts.py`
- `agent_app/tests/test_runtime_database.py`
- `agent_app/tests/test_runtime_event_ledger.py`
- `agent_app/tests/test_runtime_artifact_graph.py`
- `agent_app/tests/test_runtime_control_ledgers.py`
- `agent_app/tests/test_runtime_tool_policy.py`
- `agent_app/tests/test_runtime_tool_execution.py`
- `agent_app/tests/test_runtime_completion.py`
- `agent_app/tests/test_runtime_bootstrap.py`
- `docs/runbooks/deepagent-native-runtime.md`

## Task 1: Lock Runtime Contracts And Status Semantics

**Files:**

- Create `agent_app/runtime/contracts.py`
- Create `agent_app/runtime/__init__.py`
- Create `agent_app/tests/test_native_runtime_contracts.py`

- [ ] Write serialization round-trip tests for `RuntimeStatus`, `GoalEnvelope`,
  `NewRunEvent`, `RunEvent`,
  `ArtifactVersion`, `BudgetSnapshot`, `SteeringCommand`, `ContextManifest`,
  `CompletionCondition`, `CompletionVerdict`, and `ContinuationDirective` using the
  existing `to_json_dict` and `from_json_dict` helpers.

- [ ] Add this status-compatibility test:

```python
def test_runtime_status_covers_native_wait_and_revision_states():
    assert {status.value for status in RuntimeStatus} == {
        "pending", "running", "completed", "failed", "partial",
        "waiting_user", "waiting_external", "revision_required", "cancelled",
    }
```

- [ ] Define the core enums and immutable contracts with these public fields:

```python
class ArtifactState(str, Enum):
    PREPARED = "prepared"
    VALID = "valid"
    STALE = "stale"

class RuntimeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    WAITING_EXTERNAL = "waiting_external"
    REVISION_REQUIRED = "revision_required"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class SteeringKind(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    CORRECT = "correct"
    ANSWER = "answer"

@dataclass(frozen=True)
class GoalEnvelope:
    run_id: str
    objective: str
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    mode: str = "autopilot"
    revision: int = 1

@dataclass(frozen=True)
class RunEvent:
    sequence_id: int
    event_id: str
    run_id: str
    event_type: str
    actor_id: str
    payload: dict[str, Any]
    correlation_id: str = ""
    causation_id: str = ""
    idempotency_key: str = ""
    created_at: str = ""

@dataclass(frozen=True)
class ArtifactVersion:
    artifact_id: str
    run_id: str
    logical_path: Path
    kind: str
    version: int
    digest: str
    state: ArtifactState
    produced_by_event_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NewRunEvent:
    event_id: str
    run_id: str
    event_type: str
    actor_id: str
    payload: dict[str, Any]
    correlation_id: str = ""
    causation_id: str = ""
    idempotency_key: str = ""

@dataclass(frozen=True)
class BudgetSnapshot:
    account: str
    limit: int
    reserved: int
    consumed: int
    unit: str

@dataclass(frozen=True)
class SteeringCommand:
    command_id: str
    run_id: str
    kind: SteeringKind
    payload: dict[str, Any]
    status: str = "pending"
    created_at: str = ""

@dataclass(frozen=True)
class ContextManifest:
    run_id: str
    goal_digest: str
    artifact_digests: dict[str, str]
    unresolved_condition_codes: list[str]
    failed_approaches: list[str]
    budgets: list[BudgetSnapshot]
    pending_steering_ids: list[str]
    active_task_ids: list[str]
    created_at: str = ""

@dataclass(frozen=True)
class CompletionCondition:
    code: str
    passed: bool
    blocking: bool
    message: str
    artifact_ids: tuple[str, ...] = ()
    resolution: str = "agent"

@dataclass(frozen=True)
class CompletionVerdict:
    passed: bool
    conditions: tuple[CompletionCondition, ...]
    failure_signature: str

@dataclass(frozen=True)
class ContinuationDirective:
    unsatisfied_codes: tuple[str, ...]
    messages: tuple[str, ...]
    stale_artifact_ids: tuple[str, ...]
    available_capabilities: tuple[str, ...]
    remaining_budgets: tuple[BudgetSnapshot, ...]
```

- [ ] Validate nonblank IDs and objectives, positive versions, 64-character lowercase
  SHA-256 digests, nonnegative budget amounts, and nonblank completion condition codes in
  `__post_init__` methods.

- [ ] Export the contract surface from `agent_app.runtime` and run:

```bash
python -m pytest agent_app/tests/test_native_runtime_contracts.py -q
```

Expected: all contract tests pass and existing domain serialization tests remain green.

- [ ] Commit only Task 1 files:

```bash
git add agent_app/runtime/__init__.py agent_app/runtime/contracts.py \
  agent_app/tests/test_native_runtime_contracts.py
git commit -m "feat: add native runtime contracts"
```

## Task 2: Add The Run-Scoped SQLite Database

**Files:**

- Create `agent_app/runtime/database.py`
- Create `agent_app/tests/test_runtime_database.py`

- [ ] Write failing tests that open two `RuntimeDatabase` instances on the same file,
  verify `PRAGMA journal_mode=WAL`, verify `PRAGMA foreign_keys=ON`, and assert schema
  version `1` is applied exactly once.

- [ ] Implement `RuntimeDatabase(path: Path)` with one connection per operation,
  `busy_timeout=5000`, `sqlite3.Row`, and this transaction boundary:

```python
@contextmanager
def transaction(self) -> Iterator[sqlite3.Connection]:
    connection = self.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
```

- [ ] Create migration 1 with normalized tables for `runtime_schema`, `events`,
  `artifacts`, `artifact_dependencies`, `budgets`, `budget_reservations`, `steering`,
  `context_manifests`, and `tool_executions`. Add uniqueness for event IDs,
  `(run_id, idempotency_key)` when the key is nonblank, artifact path/version, steering
  command IDs, and tool-execution idempotency keys.

- [ ] Store JSON as canonical UTF-8 text with `sort_keys=True` and reject non-object event
  payloads at service boundaries.

- [ ] Run the database tests twice against the same temporary file to prove migration
  idempotency.

```bash
python -m pytest agent_app/tests/test_runtime_database.py -q
python -m pytest agent_app/tests/test_runtime_database.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/database.py agent_app/tests/test_runtime_database.py
git commit -m "feat: add runtime sqlite schema"
```

## Task 3: Implement The Append-Only Event Ledger

**Files:**

- Create `agent_app/runtime/event_ledger.py`
- Create `agent_app/infra/redaction.py`
- Modify `agent_app/services/run_trace.py`
- Modify `agent_app/tests/test_runtime_event_ledger.py`
- Modify `agent_app/tests/test_run_trace.py`

- [ ] Write failing tests for monotonic sequence IDs, `list_after(sequence_id)`, bounded
  limits, duplicate idempotency replay, conflicting idempotency payloads, and status
  projection from `run.status_changed` events only.

- [ ] Implement this public API:

```python
class EventLedger:
    def append(self, event: NewRunEvent) -> RunEvent: ...
    def get(self, run_id: str, event_id: str) -> RunEvent | None: ...
    def list_after(self, run_id: str, sequence_id: int = 0, limit: int = 500) -> list[RunEvent]: ...
    def project_status(self, run_id: str,
                       default: RuntimeStatus = RuntimeStatus.PENDING) -> RuntimeStatus: ...
```

- [ ] On duplicate `(run_id, idempotency_key)`, return the existing event only when event
  type and canonical payload digest match. Raise `IdempotencyConflict` otherwise.

- [ ] Make public `append()` own a transaction and provide a private
  `_append_in_transaction(connection, event)` for artifact and tool services that already
  hold the runtime transaction. Do not open nested SQLite transactions.

- [ ] Move the existing exact-key, key-pattern, and text-pattern redaction into
  `agent_app.infra.redaction.redact_payload()` and `redact_text()`. Make
  `RunTraceWriter` and `EventLedger` call the same helpers so trace and ledger behavior
  cannot diverge.

- [ ] Enforce `1 <= limit <= 1000`, redact secrets before persistence, and never store
  hidden reasoning or credentials.

- [ ] Verify status cannot change from `tool.completed`, `artifact.created`, or a Web
  acknowledgement event.

- [ ] Run:

```bash
python -m pytest agent_app/tests/test_runtime_event_ledger.py \
  agent_app/tests/test_run_trace.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/event_ledger.py agent_app/infra/redaction.py \
  agent_app/services/run_trace.py agent_app/tests/test_runtime_event_ledger.py \
  agent_app/tests/test_run_trace.py
git commit -m "feat: add append-only runtime events"
```

## Task 4: Implement Artifact Versions And Dependency Invalidation

**Files:**

- Create `agent_app/runtime/artifact_graph.py`
- Create `agent_app/tests/test_runtime_artifact_graph.py`

- [ ] Write failing tests for first registration, unchanged-content idempotency, changed
  content creating version 2, path traversal rejection, symlink rejection, dependency
  insertion, and transitive invalidation across result -> claim -> section -> package.

- [ ] Implement `ArtifactGraph` with these operations:

```python
class ArtifactGraph:
    def register_file(self, run_id: str, relative_path: Path, kind: str,
                      produced_by_event_id: str, metadata: dict[str, Any] | None = None
                      ) -> ArtifactVersion: ...
    def current(self, run_id: str, relative_path: Path) -> ArtifactVersion | None: ...
    def add_dependency(self, parent_artifact_id: str, child_artifact_id: str) -> None: ...
    def invalidate_descendants(self, artifact_id: str, reason: str) -> list[ArtifactVersion]: ...
    def list_current(self, run_id: str, include_stale: bool = False) -> list[ArtifactVersion]: ...
```

- [ ] Resolve every path beneath the run directory, compute SHA-256 from bytes, and use a
  recursive CTE inside one transaction to mark all descendants stale.

- [ ] Emit one `artifact.versioned` event for a new digest and one
  `artifact.invalidated` event containing all invalidated IDs. Do not emit a new version
  for unchanged content.

- [ ] Provide private transaction-aware helpers used by `ToolExecutionStore`, so artifact
  rows and their events can commit on the caller's existing SQLite connection instead of
  opening nested transactions.

- [ ] Run:

```bash
python -m pytest agent_app/tests/test_runtime_artifact_graph.py \
  agent_app/tests/test_run_store.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/artifact_graph.py agent_app/tests/test_runtime_artifact_graph.py
git commit -m "feat: add versioned artifact graph"
```

## Task 5: Add Budget, Steering, And Context Services

**Files:**

- Create `agent_app/runtime/budget.py`
- Create `agent_app/runtime/steering.py`
- Create `agent_app/runtime/context.py`
- Create `agent_app/tests/test_runtime_control_ledgers.py`

- [ ] Write failing budget tests for atomic reservation, over-budget rejection, settlement
  below and above reserved amount, release, duplicate reservation IDs, and concurrent
  reservations against one limit.

- [ ] Implement `BudgetLedger.configure`, `reserve`, `settle`, `release`, and `snapshot`.
  Use integer base units for tokens, milliseconds, trial counts, and micro-currency; do
  not store floating-point money.

- [ ] Write failing steering tests proving FIFO order, idempotent command IDs, one-time
  consumption, and that a later correction remains pending after a pause is consumed.

- [ ] Implement `SteeringInbox.enqueue`, `pending`, `consume`, and `mark_rejected` without
  modifying the `GoalEnvelope` inside the inbox service.

- [ ] Implement `ContextManifestBuilder.build(run_id)` to include the goal digest, current
  artifact IDs and digests, unresolved completion codes, failed approach summaries,
  budget snapshots, pending steering IDs, and active task IDs. Enforce configurable item
  and character caps and persist the resulting manifest.

- [ ] Run:

```bash
python -m pytest agent_app/tests/test_runtime_control_ledgers.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/budget.py agent_app/runtime/steering.py \
  agent_app/runtime/context.py agent_app/tests/test_runtime_control_ledgers.py
git commit -m "feat: add runtime control ledgers"
```

## Task 6: Add Tool Contracts And Policy Preflight

**Files:**

- Create `agent_app/runtime/tool_policy.py`
- Create `agent_app/tests/test_runtime_tool_policy.py`

- [ ] Write failing tests for role denial, deny-over-allow precedence, missing artifact
  versions, exhausted budget, protected writes, required interrupt, valid execution, and
  the rule that policy reports conditions but never selects a different tool.

- [ ] Define the public policy types:

```python
class SideEffectClass(str, Enum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    SANDBOX_EXECUTION = "sandbox_execution"
    EXTERNAL = "external"

@dataclass(frozen=True)
class ToolContract:
    name: str
    allowed_roles: frozenset[str]
    side_effect: SideEffectClass
    required_artifacts: tuple[str, ...] = ()
    read_scopes: tuple[str, ...] = ()
    write_scopes: tuple[str, ...] = ()
    budget_account: str = ""
    budget_amount: int = 0
    timeout_seconds: int = 30
    interrupt_required: bool = False

@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    code: str
    message: str
    missing_conditions: tuple[str, ...] = ()
    interrupt_required: bool = False
```

- [ ] Implement immutable `ToolContractRegistry` registration with duplicate-name
  rejection and `ToolPolicy.evaluate(invocation)` using artifact, budget, role, path, and
  interrupt services.

- [ ] Return stable codes including `permission_denied`, `precondition_missing`,
  `version_conflict`, `budget_exhausted`, `interrupt_required`, and `allowed`.

- [ ] Run:

```bash
python -m pytest agent_app/tests/test_runtime_tool_policy.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/tool_policy.py agent_app/tests/test_runtime_tool_policy.py
git commit -m "feat: add native tool policy"
```

## Task 7: Implement Idempotent Tool Execution Records

**Files:**

- Create `agent_app/runtime/tool_execution.py`
- Create `agent_app/tests/test_runtime_tool_execution.py`

- [ ] Write failing tests for `prepared -> committed`, committed replay, conflicting input
  digest, failed execution, a prepared record whose final file exists with the expected
  digest, and a prepared record whose file is missing or mismatched.

- [ ] Implement `ToolExecutionStore.prepare`, `commit`, `fail`, `get`, and `reconcile`.
  States are `prepared`, `committed`, `failed`, and `needs_repair`; terminal committed
  records are immutable.

- [ ] Require every preparation to include `run_id`, tool name, role, idempotency key,
  canonical input digest, expected relative write paths, and budget reservation ID.

- [ ] Treat policy budget checks as advisory. `prepare()` must either create the budget
  reservation in the same runtime transaction or validate an existing reservation for
  the same invocation; this closes the race between preflight and execution.

- [ ] Reconciliation may commit only when every expected file stays under the run root and
  matches its recorded SHA-256 digest. Otherwise mark `needs_repair` and return a
  machine-readable failure; never rerun automatically in this service.

- [ ] Commit event metadata and artifact rows in one SQLite transaction after files have
  been atomically renamed by the caller. Add a failure-injection test between rename and
  ledger commit.

- [ ] Run:

```bash
python -m pytest agent_app/tests/test_runtime_tool_execution.py \
  agent_app/tests/test_runtime_artifact_graph.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/tool_execution.py agent_app/tests/test_runtime_tool_execution.py
git commit -m "feat: add idempotent tool execution ledger"
```

## Task 8: Implement Completion Supervision And No-Progress Detection

**Files:**

- Create `agent_app/runtime/completion.py`
- Create `agent_app/tests/test_runtime_completion.py`

- [ ] Write failing tests proving that missing goals, stale artifacts, failed deterministic
  validators, unresolved blocking reviews, mismatched package versions, and absent frozen
  results reject completion.

- [ ] Define `CompletionCheck` as a protocol returning `CompletionCondition` and implement
  `CompletionSupervisor.evaluate(run_id, checks) -> CompletionVerdict`. A passing verdict
  requires every blocking condition to pass; scores and nonblocking praise cannot override
  a blocking failure.

- [ ] Implement `ContinuationDirective.from_verdict(verdict, remaining_budget)` with only
  unsatisfied condition codes, messages, stale artifact IDs, available capability names,
  and remaining budgets. Do not include a tool name or stage name field.

- [ ] Implement `ContinuationTracker.record(run_id, verdict, progress_digest)` and return
  `revision_required`, `waiting_user`, or `partial` only after three identical failure
  signatures with no changed progress digest.

- [ ] Add a regression test where an agent claims success after creating only
  `modeling_report.md`; the supervisor must reject completion without selecting
  `run_experiment` or any other action.

- [ ] Run:

```bash
python -m pytest agent_app/tests/test_runtime_completion.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/completion.py agent_app/tests/test_runtime_completion.py
git commit -m "feat: add deterministic completion supervision"
```

## Task 9: Bootstrap One Run And Prove Recovery

**Files:**

- Create `agent_app/runtime/bootstrap.py`
- Create `agent_app/tests/test_runtime_bootstrap.py`

- [ ] Write failing tests that `bootstrap_runtime(run_id, run_dir, goal)` creates
  `.runtime/runtime.sqlite3`, records `run.created` and
  `run.status_changed(pending)`, returns one coherent `RuntimeServices` bundle, and
  reconstructs the latest status from a newly opened bundle.

- [ ] Define `RuntimeServices` with one `RuntimeDatabase`, `EventLedger`, `ArtifactGraph`,
  `BudgetLedger`, `SteeringInbox`, `ContextManifestBuilder`, `ToolExecutionStore`,
  `CompletionSupervisor`, and `ContinuationTracker`. Construct it from explicit `run_id`
  and `run_dir` without global mutable state.

- [ ] Implement `bootstrap_runtime()` as idempotent. A second call with the same goal
  digest reopens the runtime without duplicate events; a conflicting initial goal raises
  `RuntimeBootstrapConflict`.

- [ ] Add `RuntimeServices.transition_status(status, actor_id, causation_id="")`. Repeating
  the same transition with the same causation ID must return the existing event. Invalid
  terminal-to-running transitions fail deterministically.

- [ ] Add `RuntimeServices.recovery_snapshot()` returning status, current artifacts,
  budgets, pending steering, unresolved completion conditions, and latest sequence ID.
  Prove the snapshot is identical after closing and reopening every service.

- [ ] Assert all runtime files stay beneath `<run_dir>/.runtime/`. Phase 2 owns the
  `RunStore` and artifact-collector integration that keeps this directory private.

- [ ] Run:

```bash
python -m pytest \
  agent_app/tests/test_runtime_bootstrap.py \
  agent_app/tests/test_runtime_event_ledger.py \
  agent_app/tests/test_runtime_artifact_graph.py \
  agent_app/tests/test_runtime_completion.py -q
```

- [ ] Commit:

```bash
git add agent_app/runtime/bootstrap.py agent_app/tests/test_runtime_bootstrap.py
git commit -m "feat: bootstrap durable run runtime"
```

## Task 10: Document And Verify The Phase Boundary

**Files:**

- Create `docs/runbooks/deepagent-native-runtime.md`

- [ ] Document `.runtime/runtime.sqlite3`, event authority, artifact versions, explicit
  status transitions, and why `run.json` remains a compatibility projection.

- [ ] State clearly that Phase 1 does not modify `RunStore`, enable native orchestration,
  register subagents, or change Web behavior and does not require a model API call.

- [ ] Run all new runtime tests:

```bash
python -m pytest \
  agent_app/tests/test_native_runtime_contracts.py \
  agent_app/tests/test_runtime_database.py \
  agent_app/tests/test_runtime_event_ledger.py \
  agent_app/tests/test_runtime_artifact_graph.py \
  agent_app/tests/test_runtime_control_ledgers.py \
  agent_app/tests/test_runtime_tool_policy.py \
  agent_app/tests/test_runtime_tool_execution.py \
  agent_app/tests/test_runtime_completion.py \
  agent_app/tests/test_runtime_bootstrap.py -q
```

Expected: all tests pass without network or API credentials.

- [ ] Run the existing compatibility set:

```bash
python -m pytest \
  agent_app/tests/test_deepagent_coordinator.py \
  agent_app/tests/test_competition_runner.py \
  agent_app/tests/test_run_store.py \
  agent_app/tests/test_stage_middleware.py \
  agent_app/tests/test_paper_chat_stream.py -q
```

Expected: at least the verified 40 baseline tests pass; any added compatibility tests also
pass.

- [ ] Run the full suite and static checks:

```bash
python -m pytest agent_app/tests -q
python -m py_compile \
  agent_app/runtime/contracts.py agent_app/runtime/database.py \
  agent_app/runtime/event_ledger.py agent_app/runtime/artifact_graph.py \
  agent_app/runtime/budget.py agent_app/runtime/steering.py \
  agent_app/runtime/context.py agent_app/runtime/tool_policy.py \
  agent_app/runtime/tool_execution.py agent_app/runtime/completion.py \
  agent_app/runtime/bootstrap.py
git diff --check
git status --short
```

- [ ] Confirm only Phase 1 paths are staged and that pre-existing knowledge, RAG, paper,
  and `zhihu_fiction/mcp_server` changes remain untouched.

- [ ] Commit documentation:

```bash
git add docs/runbooks/deepagent-native-runtime.md
git commit -m "docs: describe native runtime foundation"
```

## Phase 1 Exit Criteria

Phase 1 is complete only when:

1. runtime state can be reconstructed from SQLite after ignoring `run.json`;
2. event sequence and status projection are deterministic;
3. artifact versioning and transitive invalidation are tested;
4. budgets and steering are transactionally durable;
5. duplicate committed tool requests replay without side effects;
6. prepared executions reconcile safely after a simulated crash;
7. completion supervision rejects unsupported success without choosing a repair action;
8. runtime files are confined to `.runtime/` and the Phase 2 integration contract marks
   that path private;
9. focused, compatibility, and full test suites pass;
10. the default production behavior is still the existing compatibility runtime.

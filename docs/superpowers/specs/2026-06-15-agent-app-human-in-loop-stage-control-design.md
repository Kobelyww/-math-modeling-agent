# Agent App Human-In-Loop Stage Control Design

Date: 2026-06-15

## Goal

Turn the DeepAgent paper workflow into a controllable research workspace where a user can pause at important stages, inspect intermediate outputs, edit assumptions or plans, approve continuation, reject weak work, and resume a run without restarting from scratch.

This stage should make the system feel less like a one-shot demo and more like an industrial paper-production assistant for mathematical modeling competitions and research papers.

## Product Outcome

After this feature is implemented, a user should be able to:

- Start a paper run from the Web UI.
- Watch each stage stream live progress.
- See review checkpoints for problem understanding, data audit, model plan, experiment plan, draft paper, and final package.
- Pause a run at configured checkpoints.
- Edit checkpoint artifacts or submit natural-language revision instructions.
- Approve the current stage and continue execution.
- Reject a stage and ask the responsible agent/subagent to revise it.
- Recover a paused, partial, or failed run from run history.
- Resume from the last safe checkpoint instead of creating a brand-new run.

## Current Baseline

The project already has:

- `CompetitionPaperRunner` as the stable paper workflow entrypoint.
- `RunSpec`, `RunState`, `RunStage`, `RunStatus`, artifacts, issues, quality reports, and run persistence.
- DeepAgent coordinator and stage middleware enforcing ordered tool usage.
- Paper Web chat streaming through structured events.
- Run event persistence and downloadable submission bundles.
- Output profiles and specialized DeepAgent subagents.
- A hardened stage middleware that prevents later stages from racing ahead after failures.

Current limitations:

- A run is mostly autonomous once started.
- Users cannot approve, reject, or revise intermediate stage outputs before the next stage begins.
- Follow-up instructions create another run-shaped interaction rather than a true checkpoint resume.
- Stage state does not yet encode "waiting for user" as a first-class lifecycle state.
- Web UI has progress visibility but not workflow control.

## Confirmed Scope

This spec covers one implementation phase:

1. Add first-class stage checkpoints and human decisions.
2. Persist checkpoint payloads and user decisions.
3. Add pause, approve, reject, revise, and resume APIs.
4. Update the Web UI to expose checkpoint controls in the chat-driven workflow.
5. Integrate checkpoint decisions into the DeepAgent stage middleware and paper runner.

This spec does not replace the existing runner, tools, or subagent architecture. It extends them with a control plane.

## Non-Goals

- No full collaborative multi-user editing.
- No database migration; keep JSON-on-disk persistence for this phase.
- No real-time collaborative document editor.
- No arbitrary stage graph editing by the user.
- No manual override that marks an unexecuted stage as completed.
- No hidden fallback that fabricates missing experiment results.

## User Experience

The Web UI remains a production work surface:

- Left rail: run inputs, profile, assets, run history.
- Center: streaming chat, checkpoint prompts, user decisions, revision messages.
- Right rail: stage timeline, checkpoint status, artifacts, quality gates.
- Bottom composer: natural-language instruction box that can submit a normal follow-up or respond to the active checkpoint.

When a checkpoint is reached, the UI should show:

- Stage name and responsible agent/subagent.
- Short summary of the stage output.
- Linked artifacts produced by the stage.
- Risks, missing inputs, or quality findings.
- Three primary actions: approve, request revision, stop here.
- Optional editable structured fields when the stage output has an editable contract.

Example checkpoint actions:

- `approve`: continue to the next stage.
- `revise`: send user instruction to the same stage owner and rerun or patch the stage output.
- `stop`: keep the run paused for later.

## Stage Lifecycle

Add an explicit checkpoint-aware lifecycle separate from `RunStatus`:

- `pending`: stage has not started.
- `running`: stage is actively executing.
- `awaiting_user`: stage reached a checkpoint and is paused.
- `approved`: user approved the checkpoint.
- `revising`: stage is being revised after user feedback.
- `completed`: stage finished and may advance.
- `failed`: stage failed and requires recovery or a new run.
- `skipped`: stage was intentionally skipped by policy, never by silent failure.

`RunStatus` should stay coarse-grained:

- `RUNNING`: active execution.
- `PARTIAL`: paused, waiting for user, or completed with missing required outputs.
- `FAILED`: unrecoverable error.
- `COMPLETED`: all required stages and final gates passed.

When a run is waiting at a checkpoint, store `RunStatus.PARTIAL` and expose a clear `awaiting_user` checkpoint in the run detail API.

## Checkpoint Model

Add domain models:

- `StageCheckpoint`
  - `checkpoint_id`
  - `run_id`
  - `stage`
  - `status`
  - `title`
  - `summary`
  - `editable_payload`
  - `artifacts`
  - `quality_reports`
  - `created_at`
  - `resolved_at`

- `CheckpointDecision`
  - `decision_id`
  - `checkpoint_id`
  - `run_id`
  - `stage`
  - `action`: `approve`, `revise`, `stop`
  - `instruction`
  - `payload_patch`
  - `created_at`

- `ResumePlan`
  - `run_id`
  - `from_stage`
  - `decision_id`
  - `resume_mode`: `continue`, `revise_stage`, `replay_from_checkpoint`
  - `reason`

The first implementation should keep payloads JSON-compatible dictionaries. Later phases may introduce stricter per-stage schemas.

## Checkpoint Policy

Default checkpoints:

- After `UNDERSTAND_PROBLEM`: approve problem interpretation and deliverables.
- After `AUDIT_DATA`: approve data quality summary and missing-data assumptions.
- After `PLAN_MODELING`: approve model strategy, assumptions, variables, and evaluation plan.
- Before `RUN_EXPERIMENTS`: approve generated experiment plan and execution policy.
- After `DRAFT_PAPER`: approve draft structure before review/revision loop.
- Before `PACKAGE_SUBMISSION`: approve final paper and artifacts.

Checkpoint behavior should be configurable through `RunOptions`:

- `checkpoint_mode`: `none`, `key_stages`, `all_stages`.
- `auto_approve_timeout_seconds`: optional; default disabled.
- `require_user_approval_for_execution`: default `true` for local code execution.

Default Web behavior should use `key_stages`.
CLI behavior can default to `none` to preserve existing automation unless a flag enables checkpoints.

## Backend Architecture

Add a focused service:

- `agent_app/services/checkpoint_service.py`

Responsibilities:

- Create checkpoint records under `agent_app/output/runs/<run_id>/checkpoints/`.
- Load latest active checkpoint for a run.
- Persist user decisions.
- Validate decision transitions.
- Build resume plans.
- Expose checkpoint summaries for Web and history APIs.

Do not put checkpoint persistence directly in Web routes or DeepAgent middleware. The service should own the transition rules so CLI, Web, and future APIs behave consistently.

## Runner Integration

`CompetitionPaperRunner` should gain a resumable execution path without breaking `run(spec)`:

- `run(spec)` remains the full autonomous entrypoint.
- `run_until_checkpoint(spec)` creates a new run and pauses at the first configured checkpoint.
- `resume(run_id, decision)` continues or revises from the checkpoint.

The runner should persist state before and after every checkpoint decision. If resume fails, the previous checkpoint and decision history remain readable.

For the initial implementation, resume can be stage-level rather than token-level:

- Approved checkpoint continues from the next stage.
- Revision checkpoint re-invokes the stage-specific tool/subagent with prior outputs and user feedback.
- Replay from checkpoint reloads persisted stage inputs and artifacts.

DeepAgent execution is controlled at stage boundaries, not by interrupting an in-flight model call. When a checkpoint is required, the coordinator prompt and stage middleware must stop the workflow after the checkpoint stage and return a paused `RunResult`. A later resume call starts a new coordinator invocation with:

- the same `run_id` and `run_dir`;
- the approved or revised checkpoint decision;
- the next required stage list;
- references to prior artifacts and stage summaries.

This makes resume deterministic enough for the first industrial implementation while avoiding fragile token-level cancellation.

## DeepAgent And Middleware Integration

The stage middleware remains the ordering authority for tool calls. Checkpoints should be integrated as a controlled gate:

- When a checkpoint stage completes, middleware or runner emits a `checkpoint.created` event.
- The workflow pauses before the next managed stage.
- Future-stage tool calls must wait while the current checkpoint is `awaiting_user`.
- Approval wakes the stage gate and allows the next stage.
- Revision keeps the stage active and records the revision attempt.
- Failure during revision latches the stage as failed and wakes waiters with a clear error.

This preserves the existing guarantee: later stages cannot silently advance when the current stage has not been accepted.

## API Design

Add or extend routes:

- `GET /api/runs/{run_id}/checkpoint`
  - Returns the active checkpoint, if any.

- `GET /api/runs/{run_id}/checkpoints`
  - Returns checkpoint and decision history.

- `POST /api/runs/{run_id}/checkpoints/{checkpoint_id}/approve`
  - Records approval and resumes execution.

- `POST /api/runs/{run_id}/checkpoints/{checkpoint_id}/revise`
  - Records revision instruction and resumes the current stage in revision mode.

- `POST /api/runs/{run_id}/checkpoints/{checkpoint_id}/stop`
  - Keeps the run paused and records the user stop decision.

- `POST /api/runs/{run_id}/resume`
  - Continues an existing paused or partial run from its latest resumable state.

All write routes should validate:

- Run ID is safe.
- Checkpoint belongs to the run.
- Checkpoint is still active.
- Decision is legal for the current checkpoint status.
- Payload patch is JSON-compatible and size-bounded.

## WebSocket Events

Add structured events:

- `checkpoint_created`
- `checkpoint_updated`
- `checkpoint_decision`
- `resume_started`
- `resume_completed`
- `resume_failed`

Each event should include:

- `run_id`
- `checkpoint_id`
- `stage`
- `status`
- `summary`
- `actions`
- `artifacts`
- `timestamp`

The UI should be able to reconstruct checkpoint state by replaying `events.jsonl`.

## Editable Stage Payloads

Use small structured payloads for the first implementation:

- Problem understanding:
  - objectives
  - constraints
  - deliverables
  - assumptions

- Data audit:
  - usable_files
  - missing_files
  - data_quality_notes
  - required_user_inputs

- Model plan:
  - candidate_models
  - selected_model
  - assumptions
  - variables
  - evaluation_metrics

- Experiment plan:
  - execution_policy
  - scripts
  - expected_outputs
  - safety_notes

- Draft paper:
  - section_outline
  - missing_sections
  - revision_priorities

- Final package:
  - required_files
  - present_files
  - missing_files
  - packaging_notes

If a payload cannot be parsed safely from agent output, store a plain text summary and allow natural-language revision only.

## Persistence Layout

Under each run directory:

```text
run.json
events.jsonl
checkpoints/
  checkpoint_<stage>_<timestamp>.json
  decisions.jsonl
resume/
  resume_plan_<timestamp>.json
```

Checkpoint files should reference artifacts by relative path. They should not duplicate large paper or data files.

## Error Handling

Expected cases:

- User approves an expired checkpoint: return `409 Conflict`.
- User revises a completed run: return `409 Conflict` unless a new revision run is created.
- Resume target artifacts are missing: mark run `PARTIAL`, emit `resume_failed`, and ask user to restart from an earlier stage.
- Revision exceeds attempt limit: mark checkpoint `awaiting_user` with a clear finding.
- WebSocket disconnects while awaiting user: run remains paused and recoverable from history.

No checkpoint error should leave a run pretending to be completed.

## Security And Safety

- Never allow checkpoint payload patches to include arbitrary filesystem paths outside the run directory or approved asset store.
- Bound checkpoint instruction and patch sizes.
- Require explicit approval before local experiment execution when `require_user_approval_for_execution` is enabled.
- Persist decision history for auditability.
- Treat user edits as input to agents, not as trusted executable content.

## Testing Strategy

Follow TDD for implementation.

Unit tests:

- Checkpoint model serialization round trips.
- Checkpoint service creates, loads, and resolves checkpoints.
- Illegal transitions are rejected.
- Resume plans are built from approval and revision decisions.
- Missing checkpoint files produce clear errors.

Runner tests:

- A key-stage run pauses after problem understanding.
- Approval continues to the next stage.
- Revision re-enters the same stage with user feedback.
- Failed revision does not advance later stages.
- Existing autonomous `run(spec)` remains compatible.

Middleware tests:

- Future-stage tools wait while a checkpoint is awaiting user.
- Approval wakes waiting tools.
- Revision does not unlock future stages prematurely.
- Failure while awaiting or revising wakes waiters with failure.

API tests:

- Active checkpoint endpoint returns current checkpoint.
- Approve, revise, stop, and resume endpoints validate run/checkpoint ownership.
- Duplicate decisions return conflict.
- Event replay reconstructs checkpoint state.

Web tests:

- Starting a run shows checkpoint controls.
- Approve continues progress.
- Revise sends instruction and updates chat.
- Reloading a paused run restores checkpoint state.

Regression:

- Full `agent_app/tests` must pass.
- Existing paper chat stream behavior must still work when checkpoints are disabled.

## Acceptance Criteria

The phase is complete when:

- Users can pause at configured key stages.
- Users can approve or revise from Web.
- Paused runs are visible and recoverable from run history.
- Stage advancement is blocked while a checkpoint awaits a decision.
- Resuming from approval or revision is covered by tests.
- Autonomous mode remains available for smoke and CLI compatibility.
- The final implementation passes the required two reviews:
  - Spec review against this document.
  - Code quality review for naming, boundaries, edge cases, and test coverage.

## Rollout Plan

Implement in four slices:

1. Domain and service layer: checkpoint models, service, serialization, transition tests.
2. Runner and middleware integration: pause, approve, revise, resume, event emission.
3. API and event replay: checkpoint routes and persisted WebSocket events.
4. Web UI: checkpoint card, action buttons, editable payloads, recovery from history.

Each slice must leave the app runnable and should include focused tests before the next slice starts.

## Implementation Decisions

Use these defaults in the implementation plan:

- Revision invokes the responsible stage agent.
- Editable payloads use compact stage-specific form controls when a known schema is available; otherwise the UI shows a read-only summary plus a natural-language instruction box.
- Web defaults to `key_stages`; CLI defaults to autonomous execution.
- Resume starts a new coordinator invocation scoped to the next required stage or current revision stage.

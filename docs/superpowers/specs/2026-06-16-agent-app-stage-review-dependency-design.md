# Agent App Stage Review Dependency Design

Date: 2026-06-16

## Goal

Improve the paper-production product experience so every workflow stage exposes its concrete output for user review before the system advances, while preserving correctness when an earlier stage is revised.

The system must feel like an industrial research workflow, not an autonomous demo that silently races through stages. Users should see what each stage produced, confirm it, revise it through conversation, and understand when downstream work has become stale.

## Product Decision

Use the B+ interaction model:

- Main chat remains the user-facing conversation and progress narrative.
- A dedicated review queue/card area exposes stage outputs in a stable, scannable format.
- Each key stage pauses at a checkpoint until the user approves, requests revision, or stops.
- If a user revises an earlier stage, all downstream dependent stage outputs become stale and cannot remain visually or semantically complete.
- Stale outputs remain available as version history for comparison, but they are not eligible inputs for final packaging.

## Current Baseline

The project already has:

- Web paper chat streaming through `/api/paper/chat/start` and `/ws/paper/{task_id}`.
- Stage, tool, artifact, quality gate, revision, checkpoint, and done events.
- `CheckpointService` with persisted checkpoint records and decisions.
- Web checkpoint controls for approve, revise, and stop.
- Run history and event replay.

Current product gaps:

- Stage outputs are mostly visible as terse tool previews or artifact paths, not as reviewable product deliverables.
- The main chat receives status events, but the user cannot easily inspect each stage's actual reasoning/output contract.
- A stage can look complete even when an upstream stage was revised after it was generated.
- The UI does not clearly distinguish current outputs from stale historical versions.
- Revision semantics need to invalidate downstream stage outputs deterministically.

## UX Requirements

### Main Chat

The chat should show concise process messages:

- Stage started.
- Stage output is ready for review.
- User approved or requested revision.
- Downstream stages were invalidated due to an upstream revision.
- Execution resumed from a checkpoint.

The chat should not be the only place where long stage outputs live. Long outputs such as data audit tables, modeling plans, experiment reports, and paper drafts should be summarized in chat and fully shown in the review card area.

### Review Queue

The review queue should show one card per stage output version. The active card is the current checkpoint.

Each card should include:

- Stage label.
- Version number.
- Status: `running`, `awaiting_user`, `approved`, `revising`, `completed`, `stale`, `blocked`, or `failed`.
- Short summary written for the user, not raw JSON.
- Key structured fields from the stage output.
- Artifact links produced by the stage.
- Quality reports or risks when available.
- Actions for the active checkpoint: approve, request revision, stop.
- A natural-language revision instruction field.

Stale cards should remain visible but clearly marked:

- "已过期，仅供对比"
- The upstream stage and version that invalidated them.
- No approve or continue actions.

### Stage Timeline

The stage timeline should not show stale downstream stages as `completed`.

When an upstream stage is revised:

- The revised stage becomes `revising` or `awaiting_user` depending on execution state.
- Approved downstream stages become `stale`.
- Pending downstream stages become `blocked` until required upstream stages are approved again.
- Final packaging is blocked while any required stage is stale.

## Dependency Invalidation Rules

Each stage output must be treated as a versioned artifact with explicit dependencies.

### Stage Output Metadata

Persist metadata for every reviewable stage output:

- `stage`
- `version`
- `status`
- `run_id`
- `created_at`
- `approved_at`
- `input_fingerprint`
- `depends_on`: list of `{stage, version, output_id}`
- `invalidated_by`: optional `{stage, version, decision_id, reason}`
- `summary`
- `review_payload`
- `artifacts`
- `quality_reports`

The first implementation can store this in JSON files under the run directory. It does not require a database.

### Fingerprints

`input_fingerprint` should be a deterministic hash of the stage's meaningful inputs:

- User question.
- Selected assets and uploaded files.
- Upstream approved stage output ids or versions.
- User checkpoint payload patches and revision instructions.
- Output profile.

The fingerprint is used to decide whether a previously completed stage is still valid.

### Revision Rule

When the user chooses `revise` for stage `S`:

1. Record the checkpoint decision.
2. Mark the current stage output version for `S` as `revising`.
3. Mark every downstream output that directly or indirectly depends on `S` as `stale`.
4. Preserve stale outputs and artifacts for history.
5. Resume execution from `S`.
6. When the revised output for `S` is generated, create a new review version.
7. Downstream stages rerun only after the revised `S` version is approved.

### Payload Patch Rule

If the user approves a checkpoint with edited structured fields, treat it as a content change unless the patch is empty.

- Empty approve: continue to next stage.
- Approve with payload patch: create a new approved version for the current stage and invalidate downstream stages.
- Revise with instruction or payload patch: rerun the current stage and invalidate downstream stages.

### Final Package Rule

`package_submission` can run only when all required upstream stages have current, non-stale approved outputs.

If any required stage is stale, the runner must return a partial state with a clear message instead of generating a final package from mixed versions.

## Event Protocol

Add structured events for reviewable stage outputs:

- `stage_review_created`
- `stage_review_updated`
- `stage_invalidated`
- `stage_review_decision`

Example `stage_review_created` payload:

```json
{
  "type": "stage_review_created",
  "run_id": "run_...",
  "stage": "plan_modeling",
  "stage_label": "规划模型",
  "output_id": "plan_modeling_v2",
  "version": 2,
  "status": "awaiting_user",
  "summary": "已形成三层建模方案，建议先使用整数规划建立基线。",
  "review_payload": {
    "assumptions": ["需求稳定", "运输成本线性"],
    "decision_variables": ["x_ij", "y_j"],
    "objective": "最小化成本并满足服务约束",
    "risks": ["缺少缺失值处理策略"]
  },
  "artifacts": [],
  "quality_reports": []
}
```

Example invalidation event:

```json
{
  "type": "stage_invalidated",
  "run_id": "run_...",
  "stage": "plan_modeling",
  "output_id": "plan_modeling_v1",
  "status": "stale",
  "invalidated_by": {
    "stage": "understand_problem",
    "version": 2,
    "decision_id": "decision_..."
  },
  "reason": "问题理解被用户修改，模型规划依赖旧问题定义。"
}
```

Checkpoint events can remain, but the UI should render review cards from `stage_review_*` events because they are product-oriented and stable for replay.

## Backend Design

Add a focused stage review service:

- `agent_app/services/stage_review_service.py`

Responsibilities:

- Create stage output versions.
- Persist review payloads and summaries.
- Compute input fingerprints.
- Resolve dependency graph for downstream invalidation.
- Mark stale outputs.
- Return current review state for Web replay.
- Validate that final packaging only uses current approved outputs.

The existing `CheckpointService` remains responsible for user checkpoint decisions. The stage review service owns versioning and dependency validity.

## Runner Integration

The runner should create a review output whenever a reviewable stage completes.

For each key stage:

1. Execute stage tool/subagent.
2. Normalize raw output into a review payload.
3. Persist stage review version.
4. Emit `stage_review_created`.
5. Create or update the corresponding checkpoint.
6. Return `RunStatus.PARTIAL` while waiting for user approval.

On resume:

- `approve` continues only if the stage version is current.
- `approve` with payload changes creates an approved patched version and invalidates downstream versions.
- `revise` invalidates downstream versions before rerunning the selected stage.
- Resume never reuses stale downstream outputs as final inputs.

## Frontend Design

Update `agent_app/web/static/app.js` and `style.css` to add:

- `stageReviewRecords` state.
- Render function for stage review cards.
- Handling for `stage_review_created`, `stage_review_updated`, `stage_invalidated`, and `stage_review_decision`.
- Stale visual state in review queue and stage timeline.
- Active checkpoint actions attached to the current review card.
- Chat messages that summarize review readiness and invalidations.

The existing checkpoint panel can be folded into the review card or kept as the action section of the active review card. There should not be two separate places asking for the same decision.

## Tests

Add or update tests for:

- Stage review service creates versioned outputs with fingerprints.
- Revising an upstream stage marks all dependent downstream outputs stale.
- Approving with payload patch invalidates downstream outputs.
- Final packaging fails or returns partial when required outputs are stale.
- Web event handler renders review cards and stale states.
- Run history replay reconstructs review queue state.
- Existing checkpoint approve/revise/stop flows still work.

## Acceptance Criteria

This feature is complete when:

- Starting a paper run pauses at each configured reviewable stage.
- The user can inspect the stage's actual deliverable in a review card.
- The user can approve, revise, or stop from the card.
- Revising an earlier stage visibly invalidates downstream stages.
- Downstream stages rerun from the correct dependency point.
- The UI never shows stale downstream outputs as complete.
- Final submission cannot be generated from stale mixed-version outputs.
- Event replay from run history reconstructs the same review and invalidation state.

## Non-Goals

- No collaborative editing.
- No database migration.
- No token-level interruption of an in-flight model call.
- No arbitrary graph editor for stage dependencies.
- No deletion of old stale artifacts; keep them for audit and comparison.

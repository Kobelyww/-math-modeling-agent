# Agent App Full Feature Expansion Design

Date: 2026-06-12

## Goal

Expand the DeepAgent math modeling paper system from a working paper-generation workflow into an industrial competition research workspace. The system should let a user upload and manage inputs, run and resume paper tasks, execute experiments, revise papers through quality gates, choose output profiles, and eventually delegate each major capability to specialized DeepAgent subagents.

This design builds on the existing `competition_paper` runner and WebSocket paper chat. It avoids a single large rewrite by delivering six independently testable capability slices.

## Confirmed Scope

The expansion includes all six capability areas:

1. File upload and input asset management.
2. Run history, recovery, and downloadable submissions.
3. Real experiment execution and figure/table capture.
4. Paper quality feedback and revision loops.
5. Output profiles for MCM/ICM, China Undergraduate Mathematical Contest in Modeling, and research-paper style output.
6. Specialized DeepAgent subagents for data, modeling, experiment, writing, review, and packaging.

## Current Baseline

The current system already has:

- `CompetitionPaperRunner` as the primary run API.
- `RunSpec`, `RunState`, `ArtifactRef`, `QualityReport`, and related domain models.
- DeepAgent coordinator and stage middleware.
- Web paper chat using `POST /api/paper/chat/start` and `WS /ws/paper/{task_id}`.
- Stage/tool/artifact WebSocket events from real DeepAgent tool calls.
- Services for ingestion, data analysis, code execution, LaTeX, RAG, literature, and artifacts.
- Tests covering runner behavior, middleware, tools, quality gates, Web stream behavior, and services.

Known gaps this expansion addresses:

- Users still type file paths instead of managing files in Web.
- Run history exists on disk but is not a first-class UI/API feature.
- Experiment scripts are generated but not yet an industrial execution pipeline with result ingestion.
- Paper quality gates can report problems but do not yet drive controlled revision loops.
- Output style is mostly one competition-paper profile.
- DeepAgent orchestration uses tools, but subagent responsibilities are not yet formalized.

## Delivery Strategy

The work should be implemented in six phases. Each phase must leave the app runnable, keep existing paper runs compatible, and add tests around its public contracts before expanding the next phase.

### Phase 1: File Upload And Input Asset Management

Purpose: remove the path-typing bottleneck and make all user inputs traceable.

New concepts:

- `InputAsset`: immutable uploaded file record.
- `AssetKind`: `question`, `data`, `reference`, `image`, `other`.
- `AssetStatus`: `uploaded`, `validated`, `rejected`.
- `AssetManifest`: selected assets attached to a run.

Storage:

- Uploaded files live under `agent_app/data/paper_inputs/assets/<asset_id>/`.
- Original filenames are preserved in metadata, but filesystem paths use safe generated IDs.
- Metadata is stored as JSON in `asset.json` for each asset. A later database-backed implementation can reuse the same schema.

API:

- `POST /api/assets/upload`: upload one file, infer kind, validate size/type, and return metadata.
- `GET /api/assets`: list uploaded assets.
- `GET /api/assets/{asset_id}`: return metadata.
- `DELETE /api/assets/{asset_id}`: soft-delete or mark unavailable, not hard-delete by default.

Web UI:

- Add an input asset panel with drag/drop upload.
- Show uploaded files as selectable rows with kind, size, validation status, and preview when possible.
- Starting a paper run sends selected `asset_ids`; the backend resolves them to safe paths.

Validation:

- Accept CSV, XLSX, JSON, TXT, MD, PDF, PNG, JPG, JPEG.
- Reject path traversal, unknown binary formats, empty files, and oversized files.
- Keep the current path-based input for CLI compatibility, but Web should prefer `asset_ids`.

### Phase 2: Run History, Recovery, And Submission Downloads

Purpose: make every paper task visible, resumable, and exportable.

New concepts:

- `RunSummary`: compact list item for Web.
- `RunEvent`: persisted stage/tool/message/artifact event.
- `SubmissionBundle`: downloadable archive metadata.

Storage:

- Continue using `agent_app/output/runs/<run_id>/`.
- Add `events.jsonl` per run. WebSocket events are appended as they are emitted.
- Add `submission.zip` generation only when requested or when package stage completes.

API:

- `GET /api/runs`: list recent runs with status, created time, profile, question preview, artifact count.
- `GET /api/runs/{run_id}`: load full `RunState`, artifacts, and quality reports.
- `GET /api/runs/{run_id}/events`: replay persisted events for UI recovery.
- `POST /api/runs/{run_id}/continue`: continue a run with a follow-up instruction.
- `GET /api/runs/{run_id}/download`: return a zip submission bundle.

Web UI:

- Add a run history sidebar or tab.
- Selecting a run loads prior chat, events, stages, artifacts, and quality reports.
- If a run is `partial` or `failed`, the follow-up box remains available.
- Completed runs show a download action.

Recovery behavior:

- If WebSocket disconnects, the server continues the run unless explicitly cancelled.
- Reopening the run replays `events.jsonl` and resumes display from persisted state.

### Phase 3: Real Experiment Execution And Result Capture

Purpose: turn `solve.py` into a reproducible experiment, not only a generated artifact.

New concepts:

- `ExecutionPolicy`: local subprocess, docker sandbox, or disabled.
- `ExecutionAttempt`: command, exit code, stdout, stderr, duration, produced files.
- `ExperimentManifest`: metrics, tables, figures, and raw output files.

Services:

- Extend `CodeExecutionService` to run `solve.py` with a bounded timeout, working directory, and allowed environment.
- Add output scanning for `results/`, `figures/`, and supported table formats.
- Add a result normalizer that stores discovered tables, metrics, and figure paths in `ExperimentResult`.

Workflow changes:

- `run_experiment` must generate code and execute it.
- If execution fails, `repair_code` may be called up to `RunOptions.max_repair_attempts`.
- Experiment stage completes only when there is either a successful execution or an explicit failure report with diagnostics.

Security:

- Default local execution timeout is bounded.
- Network access is disabled for experiment code unless explicitly configured.
- Docker sandbox is preferred when available; subprocess fallback must be clearly marked.

Web UI:

- Show execution attempts under the experiment stage.
- Display stdout/stderr previews and generated figures/tables.
- Surface repair attempts as events.

### Phase 4: Paper Quality Revision Loop

Purpose: produce stronger papers through controlled review and revision, not one-pass drafting.

New concepts:

- `RevisionPlan`: structured fixes derived from quality reports.
- `RevisionAttempt`: before/after artifact references, applied fixes, remaining issues.
- `QualityThresholds`: minimum scores per gate and overall.

Workflow changes:

- `review_submission` produces structured findings.
- If required fixes exist, `revise_paper` updates `paper.md`, `paper.tex`, and related artifacts.
- The loop runs until all required gates pass, max attempts are reached, or user input is required.

Quality gates:

- Input completeness.
- Modeling validity.
- Experiment reproducibility.
- Paper structure and citation adequacy.
- Submission completeness.

Rules:

- The loop may not fabricate missing experiment results.
- If a fix requires missing data or user judgment, the run becomes `partial` with a clear follow-up question.
- Each revision attempt must be preserved as a versioned artifact or diff summary.

Web UI:

- Show quality gate cards with score, pass/fail, required fixes, and revision attempts.
- The chat should explain when it needs user input instead of silently failing.

### Phase 5: Output Profiles

Purpose: support different submission styles without forking the workflow.

Profiles:

- `mcm_icm`: MCM/ICM-style English paper package.
- `cumcm`: China Undergraduate Mathematical Contest in Modeling style Chinese paper package.
- `research_paper`: research article style with stronger literature, method, experiment, and discussion sections.

New concepts:

- `OutputProfile`: template, language, required sections, citation style, quality thresholds, packaging rules.
- `ProfileRegistry`: maps profile IDs to configuration.

Workflow changes:

- `RunSpec.output_profile` selects the profile.
- Paper drafting, review, and packaging tools receive profile configuration.
- The default remains `competition_paper` or aliases to `mcm_icm` until the UI exposes selection.

Web UI:

- Add profile selector near the start button.
- Profile selection changes placeholder text, expected deliverables, and quality gate labels.

Compatibility:

- Existing runs without explicit profile load as `competition_paper`.
- CLI `/paper` may accept optional `--profile`.

### Phase 6: Specialized DeepAgent Subagents

Purpose: turn the workflow into an explicit expert team while keeping the main coordinator accountable.

Subagents:

- Data subagent: input ingestion, schema inference, data audit.
- Modeling subagent: problem decomposition, assumptions, model plan.
- Experiment subagent: code generation, execution, repair, result interpretation.
- Writing subagent: paper drafting, LaTeX, figures/tables integration.
- Review subagent: quality gates, revision plan, risk detection.
- Packaging subagent: final manifest, zip, submission checks.

Coordinator responsibilities:

- Own run state and stage transitions.
- Delegate stage-specific work to subagents.
- Enforce tool and quality gate constraints.
- Decide when to continue, revise, ask the user, or stop.

Implementation rule:

- Subagents must not directly mutate run state except through approved tools/services.
- Every subagent output must be converted into structured artifacts or quality reports.
- The Web event stream remains driven by stage/tool events, so UI behavior does not depend on whether a tool was called by the main coordinator or a subagent.

## API And UI Shape

### Web API Additions

```text
POST   /api/assets/upload
GET    /api/assets
GET    /api/assets/{asset_id}
DELETE /api/assets/{asset_id}

GET    /api/runs
GET    /api/runs/{run_id}
GET    /api/runs/{run_id}/events
POST   /api/runs/{run_id}/continue
GET    /api/runs/{run_id}/download

GET    /api/profiles
```

Existing endpoints remain:

```text
POST /api/paper/chat/start
WS   /ws/paper/{task_id}
GET  /api/health
```

### Web UI Layout

The first screen remains the actual paper workspace, not a landing page.

Recommended layout:

- Left rail: asset upload/selection, profile selector, run controls.
- Center: chat and event stream.
- Right rail: stages, quality gates, artifacts, run history.

For compact screens:

- Use tabs for Assets, Chat, Stages, Artifacts, History.
- Keep the primary chat and start action visible without scrolling through marketing content.

## Data Flow

1. User uploads assets.
2. User selects assets and output profile.
3. Web calls paper chat start with question, asset IDs, profile, and conversation context.
4. Backend resolves assets into `RunSpec`.
5. Runner creates a run and appends events to `events.jsonl`.
6. DeepAgent coordinator runs stages and subagents.
7. Tools call services and write artifacts.
8. Middleware streams stage/tool/artifact events to WebSocket.
9. Quality gates may trigger revision loops.
10. Packaging creates final manifest and downloadable bundle.
11. Run history can replay the event stream and continue a partial run.

## Error Handling

- Invalid uploads return a clear validation error and do not create assets.
- Missing selected assets fail before run creation.
- Tool failures emit `tool failed` and stage failure events.
- Experiment failures are recorded as `ExecutionAttempt`, not hidden in text.
- If required user information is missing, the run status becomes `partial`.
- If infrastructure fails unexpectedly, the run status becomes `failed` and preserves all artifacts created so far.
- WebSocket disconnect does not automatically cancel the run.

## Testing Strategy

Each phase needs focused tests:

- Asset service tests: upload validation, metadata persistence, safe paths, kind inference.
- Route tests: asset APIs, run history APIs, download endpoint.
- Runner tests: asset ID resolution, profile propagation, event persistence.
- Experiment tests: success, timeout, failure, repair attempts, output scanning.
- Quality loop tests: pass first time, revise then pass, max attempts, user-input partial.
- Profile tests: required sections, template selection, compatibility defaults.
- Subagent tests: registry construction, coordinator delegation, tool constraints.
- Web stream tests: event replay, partial handling, no false completion.

Full regression remains:

```bash
pytest agent_app/tests -q
```

## Migration Plan

Implement in this order:

1. Asset model/service/API and Web selection.
2. Run event persistence and history/replay.
3. Experiment execution pipeline.
4. Revision loop and quality UI.
5. Profile registry and selector.
6. DeepAgent subagent decomposition.

The order is intentional: later phases depend on inputs, persisted events, and robust run recovery.

## Acceptance Criteria

The expansion is complete when:

- A user can upload files in Web, select them, and start a paper run without typing server paths.
- A disconnected browser can reopen a run and see prior events/artifacts.
- A completed run has `modeling_report.md`, `solve.py`, `paper.tex`, `final_synthesis.md`, `run.json`, and a downloadable package.
- Experiment execution produces either successful result artifacts or explicit diagnostics.
- Quality gates can trigger at least one automatic paper revision.
- MCM/ICM, CUMCM, and research-paper profiles produce visibly different paper structures.
- DeepAgent subagents are registered and used for their dedicated stage responsibilities.
- The full test suite passes.

## Non-Goals

- Multi-user collaboration.
- Cloud deployment, authentication, or billing.
- Real-time collaborative editing of LaTeX.
- Guaranteed competition-winning mathematical originality.
- Unrestricted code execution.

## Open Implementation Notes

- File storage should start as JSON-on-disk to match the current run store style. A database can be introduced later if needed.
- Existing path-based APIs remain for CLI and tests, but Web should transition to asset IDs.
- The current Web UI can be incrementally evolved; a full visual redesign is not required for the first phase.
- Subagents should come after the workflow has enough persisted state and quality contracts to make delegation observable.

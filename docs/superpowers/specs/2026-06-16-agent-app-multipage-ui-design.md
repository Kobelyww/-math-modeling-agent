# Agent App Multipage UI Design

Date: 2026-06-16

## Goal

Refactor the current one-page paper chat console into a multipage research workflow UI. The product should feel like an industrial math-modeling paper production workspace, not a dense demo dashboard.

The UI must separate major user jobs:

- Start and drive a paper workflow.
- Review and approve stage outputs.
- Inspect generated artifacts.
- Use RAG and Nature Skills resources.
- Recover the current run after page refresh or navigation.

## Current Baseline

The current Web UI has one template:

- `agent_app/web/templates/index.html`

The single page currently contains:

- Paper task input.
- PDF upload.
- RAG search and rebuild.
- Nature Skills list.
- Chat/event stream.
- Stage timeline.
- Stage Review Queue.
- Artifact list.

The backend currently exposes one page route:

- `GET /`

The existing workflow APIs and WebSocket should remain compatible:

- `POST /api/paper/chat/start`
- `WS /ws/paper/{task_id}`
- `POST /api/runs/{run_id}/stage-reviews/{output_id}/approve`
- `POST /api/runs/{run_id}/stage-reviews/{output_id}/revise`
- `POST /api/runs/{run_id}/stage-reviews/{output_id}/stop`
- `GET /api/rag/query`
- `POST /api/rag/rebuild`
- `GET /api/skills`

## Product Decision

Use a server-rendered multipage application with shared CSS and lightweight page-specific JavaScript.

Do not introduce a frontend framework in this phase. The current FastAPI + Jinja + vanilla JavaScript stack is sufficient and keeps the refactor low-risk.

## Page Information Architecture

### Dashboard: `/`

Purpose: show the user where they are in the system.

Content:

- Product title and concise system status.
- Current or most recent run summary.
- Quick links to Paper Workflow, Review Center, Artifacts, and Knowledge.
- Counts for pending reviews, stale reviews, and generated artifacts when a run is selected.
- Primary action: start a new paper workflow at `/paper`.

The dashboard must not contain the full paper chat console.

### Paper Workflow: `/paper`

Purpose: start and drive the paper production workflow.

Content:

- Problem statement input.
- Data file paths.
- Reference file paths.
- PDF upload and extraction status.
- Start button.
- Chat/event stream.
- Compact stage timeline.
- Current active review summary.
- Current artifact summary.

Behavior:

- Start paper workflow through existing `POST /api/paper/chat/start`.
- Stream events through existing `WS /ws/paper/{task_id}`.
- Store `currentRunId` in `localStorage` when events include `run_id`.
- Keep review actions available only for the current `awaiting_user` review card.

The page should not show every historical review version by default. Full review history belongs in `/reviews`.

### Review Center: `/reviews`

Purpose: make stage output review a first-class workflow.

Content:

- Review list grouped by status: `awaiting_user`, `approved`, `revising`, `stale`, `replaced`, `failed`.
- Detail panel for the selected review.
- Structured review payload preview.
- Artifact links attached to the selected stage output.
- Approve, revise, and stop controls only for `awaiting_user` reviews.
- Stale and replaced outputs shown as read-only history.

Behavior:

- Load reviews for the selected run through a new read API.
- Apply approve/revise/stop decisions through existing decision APIs.
- Feed returned `stage_review_decision`, `stage_review_updated`, `stage_invalidated`, and `resume_events` into shared event state.
- Never render action buttons for stale or replaced outputs.

### Artifacts: `/artifacts`

Purpose: manage generated deliverables and final package readiness.

Content:

- Artifact list for the selected run.
- Artifact kind, path, source stage when known, and status.
- Core submission readiness summary: paper, code, modeling report, final synthesis.
- Export current chat transcript action.

Behavior:

- Load run artifacts through a new read API.
- Show clear empty and partial states.
- Do not claim final package readiness if required stage reviews are missing or stale.

### Knowledge: `/knowledge`

Purpose: isolate supporting research tools from the paper workflow.

Content:

- RAG index readiness.
- RAG query input and results.
- Rebuild index action.
- Nature Skills rules, visualization templates, and tools.

Behavior:

- Use existing `GET /api/rag/query`.
- Use existing `POST /api/rag/rebuild`.
- Use existing `GET /api/skills`.

## Navigation and Layout

Add a shared layout template:

- `agent_app/web/templates/base.html`

Shared layout requirements:

- Persistent product header.
- Left navigation or top navigation with links:
  - Dashboard
  - Paper
  - Reviews
  - Artifacts
  - Knowledge
- Active navigation state.
- Shared status area for selected run when available.
- Main content slot.

Template files:

- `dashboard.html`
- `paper.html`
- `reviews.html`
- `artifacts.html`
- `knowledge.html`

The previous `index.html` can either become `dashboard.html` content or remain as a compatibility wrapper that extends the new base layout.

## API Additions

Add read-only APIs required for multipage state recovery:

### `GET /api/runs`

Return recent runs from the run output directory.

Response fields:

- `run_id`
- `status`
- `stage`
- `summary`
- `created_at`
- `updated_at`
- `artifact_count`
- `pending_review_count`
- `stale_review_count`

### `GET /api/runs/{run_id}`

Return serialized run state plus summary counts.

### `GET /api/runs/{run_id}/stage-reviews`

Return all stage review records for a run, sorted by stage order and version.

### `GET /api/runs/{run_id}/artifacts`

Return serialized artifact records for a run.

Security and correctness:

- Validate `run_id` using existing run id validation through `RunStore.run_dir`.
- Return `404` for missing runs.
- Do not expose `.env` or hidden files.

## Frontend JavaScript Structure

Split page code by responsibility:

- `app.js`: shared utilities, run selection, navigation helpers, event reducers.
- `paper.js`: paper workflow start, WebSocket, chat stream, PDF upload.
- `reviews.js`: review list, detail rendering, review decisions.
- `artifacts.js`: artifact list and readiness display.
- `knowledge.js`: RAG and skills interactions.

Shared state:

- `currentRunId` stored in `localStorage`.
- URL query parameter `run_id` overrides `localStorage`.
- Pages that need a run load it in this order:
  1. `?run_id=...`
  2. `localStorage.currentRunId`
  3. most recent run from `GET /api/runs`

Shared event handling:

- `stage_review_created`
- `stage_review_updated`
- `stage_review_decision`
- `stage_invalidated`
- `artifact`
- `stage`
- `done`
- `error`

The event reducer should be resilient when a page does not contain every DOM node. Missing elements must be ignored, not treated as errors.

## Visual Design Direction

The interface should feel like a professional research operations tool:

- Dense but organized.
- Clear navigation.
- Compact headings.
- Stable tables/lists for repeated records.
- No marketing hero sections.
- No decorative gradient/orb background.
- No nested cards.
- No large text blocks that describe how to use the system inside the app.

Recommended layout:

- Dashboard: summary grid plus recent run list.
- Paper: two-column layout on desktop, single column on mobile.
- Reviews: list/detail split view.
- Artifacts: table/list view.
- Knowledge: search panel plus resource sections.

Cards are acceptable for repeated run/review/artifact records, with border radius at 8px or less.

## State and Recovery Behavior

After a paper workflow starts:

- The first event containing `run_id` updates `currentRunId`.
- The UI stores the run id in localStorage.
- Navigation links should preserve the selected run by appending `?run_id=<id>` where useful.

After refresh:

- Paper page can restore selected run metadata, but cannot replay a closed WebSocket unless run history replay is implemented.
- Reviews and Artifacts pages must restore persisted state through REST APIs.

This phase does not require full WebSocket event replay. It requires persisted run, review, and artifact state to be readable from multipage views.

## Error Handling

All pages must show clear empty/error states:

- No run selected.
- Run not found.
- No reviews yet.
- No artifacts yet.
- RAG unavailable.
- PDF extraction failure.
- Stage decision conflict.

API errors should be rendered in page status areas, not only in the browser console.

## Tests

Add or update tests for:

- Page routes render successfully:
  - `/`
  - `/paper`
  - `/reviews`
  - `/artifacts`
  - `/knowledge`
- New run read APIs return expected run summaries.
- Review read API returns persisted stage reviews.
- Artifact read API returns run artifacts.
- Stage review decision APIs still work after page split.
- Existing paper chat stream tests remain green.

Frontend verification:

- `node --check` for all JavaScript files.
- Manual or browser verification that each page renders without obvious overlap at desktop and mobile widths.

## Non-Goals

This phase does not include:

- Adding a frontend framework.
- User authentication.
- Multi-user run ownership.
- Full WebSocket replay after refresh.
- Artifact file download endpoint beyond existing paths and transcript export.
- A new database.

## Rollout Plan

1. Add multipage templates and navigation.
2. Add read-only run/review/artifact APIs.
3. Split JavaScript by page.
4. Move current single-page workflow into `/paper`.
5. Build `/reviews`, `/artifacts`, and `/knowledge`.
6. Update tests.
7. Run service and visually inspect all pages.

## Acceptance Criteria

- `/` is a dashboard, not the old dense console.
- `/paper` can start a paper workflow and display streaming events.
- `/reviews` can display persisted stage review records and submit decisions for `awaiting_user` records.
- `/artifacts` can display persisted artifacts for a selected run.
- `/knowledge` can query RAG and list Nature Skills.
- Navigation between pages preserves the selected run when possible.
- Refreshing `/reviews` or `/artifacts` can recover persisted run state.
- Stale and replaced reviews are read-only.
- JavaScript syntax checks pass.
- Relevant backend tests pass.
- The layout is usable on desktop and mobile without overlapping text or controls.

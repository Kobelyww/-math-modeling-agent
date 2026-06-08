# Zhihu Fiction Workspace Business Modules Design

Date: 2026-06-08

## Goal

Extend `zhihu_fiction` from a one-run fiction generator into a business-complete local content production workspace.

The first version should connect three business modules into one usable loop:

```text
material library
-> topic card
-> queued story task
-> pipeline generation
-> review draft
-> lightweight editing
-> publish package
```

The design keeps the current file-based architecture, adds repository and service boundaries, and reserves a later SQLite implementation without requiring a database migration now.

## Confirmed Decisions

- Scope: business-complete version of material, task, review, and publish-package modules.
- Storage: file system first, accessed through repository interfaces so SQLite can replace it later.
- Queue: single active task, with pending tasks queued.
- Review and editing: lightweight Web editing for title, synopsis, tags, and body.
- Material-to-task flow: materials become topic cards first; approved topic cards create story tasks.
- Architecture approach: domain modules under `zhihu_fiction/workspace/`, not direct feature growth inside `server.py` and `pipeline.py`.

## Existing Context

Current `zhihu_fiction` already has these capabilities:

- `scraper.py`: Zhihu hot-list, search, and manual material entry.
- `distiller.py` and `skills_store.py`: writing skill distillation and skill-card storage.
- `agents.py` and `orchestrator.py`: DeepAgent creation workflow and reviewer.
- `pipeline.py`: scrape, select, create, review, rewrite, publish, checkpoints, scheduling, and run records.
- `exporter.py` and `publishers/`: multi-platform publishing package generation.
- `server.py`: FastAPI app with run, stream, history, story, skill, and scheduler APIs.
- `static/index.html`: current Alpine/Tailwind Web workspace.

The new modules should reuse these capabilities instead of replacing them.

## Product Scope

### In Scope

1. Material library for imported scraped files, manual entries, and selected source records.
2. Topic cards as the structured bridge from materials to story tasks.
3. Single-worker task queue with queued, running, failed, canceled, and review-ready states.
4. Review drafts that preserve generated output and store user edits separately.
5. Publish packages generated from edited review drafts.
6. FastAPI workspace endpoints for all new business objects.
7. Web workspace pages for materials, topic cards, tasks, review drafts, and publish packages.
8. Focused tests for models, repositories, services, queue behavior, and APIs.

### Out of Scope

- Multi-user accounts or permissions.
- Cloud database or SaaS deployment.
- Multi-task LLM concurrency.
- Full rich-text editor, version diff, or chapter-level editing.
- Automatic publishing without explicit user action.
- Xiaohongshu, WeChat, short-drama, or other new platform implementations.
- Analytics dashboard; it remains a later module.

## Architecture

Add a new package:

```text
zhihu_fiction/workspace/
├── __init__.py
├── models.py
├── repositories.py
├── services.py
├── queue.py
└── schemas.py
```

Responsibilities:

- `models.py`: dataclasses or Pydantic-compatible domain objects.
- `repositories.py`: file-backed repository interfaces and implementations.
- `services.py`: business operations such as material import, topic-card approval, task creation, draft editing, and package generation.
- `queue.py`: single active worker, queued task lifecycle, retry, cancel, and startup repair.
- `schemas.py`: FastAPI request and response models.

Server integration:

- Prefer adding `zhihu_fiction/workspace_routes.py` and mounting the router from `server.py`.
- Keep existing `/api/run`, `/api/stream/{run_id}`, `/api/runs`, `/api/stories`, `/api/skills`, and scheduler routes compatible.
- Reuse `Pipeline.run()` for actual story generation; queue code should coordinate when it is called, not duplicate pipeline logic.

Existing module boundaries:

- `scraper.py` collects raw material only.
- `pipeline.py` executes one story run only.
- `exporter.py` generates platform packages only.
- `workspace/services.py` orchestrates the business flow across these modules.

## Storage Layout

Use file-backed storage under:

```text
zhihu_fiction/data/workspace/
├── materials.jsonl
├── topic_cards.jsonl
├── tasks.jsonl
├── drafts/
│   └── <task_id>.json
├── reviews/
│   └── <task_id>.json
└── publish_packages/
    └── <package_id>/
```

Rules:

- JSONL files store append/update business records.
- Large body text can live in per-object JSON or Markdown files under `drafts/` and `publish_packages/`.
- Repositories own file paths and serialization details.
- Services should not open workspace files directly.
- Repository method names should make a later SQLite implementation straightforward, for example `list_tasks()`, `get_task(id)`, `save_task(task)`, and `update_task_status(id, status)`.

## Domain Objects

### Material

Fields:

- `id`
- `source`
- `title`
- `excerpt`
- `content`
- `url`
- `hot_score`
- `tags`
- `captured_at`
- `status`: `inbox | selected | archived`

Purpose:

Represents raw upstream content from Zhihu hot list, Zhihu search, manual entry, or imported scraped files.

### TopicCard

Fields:

- `id`
- `title`
- `source_material_ids`
- `genre`
- `platform`
- `hook`
- `angle`
- `risk_notes`
- `target_reader`
- `created_at`
- `status`: `draft | approved | archived`

Purpose:

Transforms one or more materials into a reusable creation brief. A topic card can also be created manually with no source materials.

### StoryTask

Fields:

- `id`
- `topic_card_id`
- `topic`
- `genre`
- `platform`
- `chapters`
- `mode`
- `priority`
- `created_at`
- `started_at`
- `finished_at`
- `status`: `queued | running | needs_review | approved | failed | canceled`
- `error`
- `failed_stage`
- `retry_count`
- `run_id`

Purpose:

Tracks a production job from queue entry through pipeline execution and review readiness.

### ReviewDraft

Fields:

- `id`
- `task_id`
- `story_path`
- `original_body`
- `title`
- `synopsis`
- `tags`
- `body`
- `review_result`
- `editor_notes`
- `updated_at`
- `status`: `needs_edit | ready_for_package | rejected`

Purpose:

Stores the human-editable version of generated content. The generated original is preserved; publish packages are generated from the edited draft only.

### PublishPackage

Fields:

- `id`
- `task_id`
- `platform`
- `title`
- `synopsis`
- `tags`
- `content_path`
- `metadata_path`
- `package_dir`
- `created_at`
- `status`: `generated | confirmed | exported`

Purpose:

Represents a platform-ready delivery artifact. Assisted publishing must only be available from a confirmed package and must require an explicit user action.

## State Flow

Main flow:

```text
import or create Material
-> create TopicCard
-> approve TopicCard
-> create StoryTask
-> queue worker runs Pipeline
-> task becomes needs_review
-> create ReviewDraft
-> user edits ReviewDraft
-> mark draft ready_for_package
-> generate PublishPackage
-> confirm/export PublishPackage
```

Task transitions:

```text
queued -> running -> needs_review -> approved
queued -> running -> failed -> queued
queued -> canceled
running -> failed
needs_review -> approved
needs_review -> canceled
```

`StoryTask.status=approved` means the generated task has passed the human review step. It is set when the user marks the associated `ReviewDraft` as `ready_for_package`. Package confirmation/export is tracked separately by `PublishPackage.status`.

Draft transitions:

```text
needs_edit -> ready_for_package
needs_edit -> rejected
ready_for_package -> needs_edit
```

Package transitions:

```text
generated -> confirmed -> exported
generated -> exported
```

## Queue Design

First version uses one active worker.

Behavior:

- Only one task can be `running` at a time.
- New tasks enter `queued`.
- Worker chooses the oldest queued task, with optional priority sorting.
- Failed queued tasks can be retried by setting status back to `queued`.
- Queued tasks can be canceled.
- Running task cancel can be recorded as requested, but first version does not need to interrupt an active LLM call.
- On server startup, any stale `running` task should become `failed` with a startup-repair error message.

Integration:

- Queue worker calls existing `Pipeline.run(topic=..., genre=..., chapters=...)`.
- On success, it stores generated story metadata and creates a `ReviewDraft`.
- On failure, it records `error`, `failed_stage`, and `finished_at`.
- SSE progress can be exposed through `GET /api/workspace/tasks/{id}/events`.

## API Design

Add workspace routes:

```text
GET  /api/workspace/materials
POST /api/workspace/materials/import-scraped
POST /api/workspace/materials/manual
PATCH /api/workspace/materials/{id}

GET  /api/workspace/topic-cards
POST /api/workspace/topic-cards
PATCH /api/workspace/topic-cards/{id}
POST /api/workspace/topic-cards/{id}/approve
POST /api/workspace/topic-cards/{id}/create-task

GET  /api/workspace/tasks
POST /api/workspace/tasks/{id}/retry
POST /api/workspace/tasks/{id}/cancel
GET  /api/workspace/tasks/{id}/events

GET   /api/workspace/drafts
GET   /api/workspace/drafts/{task_id}
PATCH /api/workspace/drafts/{task_id}
POST  /api/workspace/drafts/{task_id}/ready

GET  /api/workspace/packages
POST /api/workspace/packages/generate
POST /api/workspace/packages/{id}/confirm
GET  /api/workspace/packages/{id}/files
```

API rules:

- Invalid state transitions return `409`.
- Missing objects return `404`.
- Validation errors return `422`.
- File import should return both imported count and failed items.
- Package generation should be idempotent enough to regenerate a package from the latest draft.

## Web Workspace

Extend the current Alpine/Tailwind Web interface with five business areas.

### Materials

- Material list with source, status, score, tags, and captured time.
- Filters for source, genre/tag, status, and search text.
- Manual material entry.
- Import from existing scraped files.
- Select one or more materials to create a topic card.

### Topic Cards

- Card list grouped by status.
- Editor for title, hook, angle, genre, platform, risk notes, and target reader.
- Approve topic card.
- Create story task from approved topic card.

### Tasks

- Queue list grouped by `queued`, `running`, `needs_review`, and `failed`.
- Current task progress and SSE log.
- Retry failed task.
- Cancel queued task.
- Link `needs_review` task to its review draft.

### Review

- Draft list.
- Editing panel for title, synopsis, tags, and body.
- Display review result, score, issues, and editor notes.
- Save draft edits.
- Mark draft ready for package.

### Publish Packages

- Package list by task and platform.
- Preview generated title, synopsis, tags, content path, and metadata path.
- Regenerate package from the latest draft.
- Confirm/export package.
- Reserve manual assisted-publishing entry for confirmed packages.

Frontend implementation:

- Keep Alpine + Tailwind for the first version.
- Existing `static/index.html` can be extended initially.
- If the file grows too large, move JavaScript to `static/app.js` and styles to `static/style.css`.
- Avoid a frontend framework migration in this slice.

## Error Handling

- Material import failure: record failed file/item and reason; continue importing valid records.
- Topic card with no source material: allow it, with `source_material_ids=[]`.
- Task execution failure: store `error`, `failed_stage`, `retry_count`, and update task to `failed`.
- Service restart while a task is running: mark stale `running` task as `failed` during startup repair.
- Draft save failure: do not overwrite the previous draft; return a clear error.
- Publish metadata failure: use title, genre, body preview, and empty tags as fallback metadata.
- Assisted publishing failure: does not mutate package files or task state.

## Testing

Add focused tests:

```text
zhihu_fiction/tests/test_workspace_models.py
zhihu_fiction/tests/test_workspace_repositories.py
zhihu_fiction/tests/test_workspace_services.py
zhihu_fiction/tests/test_workspace_queue.py
zhihu_fiction/tests/test_workspace_api.py
```

Coverage:

- Object serialization and valid status values.
- JSONL append, list, update, and corrupted-line behavior.
- Material import to topic card.
- Topic card to story task.
- Completed task to review draft.
- Edited draft to publish package.
- Single-worker queue behavior.
- Failed task retry.
- Queued task cancellation.
- Invalid transition `409` responses.
- Key happy-path API flow with fake pipeline/exporter components.

Existing test command remains:

```bash
pytest zhihu_fiction/tests
```

## Implementation Order

1. Add workspace domain models and repository implementations.
2. Add workspace services for materials, topic cards, tasks, drafts, and packages.
3. Add queue worker that reuses `Pipeline.run()`.
4. Add workspace FastAPI router and mount it from `server.py`.
5. Extend Web workspace pages.
6. Add tests for models, repositories, services, queue, and APIs.
7. Update `zhihu_fiction/README.md` with the new workspace flow.
8. Run `pytest zhihu_fiction/tests`.

## Acceptance Criteria

1. User can import or manually create materials.
2. User can create a topic card from selected materials.
3. User can approve a topic card and create a queued story task.
4. Queue runs only one task at a time.
5. Failed task can be retried.
6. Queued task can be canceled.
7. Completed task creates a review draft.
8. User can edit title, synopsis, tags, and body in a review draft.
9. Edited draft can generate a publish package.
10. Publish package can be confirmed/exported.
11. Existing CLI and old run APIs continue to work.
12. Core `zhihu_fiction/tests` pass.

## Future Extensions

- SQLite repository implementation.
- Multi-task concurrency with configurable worker count.
- Rich editing with chapter-level diffs and revision history.
- Analytics dashboard for score, retry, topic, and package performance.
- New platform modules for Xiaohongshu, WeChat, short drama, and web-novel openings.
- Team collaboration and user permissions if the project becomes SaaS-facing.

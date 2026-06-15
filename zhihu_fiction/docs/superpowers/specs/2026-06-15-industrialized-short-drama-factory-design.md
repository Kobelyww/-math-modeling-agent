# zhihu_fiction Industrialized Short Drama Factory Design

Date: 2026-06-15
Status: Approved design draft
Product mode: Local single-machine small-team production system

## 1. Product Positioning

`zhihu_fiction` should become a local, single-machine short drama content factory for small teams. The first production-grade product should serve 2-10 people who need to turn existing novels or IP drafts into short drama planning packages and video generation tasks.

The product is not a SaaS platform in V1, and it should not remain a demo. It must support repeatable production: queueing, review, confirmation, cost control, recovery, asset management, and clear delivery packages.

### Primary V1 Workflow

```text
Novel/IP import
-> LoopAgent short drama adaptation
-> staged human confirmation
-> consistency profile and reference assets
-> storyboard
-> video cost confirmation
-> video task submission
-> polling, retry, and asset ingestion
-> release package
```

### Priority Order

1. Production reliability: tasks must not be lost; failures must be readable; recovery and retry must work; costs must be controlled.
2. Consistency: character, world, visual style, plot logic, storyboard, reference assets, and video prompts must remain traceable and coherent.
3. Web user experience: the workspace must make process state, confirmation points, generation progress, costs, and errors understandable without reading terminal output.
4. Content quality: drama rhythm, hooks, reversals, emotional beats, and reusable prompts should improve continuously after reliability and consistency are protected.

## 2. Three-Track Roadmap

The product should advance A, B, and C together, but through versioned milestones. Each version must include a reliability increment, a workspace experience increment, and a content/consistency increment.

### V1: Publishable Small-Scale Production Version

V1 goal: one local machine can run the complete production chain for a small team.

Reliability:
- Use SQLite as the primary metadata store. JSONL remains only for compatibility, import, or export.
- Persist video tasks, short drama stage tasks, cost records, review records, confirmation records, and operation logs.
- Recover incomplete sessions and video tasks after service restart.
- Support retry and cancel for failed or running tasks where safe.
- Require cost estimation and human confirmation before every video API call.
- Record every key operation: confirm, revise, cancel, retry, recover, export.

Workspace experience:
- Make the single-project short drama workspace the core screen.
- Use a left stage navigator, central stage content plus human-loop dialog, and right-side status, version, asset, cost, and operation log panels.
- Add a task center for running, failed, waiting-for-confirmation, and retryable jobs.
- Add a cost center that explains estimated costs, actual costs, and provider-actual-over-estimate coverage.

Content quality and consistency:
- Use LoopAgent to connect script, style, plot, consistency, character references, storyboard, and video task stages.
- Store every stage generation, revision, and confirmation as a `StageVersion`.
- Create a first-class consistency profile covering characters, world facts, visual style, narrative constraints, and bound assets.
- Require storyboard and video prompts to cite the consistency profile.

### V2: Small-Team Production Enhancement

V2 goal: improve throughput, review efficiency, and asset reuse.

Reliability:
- Add local backup and restore commands.
- Add failed-task replay.
- Add daily budget, project budget, and batch shot limit policies.
- Improve audit reports for production and cost history.

Workspace experience:
- Add a dashboard for pending confirmations, failed tasks, today's costs, and output count.
- Add batch retry and batch confirmation where cost-safe.
- Add review notes and revision request flows.
- Add asset library filters for characters, scenes, storyboards, videos, prompts, and packages.

Content quality and consistency:
- Bind character reference images to character cards.
- Add reusable style, storyboard, and genre templates.
- Add quality scoring for short drama pacing, conflict density, and consistency risk.
- Add prompt version management.

### V3: Expansion Version

V3 goal: prepare for larger production and provider expansion.

Reliability:
- Add optional Redis, MinIO, and external worker support.
- Provide a Postgres migration path.
- Add deployment checks, health checks, and data migration tools.
- Add basic monitoring and alerts.

Workspace experience:
- Add multi-project scheduling views.
- Reserve basic role and permission boundaries.
- Expand release package workflow for Douyin, WeChat Channels, Xiaohongshu, subtitles, titles, and tags.
- Add richer production analytics.

Content quality and consistency:
- Add multi-model routing for DeepSeek, Bailian, Kling, Volcengine, and similar domestic providers.
- Add prompt A/B experiments.
- Close the loop from reference image to video generation.
- Add automatic consistency checks and revision suggestions.

## 3. Core Modules and Data Model

### Project

Represents one short drama or IP production project. It owns title, source story, project status, priority, budget metadata, current stage, and linked assets.

### Story

Represents an imported or generated novel body version. A project can have multiple story versions. V1 should support existing generated stories and manual import.

### DramaSession

Represents one LoopAgent short drama production session. It stores current stage, status, context summary, stage cursor, and whether the session is waiting for human confirmation.

### StageVersion

Represents one version of a stage output. Stages include script, style, plot, consistency, character references, storyboard, video prompts, and package drafts. Every generation, revision, restore, or confirmation creates or references a version. Stage content must not be overwritten.

### ConsistencyProfile

Consistency is the second product priority and must be a first-class entity. The profile contains:
- Character cards: name, age, appearance, clothing, personality, relationship, forbidden changes.
- World facts: time, place, social background, rules, known events.
- Visual style: color, camera language, shot rhythm, composition preference.
- Narrative constraints: main objective, reversal rhythm, facts that later stages cannot violate.
- Asset bindings: character reference images, scene references, key storyboard images.

The profile must be used as an input for later stages, not displayed only as a report.

### VideoRun

Represents one batch of video generation. It stores project, stage versions, shot count, model, status, estimated cost, confirmation metadata, submitted count, and package paths.

### VideoJob

Represents one shot-level provider job. It stores provider, provider job id, shot id, status, failure reason, retry count, output URI, and normalized status.

### Asset

Represents all reusable production assets: text, prompt, image, video, subtitle, audio, and package. Assets belong to a project and can link to stage versions, video jobs, or packages.

### Review

Represents human review and confirmation. It stores approve, reject, revision request, notes, reviewer, target kind, target id, and timestamp.

### CostLedger

Represents cost estimates and actual provider costs. It stores source, amount, project, run/job/package references, whether the entry is estimated, and metadata. Raw entries remain auditable. Summary views use effective cost rules where provider actual cost covers same-run video estimates for display and budget purposes.

### OperationLog

Represents key user and system actions: confirm, revise, cancel, retry, recover, export, import, and model call failures. V1 can use a single administrator actor while reserving actor fields for later team roles.

### Storage Rules

- SQLite is the V1 primary metadata store.
- Local object directory is the default binary asset store; MinIO is optional.
- SQLite stores URIs and metadata, not large image or video binaries.
- Every production action must trace back to a project.
- Every Agent output must be versioned.
- Every paid action must have a confirmation record.
- Every video result must become an asset.

## 4. LoopAgent Industrial Workflow

LoopAgent should automatically connect production stages while stopping at explicit human confirmation points.

### Stage Flow

```text
Start session
-> script adaptation
-> human confirm or revision
-> style design
-> human confirm or revision
-> plot design
-> human confirm or revision
-> consistency profile generation/update
-> human confirm or revision
-> character reference prompt/image task
-> human confirm or revision
-> storyboard generation
-> human confirm or revision
-> video cost estimate
-> required human cost confirmation
-> submit video tasks
-> poll, retry, and ingest assets
```

### Stage State Machine

Each stage should use the same state vocabulary:
- `queued`
- `running`
- `awaiting_review`
- `revision_requested`
- `approved`
- `failed`
- `skipped`

### Human Loop

The single-project workspace must expose each stage through a human-loop dialog:
- The user can enter revision instructions.
- Agent output based on revision instructions creates a new version.
- Old versions remain available.
- Only `confirm and continue` advances LoopAgent to the next stage.
- Confirmation records include actor, time, target version, and notes.

### Consistency Flow

Consistency must evolve through the pipeline:
- Script stage extracts initial characters and world facts.
- Style stage adds visual and narrative style.
- Plot stage checks for logic conflicts.
- Character reference stage binds character cards to reference prompts or images.
- Storyboard stage must cite character cards, style constraints, and plot facts.
- Video prompt stage must cite shot, character, scene, and style constraints.
- Any human revision triggers a consistency diff or update.

### Failure and Recovery

- Every stage failure must be persisted with a readable error.
- Users can retry the current stage.
- Restart recovery uses `DramaSession.current_stage`, stage states, and latest approved versions.
- Video retry should happen at shot level and must not resubmit successful shots.
- Over-budget, missing API key, and content risk states should stop in `awaiting_review`.

### Model Use

- Creative text stages default to DeepSeek V4 Pro.
- Character reference image and video generation use Bailian first, while keeping a provider interface for future domestic models.
- Every model call should record input summary, output version, latency, estimated cost, and failure reason.
- Prompt templates should be versioned.

## 5. Web Workspace and User Experience

### Pages

V1 should focus on four pages.

#### Project List

Shows projects with status filters:
- waiting for adaptation
- generating
- awaiting confirmation
- video running
- completed
- failed

Each row should show current stage, last updated time, today's cost, and pending action.

#### Single-Project Short Drama Workspace

This is the primary screen.

Left side:
- Novel
- Script
- Style
- Plot
- Consistency
- Character references
- Storyboard
- Video
- Release package

Center:
- Current stage content
- Human-loop dialog
- Version cards
- Revision input

Right side:
- Current status
- Latest approved version
- Consistency profile summary
- Assets
- Cost preview
- Operation log

Main actions:
- `Confirm and continue`
- `Request revision`
- `Save note`
- `Confirm cost and submit video tasks`

#### Task Center

Shows background tasks:
- stage generation
- video submission
- status refresh
- retry jobs

Users can retry, cancel, inspect errors, and view logs.

#### Asset and Cost Center

Asset library:
- character images
- scene images
- storyboard images
- videos
- prompts
- release packages

Cost center:
- daily budget
- estimated costs
- actual costs
- confirmation records
- estimate entries covered by provider actual costs

### UX Principles

- This is a production tool, not a marketing landing page.
- Use medium-to-high information density.
- Prioritize state clarity: where the project is, what it waits for, whether the next action costs money, and how failure can recover.
- Use tables, tags, timelines, drawers, logs, and compact panels.
- Avoid decorative design that hides operational status.

### Consistency UX

Because consistency is the second priority:
- The consistency profile summary should remain visible in the workspace.
- Each stage output should show which consistency sources it referenced.
- Agent-detected conflicts should be shown explicitly.
- Character cards and reference images should appear together.
- Storyboard cards should show related characters, scenes, and style tags.

## 6. Reliability, Cost, and Release Standards

### Reliability Standards

V1 must satisfy:
- Incomplete short drama stages and video tasks recover after service restart.
- No task can remain indefinitely in a vague "starting" state without an error or heartbeat.
- Failed tasks show readable error, failed stage, and retry action.
- Video jobs retry at shot level.
- Queue tasks are persisted and do not rely only on process memory.
- Stage outputs are versioned and not overwritten.
- Key human actions produce operation logs.
- Data directories can be backed up, migrated, and restored.

### Cost Control Standards

Video generation is a strong-cost action:
- Show shot count, unit price, estimated total, today's spend, and remaining budget before submission.
- Do not call video APIs without explicit confirmation.
- Persist the confirmation record.
- Record estimated cost before submission.
- When provider actual cost arrives, keep raw ledger entries but use effective display and budget rules to avoid double counting.
- Support daily budget, project budget, and per-batch shot limit.
- Video retry also requires cost confirmation.
- Cost center must explain estimate, actual, and coverage relationships.

### Release Standards

Before V1 release:
- README starts from an empty environment and reaches a running local system.
- `.env.example` covers DeepSeek, Bailian, budget, storage, and SQLite settings.
- `.env`, login state, runtime data, and object files are not committed.
- `RELEASE_CHECKLIST.md` exists.
- A formal spec exists.
- Tests cover task state, recovery, cost, confirmation, versions, and video tasks.
- Web QA covers project list, single-project workspace, task center, and cost center.
- Error states have readable UI messages.

### V1 Acceptance Scenario

The following demonstration path must work:

1. Import or select one novel.
2. Create a short drama project.
3. LoopAgent generates a script draft.
4. User requests one revision, then confirms.
5. System generates style, plot, consistency profile, character references, and storyboard.
6. User sees cost estimate in the video stage.
7. User confirms and submits 1-3 video shots.
8. Video tasks can refresh status and retry failures.
9. Generated assets enter the asset library.
10. Cost center shows estimate, actual, and coverage relationship.
11. After service restart, project state recovers.

## 7. Scope Boundaries and Risk Tradeoffs

### Explicitly Out of Scope for V1

- Full SaaS multi-tenancy.
- Complex accounts, organizations, and invitations.
- Fully automatic video spending without confirmation.
- Multi-cloud deployment or Kubernetes.
- Complex BI dashboards.
- Full support for every video provider.
- Making hot topic scraping and novel generation part of the V1 critical path.

### Required Boundaries

- Agent orchestration must be separate from model provider calls.
- Task state must be separate from Web presentation state.
- SQLite metadata must be separate from object storage.
- Estimated and actual costs must remain separate raw records while summary views use one effective cost rule.
- `StageVersion` is the source of truth; frontend cards are views.
- Consistency profile must feed later stages.
- Every confirmation point must explain why the system stopped.

### Risks and Mitigations

Risk: scope grows because A, B, and C all advance.
Mitigation: use V1/V2/V3 boundaries and stop lines.

Risk: consistency becomes decorative text.
Mitigation: require prompt inputs, storyboard schema, and video prompt schema to include consistency references.

Risk: local asset storage grows too large.
Mitigation: SQLite stores metadata only; local object directory or MinIO stores binary assets.

Risk: task recovery becomes complex.
Mitigation: persist `VideoRun`, `VideoJob`, stage states, and run recovery scans on startup.

Risk: cost reporting loses trust.
Mitigation: keep raw ledger entries auditable and show effective totals with explicit coverage explanations.

Risk: Web polish outruns production reliability.
Mitigation: workspace UI exists to expose production actions, not to decorate the product.

## 8. Implementation Planning Notes

The implementation plan should start with V1 and split work into independently verifiable phases:

1. Formalize SQLite-backed project/session/stage/cost/operation data contracts.
2. Add consistency profile model and stage references.
3. Harden LoopAgent stage state and confirmation gates.
4. Add restart recovery and task center visibility.
5. Refine cost confirmation and coverage explanations.
6. Build single-project workspace around stage versions and human-loop dialog.
7. Add asset ingestion and asset library views.
8. Add release checklist, documentation, and Web QA.

The plan should not start with visual polish or multi-provider expansion. Those become useful only after state, consistency, cost, and recovery are trustworthy.

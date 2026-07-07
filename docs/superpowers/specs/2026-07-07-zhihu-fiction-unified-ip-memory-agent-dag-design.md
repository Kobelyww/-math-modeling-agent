# Zhihu Fiction Unified IP Memory And Agent DAG Design

Date: 2026-07-07
Status: Approved design draft
Scope: `zhihu_fiction` functional core upgrade before database, Redis, MinIO, or frontend framework expansion

## 1. Goal

Upgrade `zhihu_fiction` from a pair of mostly linear generation flows into a reusable IP production engine:

```text
topic / imported story
-> unified IP memory
-> fiction generation or revision
-> short-drama adaptation
-> storyboard and video prompt package
-> human-confirmed video generation tasks
```

The next implementation phase should improve product capability first. It should not begin with infrastructure migration. The immediate target is stronger Agent behavior, durable creative memory, stage-level reasoning, consistency checks, and better traceability between the novel and short-drama outputs.

## 2. Reference Products And Lessons

The design borrows product patterns from several open-source projects:

- MoneyPrinterTurbo: short-video production should treat script, material selection, subtitles, voice, background music, composition, batch generation, Web UI, and API as one pipeline.
- NarratoAI: short-drama and commentary production benefits from video understanding, automated editing, TTS, subtitles, and exportable editing packages.
- ComfyUI: generation pipelines should be represented as reusable graph nodes with explicit inputs, outputs, dependencies, partial reruns, and saved workflow definitions.
- Show Me The Story: long-form fiction needs outline review, chapter review, foreshadowing, narrative memory, fact checks, full-book optimization, and an AI assistant that can safely operate project state.
- SillyTavern and textgen: creative AI systems become usable when they expose character cards, world/lore books, context injection controls, backend model abstraction, and user-controllable generation state.

These references point to the same product direction: `zhihu_fiction` should stop relying on one-pass prompts and instead provide a controllable production memory plus a stage graph that the Agent can inspect, revise, and resume.

## 3. Current Project Context

The project already has enough foundation for this phase:

- Fiction pipeline: `zhihu_fiction/pipeline.py`, `zhihu_fiction/orchestrator.py`, `zhihu_fiction/agents.py`.
- Short-drama package model: `zhihu_fiction/drama/models.py`, `zhihu_fiction/drama/adapter.py`, `zhihu_fiction/drama/prompts.py`.
- Video provider path: `zhihu_fiction/drama/video.py` with Bailian/DashScope support and RMB-friendly provider assumptions.
- Short-drama web/runtime services: `zhihu_fiction/app/services/drama_video_deepagent_flow.py`, `zhihu_fiction/app/services/drama_video_stage_generation.py`, `zhihu_fiction/app/services/drama_video_stage_quality.py`, `zhihu_fiction/app/services/drama_video_runtime.py`.
- Existing industrial short-drama spec: `zhihu_fiction/docs/superpowers/specs/2026-06-15-industrialized-short-drama-factory-design.md`.

The missing product layer is not another model API. The missing layer is a unified creative memory that both fiction and drama Agents can read and update, plus a graph-like execution contract that makes each stage auditable and rerunnable.

## 4. Non-Goals

This phase does not implement:

- SQL, Redis, MinIO, or Postgres migration.
- A full frontend framework rewrite.
- New paid video providers beyond the existing provider interface.
- Automatic final video editing, dubbing, subtitles, or soundtrack generation.
- Multi-user authentication and permissions.
- A total rewrite of the fiction pipeline.

The phase can add stable interfaces that make those future upgrades easier, but the first deliverable should work with the current local file-backed and service-backed architecture.

## 5. Product Requirements

### 5.1 Unified IP Memory

Create a first-class memory package for each generated or imported work. The memory package should be reusable by fiction generation, fiction revision, short-drama adaptation, storyboard creation, and future video generation.

Required memory entities:

- `StoryBible`: title, premise, genre, target reader/viewer, core hook, emotional promise, ending direction, taboo changes.
- `CharacterCard`: name, role, visual identity, personality, motivation, relationship edges, speech style, forbidden changes, asset bindings.
- `WorldFact`: time, place, social background, rules, events, props, constraints, source references.
- `Foreshadowing`: setup, active chapters or episodes, payoff plan, status, risk if forgotten.
- `NarrativeMemory`: concrete details that are easy to lose, such as promises, habits, prop states, emotional debts, injuries, aliases, and location changes.
- `StyleGuide`: fiction voice, short-drama tone, camera language, pacing, color preference, shot rhythm, content boundaries.
- `AssetBinding`: character reference images, scene references, storyboard images, video outputs, subtitles, audio, and prompt assets.

Every entity should be serializable to JSON and renderable as prompt context. Entities should preserve source metadata so later stages can explain where a fact came from.

### 5.2 Fiction Workflow Enhancement

The fiction pipeline should use memory in the following way:

```text
topic collection / imported story
-> generate or extract StoryBible
-> generate outline and foreshadowing plan
-> generate chapter
-> review chapter
-> extract NarrativeMemory and updated WorldFacts
-> fact and consistency check
-> confirm or revise
```

Requirements:

- A generated story must not be treated as only raw text after completion.
- The pipeline should extract characters, world facts, style, and foreshadowing after creation.
- Later chapters or rewrites should receive a compact memory context instead of only previous story text.
- Empty or low-quality extraction should fail softly with readable diagnostics and should not erase existing memory.
- The review stage should include memory consistency findings, not only prose quality.

### 5.3 Short-Drama Workflow Enhancement

The short-drama workflow should consume the fiction memory package as a primary input:

```text
Story + IP memory
-> adaptation blueprint
-> episode plot design
-> script
-> style design
-> consistency profile
-> character reference prompt or image plan
-> storyboard
-> video prompt package
-> cost confirmation
-> video task submission
```

Requirements:

- The drama Agent must read `StoryBible`, `CharacterCard`, `WorldFact`, `Foreshadowing`, and `StyleGuide` before creating stage output.
- Each stage output must cite which memory entities it used.
- Each stage can propose memory updates, but human confirmation is required before updates become approved memory when they alter major facts.
- Storyboard and video prompts must include stable character and scene references.
- Video prompt packages should reserve fields for TTS, subtitle, BGM, and editing metadata even if those are not generated yet.

### 5.4 Agent DAG Contract

Represent the production workflow as a graph of stage nodes rather than a hidden linear script. V1 can implement this as Python data structures and JSON manifests, without adding a graph database.

Each node must define:

- `node_id`
- `stage`
- `inputs`
- `outputs`
- `required_memory`
- `tools`
- `quality_gates`
- `human_review_policy`
- `retry_policy`
- `cost_policy`
- `next_nodes`

Initial nodes:

- `fiction.topic_intake`
- `fiction.story_bible`
- `fiction.outline`
- `fiction.chapter`
- `fiction.review`
- `fiction.memory_extract`
- `drama.adaptation_blueprint`
- `drama.episode_plot`
- `drama.script`
- `drama.style`
- `drama.consistency`
- `drama.character_reference`
- `drama.storyboard`
- `drama.video_prompt_package`
- `video.cost_confirmation`
- `video.submit_jobs`

The current DeepAgent stage flow can continue to execute linearly, but it should emit and persist node-level trace data matching this contract.

### 5.5 Agent Tooling

The main Agent should gain explicit tools instead of relying on one large prompt.

Required tools:

- `inspect_ip_memory(project_id_or_story_path)`: returns compact memory context and warnings.
- `write_ip_memory_patch(target, patch)`: proposes additive or corrective memory changes.
- `build_stage_context(stage, memory, prior_versions)`: creates stage-specific prompt context.
- `generate_stage_draft(stage, context, instructions)`: creates the draft.
- `review_stage_output(stage, output, memory)`: returns quality, consistency, and cost-risk checks.
- `request_human_review(stage, draft, review)`: moves the node to `awaiting_review`.
- `apply_human_revision(stage, version_id, instruction)`: creates a new version without overwriting old output.
- `advance_agent_graph(session_id)`: advances to the next valid node after confirmation.

The Agent trace should show tool calls, memory reads, memory patches, review findings, and human-loop checkpoints.

### 5.6 Human Loop

Human loop remains mandatory at the same conceptual points, but it should become more informative.

For each review checkpoint, the UI and API should expose:

- Current node and stage.
- Draft output.
- Memory entities used.
- Proposed memory changes.
- Consistency warnings.
- Quality score and review explanation.
- Revision instruction field.
- Confirm, revise, retry, and cancel actions.

Confirming a stage should record the approved output, approved memory patches, actor, timestamp, and next node.

### 5.7 Skills

Introduce reusable creative skills that can be attached to fiction or drama stages.

Initial skills:

- `viral_zhihu_hook`: turns topic into a high-curiosity premise.
- `web_fiction_pacing`: controls conflict density, reversal cadence, and chapter-ending hooks.
- `anti_ai_polish`: removes repetitive AI-like phrasing.
- `foreshadowing_planner`: creates setup and payoff plans.
- `continuity_checker`: checks contradictions against memory.
- `short_drama_pacing`: converts prose into 60-90 second episode rhythm.
- `shot_prompt_builder`: transforms scenes into video-model-friendly shot prompts.
- `bailian_video_prompt_guard`: keeps prompts compatible with Bailian/DashScope video generation constraints.

Skills should be versioned prompt modules with metadata:

- `skill_id`
- `version`
- `supported_stages`
- `input_contract`
- `output_contract`
- `risk_notes`

### 5.8 Observability

Every generated run should have a readable production trace:

- selected workflow nodes
- memory snapshot hash
- model used
- prompt template or skill versions
- input summary
- output version id
- review score
- human decision
- error and retry history

This trace should be available to tests and eventually to the Web workbench. It does not need to store full prompts in production by default, but local development can keep prompt excerpts for debugging.

## 6. Data Storage Approach

V1 should remain storage-light:

```text
zhihu_fiction/data/ip_memory/
  <project_or_story_id>/
    memory.json
    versions/
      <timestamp>-memory-patch.json
    traces/
      <run_id>.json
```

The file-backed implementation should use atomic writes where practical. It should avoid mixing user secrets, generated media binaries, and memory metadata in the same file.

Future SQL migration should map these concepts directly to tables, but SQL is not required in this phase.

## 7. API And UI Surface

Initial API additions:

- `GET /api/ip-memory/{project_id}`
- `POST /api/ip-memory/{project_id}/extract`
- `POST /api/ip-memory/{project_id}/patch`
- `GET /api/drama-video/deepagent/{run_id}/trace`

Initial UI additions:

- A right-side IP memory panel in the single-work workspace.
- Tabs for Story Bible, Characters, World Facts, Foreshadowing, Style, and Assets.
- Stage trace cards showing memory used, review status, and proposed changes.
- Human-loop dialog fields for revision instruction and memory patch approval.

The UI should not become a new landing page. It should improve the existing workbench.

## 8. Error Handling

Failure rules:

- Memory extraction failure should create a failed trace entry and keep prior memory intact.
- Invalid memory patches should be rejected before persistence.
- Stage generation can proceed with partial memory only if the trace clearly marks missing required memory.
- Contradictions above a configured severity should stop at `awaiting_review`.
- Paid actions still require explicit cost confirmation.
- Retrying a node should create a new output version and should not overwrite approved versions.

## 9. Testing Strategy

Add focused tests before implementation:

- Memory models serialize and deserialize without losing source metadata.
- Memory extraction from a sample story creates StoryBible, CharacterCard, WorldFact, and StyleGuide entries.
- Empty extraction does not erase existing memory.
- Fiction stage context includes the expected memory sections.
- Drama DeepAgent starts with memory context rather than raw story only.
- Stage review reports consistency warnings when output contradicts memory.
- Human revision creates a new version and preserves previous approved output.
- Agent trace records node id, memory snapshot, tool calls, review result, and human decision.

Run target checks:

```bash
python -m pytest zhihu_fiction/tests -q
python -m compileall -q zhihu_fiction
git diff --check
```

## 10. Rollout Plan

### Milestone 1: Memory Core

Create memory data models, repository, prompt rendering, and tests. No production flow changes except optional extraction from a completed story.

### Milestone 2: Fiction Memory Integration

Extract story memory after fiction generation. Inject memory into revision and review contexts. Add consistency review output.

### Milestone 3: Drama Memory Integration

Load IP memory when starting a short-drama DeepAgent session. Add memory-used citations and proposed memory patches to stage outputs.

### Milestone 4: Agent DAG Trace

Add node-level graph manifests and trace records around the existing fiction and drama stage execution.

### Milestone 5: Workbench UX

Expose memory, stage trace, and memory patch confirmation in the existing single-work workspace.

## 11. Acceptance Criteria

The phase is complete when:

- A generated or imported story can produce an IP memory package.
- Fiction review and drama generation can consume the same memory package.
- Drama stage outputs record memory entities used and consistency findings.
- Human revisions create new versions without overwriting old content.
- Agent traces show stage node, memory snapshot, tool calls, review result, and human decision.
- Existing fiction and drama tests pass.
- New tests cover memory extraction, injection, consistency review, revision versioning, and trace output.

## 12. Spec Self-Review

- Placeholder scan: no unresolved placeholders or intentionally deferred implementation details remain.
- Scope check: this spec is limited to functional core upgrade and excludes database and provider expansion.
- Consistency check: memory, Agent graph, human loop, skills, trace, and UI requirements all point to the same project-level workflow.
- Ambiguity check: SQL, Redis, MinIO, final video editing, and frontend rewrite are explicitly out of scope for this phase.

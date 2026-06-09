# Zhihu Fiction Short Drama Prompt Package Design

Date: 2026-06-09

## Goal

Add a post-processing capability to `zhihu_fiction` that converts a generated novel into a short-drama prompt package prepared for future video generation models.

The first version does not call any video generation API. It produces structured scripts, shot plans, consistency prompts, and machine-readable JSON files that can later feed providers such as Kling, Runway, Pika, Veo, Sora, or another video model adapter.

Primary flow:

```text
WorkflowResult.final_story
-> short-drama adaptation plan
-> episode scripts
-> character and location consistency settings
-> shot table
-> video generation prompt package
```

## Confirmed Decisions

- Scope: convert already generated novels into short-drama prompt packages.
- Default format: up to 10 episodes.
- Episode length: 60-90 seconds.
- Shot density: 6-12 shots per episode.
- Shot length: 5-8 seconds.
- Integration approach: standalone novel-to-drama module, not a rewrite of the existing fiction pipeline.
- First version output: files only, no video generation API calls.
- Future video-model support should be added through provider adapters that consume the package schema.

## Existing Project Context

Current `zhihu_fiction` already provides:

- `orchestrator.py`: `WorkflowResult` with `topic`, `genre`, `synthesis`, and `final_story`.
- `pipeline.py`: one-run fiction creation, review, rewrite, run records, and scheduling.
- `exporter.py` and `publishers/`: post-generation publishing package export.
- `cli.py`: commands such as `/create`, `/load`, `/publish`, and `/autopublish`.
- `server.py`: FastAPI run, stream, story, history, skill, and scheduler APIs.

The cleanest short-drama integration point is `WorkflowResult.final_story`. The short-drama module should act like a post-generation export path, similar in spirit to `/publish`, while keeping its data model separate because short drama needs episodes, shots, characters, locations, and video prompts.

## Product Scope

### In Scope

1. Convert a `WorkflowResult` into a structured `DramaProject`.
2. Generate a short-drama adaptation plan from the novel.
3. Generate character and location consistency settings.
4. Generate up to 10 episode scripts.
5. Generate a shot-level table for each episode.
6. Generate video-model prompt fields for each shot.
7. Export both human-readable Markdown and machine-readable JSON.
8. Add a CLI `/drama` command for the latest or loaded story.
9. Add focused model, adapter, exporter, and CLI tests.

### Out of Scope

- Calling video generation APIs.
- Managing video generation queues.
- Generating character reference images.
- Generating final video files.
- Editing or cutting generated video clips.
- Replacing the existing fiction pipeline.
- Building a full short-drama production workspace in this slice.

## Recommended Architecture

Add a new package:

```text
zhihu_fiction/drama/
├── __init__.py
├── models.py
├── adapter.py
├── exporter.py
└── prompts.py
```

Responsibilities:

- `models.py`: data classes and validation for short-drama projects.
- `prompts.py`: LLM prompt templates for adaptation planning and shot generation.
- `adapter.py`: calls the LLM, parses JSON, validates the result, and returns a `DramaProject`.
- `exporter.py`: writes the prompt package files.

Future video generation support should be added separately:

```text
zhihu_fiction/drama/video_providers/
├── base.py
├── kling.py
├── runway.py
└── ...
```

Provider adapters should consume `manifest.json` and `shot_table.json` rather than depending on fiction pipeline internals.

## Data Model

### DramaProject

Fields:

- `title`
- `source_title`
- `genre`
- `logline`
- `audience`
- `episode_count`
- `characters`
- `locations`
- `episodes`
- `adaptation_notes`
- `risk_notes`

Purpose:

Top-level short-drama project. It is the source for all exported Markdown and JSON files.

### DramaCharacter

Fields:

- `id`
- `name`
- `role`
- `age_range`
- `appearance`
- `costume`
- `personality`
- `motivation`
- `consistency_prompt`

Purpose:

Defines each recurring character and provides a stable visual identity prompt for future video generation.

### DramaLocation

Fields:

- `id`
- `name`
- `visual_style`
- `time_period`
- `lighting`
- `consistency_prompt`

Purpose:

Defines recurring locations so shot prompts can reference stable scene identities.

### DramaEpisode

Fields:

- `index`
- `title`
- `hook`
- `synopsis`
- `cliffhanger`
- `shots`

Purpose:

Represents one 60-90 second episode.

### DramaShot

Fields:

- `id`
- `episode_index`
- `scene_index`
- `shot_index`
- `duration_seconds`
- `location_id`
- `character_ids`
- `action`
- `dialogue`
- `emotion`
- `camera`
- `visual_prompt`
- `negative_prompt`
- `consistency_refs`

Purpose:

Represents one future video generation task. A later provider adapter can map each shot to a model request.

Example:

```json
{
  "id": "ep01_sc02_sh05",
  "episode_index": 1,
  "scene_index": 2,
  "shot_index": 5,
  "duration_seconds": 6,
  "location_id": "living_room",
  "character_ids": ["heroine", "stepmother"],
  "action": "女主抬头看向继母，第一次露出反击的眼神。",
  "dialogue": "你以为我还是三年前那个任你摆布的人吗？",
  "emotion": "压抑后的爆发",
  "camera": "medium close-up, slow push in",
  "visual_prompt": "modern Chinese family living room, tense confrontation, cinematic lighting, medium close-up, slow push in",
  "negative_prompt": "low quality, blurry, extra fingers, distorted face, inconsistent costume",
  "consistency_refs": ["character.heroine", "character.stepmother", "location.living_room"]
}
```

## Generation Flow

1. User creates or loads a story through existing flows:

```text
/create 一个适合短剧改编的复仇爽文
```

or:

```text
/load <story-file>
```

2. User runs:

```text
/drama
```

3. CLI passes the current `WorkflowResult` to `DramaAdapter`.

4. `DramaAdapter` reads:

- `result.topic`
- `result.genre`
- `result.final_story`
- `result.synthesis`

5. LLM call 1 generates the adaptation blueprint:

- short-drama title
- logline
- target audience
- episode count
- character list
- location list
- episode outline
- adaptation notes
- risk notes

6. LLM call 2 generates shot-level scripts and video prompts:

- episode hook
- synopsis
- cliffhanger
- scene and shot indexes
- shot duration
- character and location references
- action, dialogue, emotion, camera language
- `visual_prompt`
- `negative_prompt`
- `consistency_refs`

7. Adapter parses and validates the JSON.

8. `DramaExporter` writes a package directory.

9. CLI prints the output directory, episode count, and shot count.

## Output Package

Output directory:

```text
zhihu_fiction/output/<story>/短剧视频Prompt包_<timestamp>/
├── manifest.json
├── 改编方案.md
├── 角色一致性设定.md
├── 分集剧本.md
├── 镜头表.json
├── 视频生成Prompts.md
└── raw_output.txt
```

File rules:

- `manifest.json`: top-level project metadata and references to package files.
- `改编方案.md`: human-readable adaptation strategy.
- `角色一致性设定.md`: character and location consistency prompts.
- `分集剧本.md`: readable episode scripts.
- `镜头表.json`: machine-readable shot table for future video generation.
- `视频生成Prompts.md`: human-readable prompts grouped by episode and shot.
- `raw_output.txt`: only written when parsing or validation fails, or when debug output is useful.

The exporter should create a timestamped directory and never overwrite an existing package.

## Validation Rules

Validation should happen before package export.

Rules:

- Novel text must not be empty.
- `episode_count` must be between 1 and 10.
- Number of `episodes` must match `episode_count`.
- Each episode must have 6-12 shots.
- Each shot must have `duration_seconds` between 5 and 8.
- Each shot must reference an existing `location_id`.
- Each shot character reference must exist in `characters`.
- Each shot must include `visual_prompt`.
- Each shot must include `negative_prompt`.
- Each shot must include stable `consistency_refs`.

First version should fail clearly on invalid output instead of silently truncating or repairing complex model errors.

## Error Handling

- Empty story: reject the request with a clear message.
- LLM returns invalid JSON: save `raw_output.txt` and return a parsing error.
- Missing required fields: return a validation error naming the missing field.
- More than 10 episodes: validation error.
- Episode has fewer than 6 or more than 12 shots: validation error.
- Shot duration outside 5-8 seconds: validation error.
- Unknown character or location references: validation error.
- Output directory already exists: create a new timestamped directory.
- CLI `/drama` with no loaded story: print a clear message asking the user to run `/create` or `/load` first.

## CLI Design

Add:

```text
/drama        Convert the latest or loaded story into a short-drama video prompt package.
```

Behavior:

- Requires `self.last_result`.
- Uses a lower-temperature LLM, for example `temperature=0.3`, to improve structural consistency.
- Writes the package through `DramaExporter`.
- Prints:

```text
短剧 Prompt 包已生成：
<output_dir>
共 <episode_count> 集，<shot_count> 个镜头
```

If no story is available:

```text
没有可转换的小说。请先运行 /create <主题> 或 /load <文件名>。
```

Optional later CLI extension:

```text
/drama <story-file>
```

The first version can rely on existing `/load` plus `/drama` to keep scope smaller.

## Web API Design

The first implementation can be CLI-only if needed, but the module should not block future Web integration.

Recommended later route:

```text
POST /api/stories/{story_path}/drama-package
```

Response:

```json
{
  "status": "ok",
  "package_dir": "...",
  "episode_count": 8,
  "shot_count": 74
}
```

The API should reuse `DramaAdapter` and `DramaExporter`; it should not duplicate prompt or validation logic.

## Testing

Add focused tests:

```text
zhihu_fiction/tests/test_drama_models.py
zhihu_fiction/tests/test_drama_adapter.py
zhihu_fiction/tests/test_drama_exporter.py
zhihu_fiction/tests/test_cli_drama.py
```

Coverage:

- Valid `DramaProject` serializes to JSON.
- Empty story is rejected.
- More than 10 episodes fails validation.
- Shot duration outside 5-8 seconds fails validation.
- Unknown character reference fails validation.
- Unknown location reference fails validation.
- Adapter parses valid LLM JSON.
- Adapter handles invalid LLM JSON with a clear error.
- Exporter writes the target package files.
- Exporter does not overwrite an existing package.
- CLI `/drama` with no story prints a clear message.

Test command:

```bash
pytest zhihu_fiction/tests
```

## Implementation Order

1. Add `zhihu_fiction/drama/models.py` with data classes, serialization, and validation.
2. Add tests for valid and invalid model data.
3. Add `prompts.py` with blueprint and shot-generation prompts.
4. Add `adapter.py` with LLM invocation, JSON parsing, and validation.
5. Add adapter tests using fake LLM responses.
6. Add `exporter.py` and exporter tests.
7. Add CLI `/drama` command.
8. Add CLI tests for no-story and happy-path behavior.
9. Update `zhihu_fiction/README.md` with the short-drama prompt package workflow.
10. Run `pytest zhihu_fiction/tests`.

## Acceptance Criteria

1. After `/create` or `/load`, user can run `/drama`.
2. `/drama` generates a timestamped short-drama prompt package directory.
3. Package contains `manifest.json`, `改编方案.md`, `角色一致性设定.md`, `分集剧本.md`, `镜头表.json`, and `视频生成Prompts.md`.
4. Generated project has 1-10 episodes.
5. Each episode has 6-12 shots.
6. Each shot lasts 5-8 seconds.
7. Each shot has character, location, camera, dialogue, action, visual prompt, negative prompt, and consistency references.
8. Invalid LLM output fails clearly and preserves raw output for debugging.
9. Existing fiction generation, loading, publishing, and tests continue to work.

Expected CLI result:

```text
短剧 Prompt 包已生成：
zhihu_fiction/output/<story>/短剧视频Prompt包_<timestamp>/
共 8 集，74 个镜头
```

## Future Extensions

- Web story detail button: "生成短剧 Prompt 包".
- Video provider adapters that consume `镜头表.json`.
- Video task queue with retry, cost tracking, and per-shot status.
- Character reference image generation.
- Shot regeneration from user feedback.
- Clip review and manual approval workflow.
- Final video assembly and export.
- Short-drama analytics for hook strength, completion risk, production cost, and model success rate.

# Zhihu Fiction Studio MVP Design

Date: 2026-06-05

## Goal

Turn `zhihu_fiction` from an AI fiction generation prototype into a usable short-story production workspace.

The MVP should complete one practical loop:

```text
collect trend/sample material
→ distill reusable writing skills
→ create a short-story task
→ generate and review the story
→ revise based on structured feedback
→ let the user inspect/edit the result
→ export a publishing package
→ record the run for later review
```

The MVP focuses on productizing the first useful workflow, not building a full SaaS platform, long-form IP system, or unattended publishing bot.

## Product Scope

### In scope

1. Productization basics: documentation, environment examples, clearer configuration errors, safety notes, and current tests.
2. Structured review: reviewer output becomes machine-readable while preserving raw text fallback.
3. Skill distillation improvements: skill cards become structured by platform and genre.
4. Short-story web workspace: create tasks, stream progress, inspect stage outputs, review scores, publish package, and history.
5. Standardized publishing package: a stable schema with Markdown/JSON export and manual confirmation before assisted publishing.

### Out of scope

- User accounts and permissions.
- Multi-tenant SaaS deployment.
- Cloud database migration.
- Automated account-matrix publishing.
- Real automatic publishing to Xiaohongshu or WeChat official accounts.
- Long-form IP worldbuilding and continuity management.
- Payments, team collaboration, or analytics dashboards.

## Existing Project Context

Current core modules:

- `scraper.py`: Zhihu hot-list, search, manual entry, caching.
- `distiller.py`: extracts writing skills from collected content.
- `skills_store.py`: stores and retrieves skill cards.
- `agents.py`: DeepAgent tool prompts for topic analysis, outline, draft, polishing, review, and publishing synthesis.
- `orchestrator.py`: wraps coordinator invocation and parses coordinator output.
- `pipeline.py`: autonomous pipeline, moderation, review/rewrite loop, scheduling, checkpoints, run records.
- `exporter.py` and `publishers/`: multi-platform metadata and publishing package adapters.
- `server.py`: FastAPI app, SSE progress, history, story and skill APIs, scheduler APIs.
- `cli.py`: interactive CLI for scraping, distillation, generation, export, continuation, and assisted publishing.

The existing system already has most of the raw capabilities. The MVP should standardize data formats, make the quality loop explicit, and expose a clearer web workflow.

## Recommended Architecture

Keep the current file-based architecture for MVP. Do not introduce a database or major framework change yet.

Add stable domain schemas around the existing workflow:

```text
MaterialItem
SkillCard
StoryTaskRequest
StageOutput
ReviewResult
PublishPackage
RunRecord
```

These schemas can be implemented as dataclasses or Pydantic models depending on the module boundary:

- Use dataclasses for internal pipeline records if staying close to current style.
- Use Pydantic models for API request/response boundaries in `server.py`.

The main design principle is to preserve existing CLI behavior while letting Web and tests rely on stable structured data.

## Data Flow

```text
Scraper / Manual Entry
    ↓
Material Library
    ↓
Distiller
    ↓
Structured SkillCard Store
    ↓
Story Task Request: topic + platform + genre + mode + word target
    ↓
Pipeline / Orchestrator
    ↓
Stage Outputs: topic analysis, outline, draft, polished story, synthesis
    ↓
Structured ReviewResult
    ↓
Targeted Revision if needed
    ↓
PublishPackage generation
    ↓
RunRecord persisted to output/.pipeline/runs.jsonl
    ↓
Web history and export views
```

## Module Design

### 1. Productization Basics

Files:

- `zhihu_fiction/README.md`
- `zhihu_fiction/.env.example`
- `zhihu_fiction/config.py`
- `zhihu_fiction/tests/`

Changes:

- Keep README focused on installation, configuration, CLI, Web, data directories, testing, and safety boundaries.
- Add `.env.example` with all supported DeepSeek variables.
- Improve missing or malformed environment variable messages in `config.py`.
- Document sensitive runtime directories such as `data/auth/`.

Acceptance criteria:

- A new user can start CLI and Web from README instructions.
- Missing `DEEPSEEK_API_KEY` fails with a clear setup message.
- Existing tests pass.

### 2. Structured Review

Files:

- `agents.py`
- `orchestrator.py`
- `pipeline.py`
- `server.py`
- `tests/test_agents.py`
- `tests/test_pipeline.py`

Review schema:

```json
{
  "overall_score": 7.6,
  "viral_probability": 0.72,
  "scores": {
    "hook": 8,
    "pacing": 7,
    "character": 7,
    "logic": 6,
    "emotion": 8,
    "quotable_lines": 7,
    "ending": 8,
    "platform_fit": 8
  },
  "must_fix": [
    {
      "priority": 1,
      "issue": "中段反转不足",
      "suggestion": "在第 3 节增加一次身份误导"
    }
  ],
  "decision": "revise"
}
```

Allowed `decision` values:

- `accept`
- `revise`

Changes:

- Update reviewer prompt to request JSON only.
- Add a parser that extracts JSON from model output.
- Preserve raw review text if parsing fails.
- Pipeline uses `overall_score` and `decision` to decide whether to revise.
- Revision prompt uses `must_fix` instead of asking for a full workflow rerun.
- API responses include both parsed review data and raw review text.

Acceptance criteria:

- Valid JSON review parses into structured data.
- Invalid JSON does not crash the pipeline.
- Low score or `decision=revise` triggers targeted revision.
- High score and `decision=accept` skips revision.
- Tests cover valid review, invalid review fallback, revise, and accept paths.

### 3. Skill Distillation Improvements

Files:

- `distiller.py`
- `skills_store.py`
- `agents.py`
- `orchestrator.py`
- `server.py`
- related tests

Skill card schema:

```json
{
  "genre": "悬疑",
  "platform": "zhihu",
  "version": 1,
  "source_count": 12,
  "hook_patterns": [],
  "plot_patterns": [],
  "reversal_patterns": [],
  "emotion_triggers": [],
  "title_patterns": [],
  "interaction_patterns": [],
  "risk_notes": [],
  "examples": []
}
```

Changes:

- Store skills by `platform + genre`.
- Keep compatibility with existing genre-only lookup by defaulting platform to `zhihu`.
- Distillation outputs structured skill cards.
- Creation flow retrieves the best matching card for selected platform and genre.
- Web API exposes available platforms, genres, and skill summaries.

Acceptance criteria:

- `/distill` creates or updates a structured skill card.
- `/skills` and existing skill lookup continue to work.
- Web can list skill genres and show one skill card.
- Story generation receives the matched skill content.
- Tests cover reading, writing, updating, and fallback lookup.

### 4. Short-Story Web Workspace

Files:

- `server.py`
- `static/`
- `pipeline.py`

Workspace sections:

```text
Material Library
Skill Library
Create Story Task
Live Progress
Stage Outputs
Review Result
Publish Package
Run History
```

MVP UI expectations:

- Simple layout is acceptable.
- The workflow should be understandable without reading CLI help.
- SSE should show stage-level progress.
- Stage outputs should be inspectable after completion.
- History should link to generated story and publish package.

API changes:

- Extend `/api/run` request with `platform`, `genre`, `mode`, and optional `word_target`.
- Extend run response/history with review score, revision count, publish package path, and skill card reference.
- Add or extend endpoints for material and publishing package retrieval as needed.

Acceptance criteria:

- User can create a story task from the browser.
- User can watch progress via SSE.
- User can view final story, review result, and publish package.
- User can inspect recent runs.

### 5. Standardized Publishing Package

Files:

- `exporter.py`
- `publishers/base.py`
- `publishers/zhihu.py`
- `publishers/qidian.py`
- `publishers/fanqie.py`
- `automator_zhihu.py`
- `server.py`

Publish package schema:

```json
{
  "platform": "zhihu",
  "title": "",
  "subtitle": "",
  "content": "",
  "tags": [],
  "recommendation": "",
  "category": "",
  "word_count": 0,
  "risk_notes": [],
  "metadata": {}
}
```

Changes:

- Export Markdown and JSON for every publish package.
- Keep current Zhihu, Qidian, and Fanqie adapters, but make their output conform to the shared schema.
- Add reserved platform values for future `xiaohongshu` and `wechat`, without implementing real automatic publishing.
- Assisted publishing must require an explicit user action.

Acceptance criteria:

- A completed story can produce a JSON publish package.
- A completed story can produce a Markdown publish package.
- Package contains title, content, tags, recommendation, platform, and word count.
- Browser-assisted publishing is not triggered automatically.

## Error Handling

- Missing config: fail early with setup instructions.
- LLM output format errors: preserve raw output and continue with fallback when safe.
- Review parse failure: mark review as unstructured and do not crash.
- Publish package metadata failure: use story title, genre, first content preview, and empty tags as fallback.
- Web task failure: store failed run status and show the error in history.

Do not add broad silent fallbacks that hide real failures. Fallbacks should preserve enough raw data for debugging.

## Testing Plan

Run existing tests after each implementation slice:

```bash
python -m pytest zhihu_fiction/tests
```

Add tests for:

1. Review JSON parsing.
2. Review fallback behavior.
3. Pipeline revise/accept decisions.
4. Skill card read/write/update/fallback lookup.
5. Publish package schema and exports.
6. Basic API task creation and history response using fake LLM/pipeline components.

## Implementation Order

1. Productization basics.
2. Structured review.
3. Skill card schema and skill lookup.
4. Web workspace flow.
5. Publishing package schema and export.
6. Final review and verification.

Each implementation slice should pass the project rule for two reviews:

1. Spec review: compare changes against this design and identify omissions or extra scope.
2. Quality review: check naming, boundaries, edge cases, and test coverage.

## MVP Success Criteria

The MVP is complete when:

1. CLI and Web setup instructions are clear and current.
2. A user can collect or enter material.
3. A user can distill a structured skill card.
4. A user can create a short-story task from Web.
5. The system shows live generation progress.
6. The system returns a structured review score.
7. The system performs targeted revision when review requires it.
8. The user can inspect the final story and publish package.
9. The system records the run with review and export metadata.
10. Core tests pass, including new review, skill, pipeline, and export tests.

## Future Phases

After MVP, the next logical phases are:

1. Add platform-specific writing modes for Xiaohongshu and WeChat official account stories.
2. Add lightweight data review for story scores, rewrite frequency, and platform packages.
3. Add real platform adaptation for titles, tags, word count, and style.
4. Add long-form web novel support only after the short-story workflow is stable.
5. Add IP incubation features such as character bible, world bible, episode planning, and short-drama adaptation.
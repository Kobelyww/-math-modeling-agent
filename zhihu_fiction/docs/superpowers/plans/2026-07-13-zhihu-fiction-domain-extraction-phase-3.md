# Zhihu Fiction Domain Extraction Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the `zhihu_fiction.fiction` namespace for the story-generation domain without breaking legacy imports.

**Architecture:** This phase creates import-compatible re-export modules for the current fiction production chain: agents, orchestrator, pipeline, scraper, distiller and skills store. Implementation bodies remain in legacy root modules until downstream imports can be migrated safely.

**Tech Stack:** Python packages, pytest, compatibility shims.

---

### Task 1: Lock Fiction Namespace Compatibility

**Files:**
- Create: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add a failing compatibility test**

Assert that `zhihu_fiction.fiction.agents`, `orchestrator`, `pipeline`, `scraper`, `distiller`, and `skills_store` expose the same public story-generation objects as the legacy root modules.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.fiction'
```

### Task 2: Add Fiction Compatibility Namespace

**Files:**
- Create: `zhihu_fiction/fiction/__init__.py`
- Create: `zhihu_fiction/fiction/agents.py`
- Create: `zhihu_fiction/fiction/orchestrator.py`
- Create: `zhihu_fiction/fiction/pipeline.py`
- Create: `zhihu_fiction/fiction/scraper.py`
- Create: `zhihu_fiction/fiction/distiller.py`
- Create: `zhihu_fiction/fiction/skills_store.py`

- [x] **Step 1: Add the package namespace**

Create `zhihu_fiction.fiction` with explicit submodule names in `__all__`.

- [x] **Step 2: Re-export agent entrypoints**

Expose `create_coordinator` and `ReviewerAgent` from `zhihu_fiction.agents`.

- [x] **Step 3: Re-export orchestration entrypoints**

Expose `run_coordinator`, `WorkflowResult`, and `StageResult` from `zhihu_fiction.orchestrator`.

- [x] **Step 4: Re-export pipeline entrypoints**

Expose `Pipeline`, `RunResult`, `StageRecord`, and `select_topic` from `zhihu_fiction.pipeline`.

- [x] **Step 5: Re-export scraper entrypoints**

Expose hot-topic scraping, search, manual entry, persistence, and file-loading helpers from `zhihu_fiction.scraper`.

- [x] **Step 6: Re-export distillation and skill store entrypoints**

Expose `Distiller`, `distill_single`, `distill_aggregate`, and `SkillsStore`.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests and release checks.

- [x] **Step 1: Verify focused tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py zhihu_fiction/tests/test_core_imports.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 2: Verify release checks pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected:

```text
9 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase implements only the Phase 3 namespace from the architecture cleanup design and does not move implementation bodies or alter public behavior.

- [x] **Step 2: Quality review**

Check explicit `__all__`, small import-only modules, no new external API calls, no import cycles beyond existing legacy imports, and no runtime data staging.

- [x] **Step 3: Git hygiene review**

Stage only the new fiction namespace, focused test, and this plan. Do not stage `data/auth`, output files, or nested MCP repository changes.

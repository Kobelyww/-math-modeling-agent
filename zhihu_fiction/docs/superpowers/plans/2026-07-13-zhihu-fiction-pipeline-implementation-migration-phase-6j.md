# Zhihu Fiction Pipeline Implementation Migration Phase 6J Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fiction pipeline implementation into `zhihu_fiction.fiction.pipeline`.

**Architecture:** This phase continues the fiction-domain implementation migration. `zhihu_fiction.fiction.pipeline` becomes the source of truth for topic selection, moderation, run records, scheduling, checkpoint resume, IP memory extraction hooks, and the `Pipeline` class. `zhihu_fiction.pipeline` remains a compatibility shim for existing web runtime, CLI, tests, and external imports.

**Tech Stack:** Python, LangChain messages, pytest, compatibility shims.

---

### Task 1: Lock Pipeline Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `Pipeline`, `RunResult`, `StageRecord`, and `select_topic` are available from both old and new paths, but their implementation module is `zhihu_fiction.fiction.pipeline`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.pipeline' == 'zhihu_fiction.fiction.pipeline'
```

### Task 2: Move Pipeline Implementation

**Files:**
- Modify: `zhihu_fiction/fiction/pipeline.py`
- Modify: `zhihu_fiction/pipeline.py`

- [x] **Step 1: Move pipeline implementation to `fiction/pipeline.py`**

Move topic selection, run result records, moderation helper, pipeline scheduling, checkpointing, story saving, and IP memory hooks into the fiction namespace.

- [x] **Step 2: Use migrated dependencies**

Import configuration and content normalization from `zhihu_fiction.core`, scraper and distiller from `zhihu_fiction.fiction`, and pipeline storage from `zhihu_fiction.storage`.

- [x] **Step 3: Convert legacy `pipeline.py` into a shim**

Re-export pipeline public constants, protocols, dataclasses, helpers, and `Pipeline` from the legacy module so existing imports keep working.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify fiction import test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected:

```text
1 passed
```

- [x] **Step 2: Verify pipeline-adjacent behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_cli_drama.py zhihu_fiction/tests/test_server_app_factory.py -q
```

Expected: all selected tests pass.

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only the fiction pipeline under the approved architecture design and does not change run directories, checkpoint formats, story output files, CLI commands, or web routes.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, migrated dependencies point to `core`/`fiction`/`storage`, public exports remain explicit, and runtime output/auth data are not staged.

- [x] **Step 3: Git hygiene review**

Stage only the pipeline migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

# Zhihu Fiction Pipeline Storage Implementation Migration Phase 6D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move pipeline run storage implementation into `zhihu_fiction.storage.pipeline_storage`.

**Architecture:** This phase continues the gradual implementation migration under the approved architecture cleanup design. `zhihu_fiction.storage.pipeline_storage` becomes the source of truth for `PipelineStorage`, while `zhihu_fiction.pipeline_storage` remains a compatibility shim for existing imports.

**Tech Stack:** Python file IO, JSON/JSONL persistence, pytest, compatibility shims.

---

### Task 1: Lock Pipeline Storage Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_integration_storage_imports.py`

- [x] **Step 1: Add failing ownership assertion**

Assert that `PipelineStorage` is available from both old and new paths, but its implementation module is `zhihu_fiction.storage.pipeline_storage`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_integration_storage_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.pipeline_storage' == 'zhihu_fiction.storage.pipeline_storage'
```

### Task 2: Move Pipeline Storage Implementation

**Files:**
- Modify: `zhihu_fiction/storage/pipeline_storage.py`
- Modify: `zhihu_fiction/pipeline_storage.py`

- [x] **Step 1: Move `PipelineStorage` to `storage/pipeline_storage.py`**

Move JSONL run history, schedule, and checkpoint persistence into the storage namespace.

- [x] **Step 2: Convert legacy `pipeline_storage.py` into a shim**

Re-export `PipelineStorage` from the legacy module so existing imports keep working.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify storage import test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_integration_storage_imports.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 2: Verify pipeline storage behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_pipeline_storage.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_pipeline_routes.py -q
```

Expected:

```text
11 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only pipeline persistence implementation under the approved architecture design and does not change file formats, paths, API routes, or runtime data.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, JSON parsing behavior remains identical, checkpoint behavior remains identical, and no runtime data is staged.

- [x] **Step 3: Git hygiene review**

Stage only the storage migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

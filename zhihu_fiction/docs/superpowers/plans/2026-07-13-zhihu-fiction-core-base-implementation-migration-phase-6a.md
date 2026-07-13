# Zhihu Fiction Core Base Implementation Migration Phase 6A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the first low-risk implementation body into the new `zhihu_fiction.core` namespace.

**Architecture:** Full `src/` layout switching is deferred because the repository root `pyproject.toml` still represents the wider LLM-Study workspace. This phase starts the real migration by making `zhihu_fiction.core.base` the source of truth for shared content helpers while keeping `zhihu_fiction.base` as a compatibility shim.

**Tech Stack:** Python modules, pytest, compatibility shims.

---

### Task 1: Lock Core Base Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_core_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `normalize_content` and `extract_story_body` are still available from both old and new paths, but their implementation module is `zhihu_fiction.core.base`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.base' == 'zhihu_fiction.core.base'
```

### Task 2: Move Shared Helper Implementation

**Files:**
- Modify: `zhihu_fiction/core/base.py`
- Modify: `zhihu_fiction/base.py`

- [x] **Step 1: Move helper bodies to `core/base.py`**

Move `normalize_content` and `extract_story_body` into `zhihu_fiction.core.base`.

- [x] **Step 2: Convert legacy `base.py` into a shim**

Re-export the same helpers from `zhihu_fiction.base` so existing imports keep working.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify core ownership test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py -q
```

Expected:

```text
1 passed
```

- [x] **Step 2: Verify dependent behavior still passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_story_library.py zhihu_fiction/tests/test_pipeline.py -q
```

Expected:

```text
8 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase starts the implementation migration under the approved architecture design without performing the full `src/` layout switch.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, the new module has no new dependencies, and behavior remains identical.

- [x] **Step 3: Git hygiene review**

Stage only the base migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

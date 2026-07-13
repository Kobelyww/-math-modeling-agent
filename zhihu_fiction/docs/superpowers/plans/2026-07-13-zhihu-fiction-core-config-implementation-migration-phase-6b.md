# Zhihu Fiction Core Config Implementation Migration Phase 6B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move application configuration implementation into `zhihu_fiction.core.config`.

**Architecture:** This phase continues the gradual implementation migration started in Phase 6A. `zhihu_fiction.core.config` becomes the source of truth for settings dataclasses, model aliases, `APP_ROOT`, and environment loading while `zhihu_fiction.config` remains a compatibility shim.

**Tech Stack:** Python dataclasses, python-dotenv, pytest, compatibility shims.

---

### Task 1: Lock Core Config Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_core_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `AgentConfig`, `Settings`, and `load_settings` are still available from both old and new paths, but their implementation module is `zhihu_fiction.core.config`.

- [x] **Step 2: Guard `APP_ROOT` behavior**

Assert that `APP_ROOT.name == "zhihu_fiction"` so moving the implementation into `core/` does not shift runtime paths into `zhihu_fiction/core/`.

- [x] **Step 3: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.config' == 'zhihu_fiction.core.config'
```

### Task 2: Move Config Implementation

**Files:**
- Modify: `zhihu_fiction/core/config.py`
- Modify: `zhihu_fiction/config.py`

- [x] **Step 1: Move settings implementation to `core/config.py`**

Move `APP_ROOT`, `MODEL_ALIASES`, `AgentConfig`, `Settings`, and `load_settings` into `zhihu_fiction.core.config`.

- [x] **Step 2: Preserve package root path**

Define `APP_ROOT = Path(__file__).resolve().parents[1]` in `core/config.py` so runtime data still resolves under `zhihu_fiction/`.

- [x] **Step 3: Convert legacy `config.py` into a shim**

Re-export the same public objects from `zhihu_fiction.config`.

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

- [x] **Step 2: Verify settings and app factory checks pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_settings.py zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected:

```text
28 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only configuration implementation under the approved architecture design and does not change environment variable names, runtime paths, API routes, or CLI commands.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, `APP_ROOT` remains stable, no new dependencies are added, and behavior remains identical.

- [x] **Step 3: Git hygiene review**

Stage only the config migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

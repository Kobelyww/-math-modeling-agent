# Zhihu Fiction Web Boundary Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the `zhihu_fiction.web` namespace for the FastAPI application layer without breaking the existing `zhihu_fiction.app` implementation.

**Architecture:** This phase creates compatibility exports and module aliases for the current Web layer. The existing `app/` implementation remains the source of truth while `web/` becomes the target namespace for future route and runtime-service migration.

**Tech Stack:** Python packages, importlib module aliases, pytest, FastAPI compatibility shims.

---

### Task 1: Lock Web Namespace Compatibility

**Files:**
- Create: `zhihu_fiction/tests/test_web_imports.py`

- [x] **Step 1: Add failing top-level Web import tests**

Assert that `zhihu_fiction.web.factory`, `dependencies`, `settings`, `security`, `sse`, `state`, and `request_parsing` expose the same public objects as `zhihu_fiction.app`.

- [x] **Step 2: Add failing route module import tests**

Assert that `zhihu_fiction.web.routes.<name>` imports resolve to the current `zhihu_fiction.app.routes.<name>` modules and expose the same `router` objects.

- [x] **Step 3: Add failing service module import tests**

Assert that `zhihu_fiction.web.services.<name>` imports resolve to the current `zhihu_fiction.app.services.<name>` modules.

- [x] **Step 4: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_web_imports.py -q
```

Expected initial failure:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.web'
```

### Task 2: Add Web Compatibility Namespace

**Files:**
- Create: `zhihu_fiction/web/__init__.py`
- Create: `zhihu_fiction/web/dependencies.py`
- Create: `zhihu_fiction/web/drama_video_stages.py`
- Create: `zhihu_fiction/web/factory.py`
- Create: `zhihu_fiction/web/legacy_compat.py`
- Create: `zhihu_fiction/web/request_parsing.py`
- Create: `zhihu_fiction/web/security.py`
- Create: `zhihu_fiction/web/settings.py`
- Create: `zhihu_fiction/web/sse.py`
- Create: `zhihu_fiction/web/state.py`
- Create: `zhihu_fiction/web/routes/__init__.py`
- Create: `zhihu_fiction/web/services/__init__.py`

- [x] **Step 1: Add explicit top-level re-export modules**

Expose the Web app factory, dependencies, settings, security, SSE, state, parsing, stage helpers and legacy compatibility helpers from the current `zhihu_fiction.app` modules.

- [x] **Step 2: Add route module aliases**

Register `zhihu_fiction.web.routes.<name>` aliases for each current `zhihu_fiction.app.routes.<name>` module.

- [x] **Step 3: Add service module aliases**

Register `zhihu_fiction.web.services.<name>` aliases for each current `zhihu_fiction.app.services.<name>` module.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests and release checks.

- [x] **Step 1: Verify focused tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_web_imports.py zhihu_fiction/tests/test_core_imports.py zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected:

```text
5 passed
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

Confirm this phase implements only the Phase 4 Web boundary namespace from the architecture cleanup design and does not move route implementations or change public API paths.

- [x] **Step 2: Quality review**

Check explicit `__all__`, small compatibility modules, no new HTTP behavior, no new external calls, and no source of truth split beyond module aliases.

- [x] **Step 3: Git hygiene review**

Stage only the new Web namespace, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

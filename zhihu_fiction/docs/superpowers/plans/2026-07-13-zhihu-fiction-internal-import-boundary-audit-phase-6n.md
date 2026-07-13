# Zhihu Fiction Internal Import Boundary Audit Phase 6N Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move internal production imports away from legacy root compatibility modules.

**Architecture:** Earlier phases moved implementations into `zhihu_fiction.core`, `zhihu_fiction.fiction`, and `zhihu_fiction.storage`, while root modules remain compatibility aliases for external callers. This phase enforces the boundary: production code inside `zhihu_fiction` should import real namespaces directly. Legacy root modules remain available, but only as compatibility surfaces.

**Tech Stack:** Python AST import scanning, pytest, namespace refactor.

---

### Task 1: Lock Internal Import Boundary

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing static import test**

Scan production Python files under `zhihu_fiction`, excluding tests and legacy alias modules, and fail if they import migrated legacy root modules:

- `zhihu_fiction.base`
- `zhihu_fiction.config`
- `zhihu_fiction.llm`
- `zhihu_fiction.agents`
- `zhihu_fiction.distiller`
- `zhihu_fiction.orchestrator`
- `zhihu_fiction.pipeline`
- `zhihu_fiction.pipeline_storage`
- `zhihu_fiction.scraper`
- `zhihu_fiction.skills_store`
- `zhihu_fiction.tools`

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py::test_internal_code_imports_real_namespaces_not_legacy_root_modules -q
```

Expected initial failure: production files still import legacy root modules.

### Task 2: Migrate Internal Consumers

**Files:**
- Modify: `zhihu_fiction/__init__.py`
- Modify: `zhihu_fiction/server.py`
- Modify: `zhihu_fiction/cli.py`
- Modify: `zhihu_fiction/exporter.py`
- Modify: `zhihu_fiction/automator.py`
- Modify: `zhihu_fiction/automator_zhihu.py`
- Modify: `zhihu_fiction/drama/assets.py`
- Modify: `zhihu_fiction/drama/exporter.py`
- Modify: `zhihu_fiction/workspace/repositories.py`
- Modify: `zhihu_fiction/workspace/queue.py`
- Modify: `zhihu_fiction/workspace/services.py`
- Modify: `zhihu_fiction/app/dependencies.py`
- Modify: `zhihu_fiction/app/routes/ip_memory.py`
- Modify: `zhihu_fiction/app/routes/static.py`
- Modify: `zhihu_fiction/app/services/pipeline_runtime.py`
- Modify: `zhihu_fiction/app/services/story_library.py`
- Modify: `zhihu_fiction/app/services/drama_video_stage_generation.py`
- Modify: `zhihu_fiction/app/services/drama_video_runtime.py`
- Modify: `zhihu_fiction/app/services/drama_video_execution.py`

- [x] **Step 1: Route core imports to `zhihu_fiction.core`**

Move `APP_ROOT`, settings, LLM construction, and content helpers to `core.config`, `core.llm`, and `core.base`.

- [x] **Step 2: Route fiction imports to `zhihu_fiction.fiction`**

Move pipeline, orchestrator, distiller, scraper, and skills-store consumers to `fiction.*`.

- [x] **Step 3: Route storage imports to `zhihu_fiction.storage`**

Move pipeline runtime storage imports to `storage.pipeline_storage`.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify static import boundary passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py::test_internal_code_imports_real_namespaces_not_legacy_root_modules -q
```

Expected:

```text
1 passed
```

- [x] **Step 2: Verify fiction import tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected:

```text
3 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase changes only internal import boundaries and the static test; it does not change prompts, routes, persisted formats, or business logic.

- [x] **Step 2: Quality review**

Check that legacy root modules remain available for external compatibility, internal production imports use real namespaces, and no runtime data or secrets are staged.

- [x] **Step 3: Git hygiene review**

Stage only import-boundary files, the focused test, and this plan. Do not stage runtime data, auth files, or nested MCP repository changes.

# Zhihu Fiction Integration Storage Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `zhihu_fiction.integrations` and `zhihu_fiction.storage` namespaces without moving implementation bodies.

**Architecture:** This phase creates compatibility modules for external providers and persistence adapters. Browser publishing, Zhihu publishing and Bailian video generation remain implemented in their legacy modules, while the new namespaces provide stable target paths for future provider/storage extraction.

**Tech Stack:** Python packages, pytest, compatibility re-exports.

---

### Task 1: Lock Integration and Storage Import Contracts

**Files:**
- Create: `zhihu_fiction/tests/test_integration_storage_imports.py`

- [x] **Step 1: Add failing integration import tests**

Assert that `zhihu_fiction.integrations.browser_automation`, `zhihu_browser`, and `bailian_video` expose the existing browser automation, Zhihu publishing, and Bailian video provider objects.

- [x] **Step 2: Add failing storage import tests**

Assert that `zhihu_fiction.storage.pipeline_storage` and `object_storage` expose the existing pipeline and object storage adapters.

- [x] **Step 3: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_integration_storage_imports.py -q
```

Expected initial failure:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.integrations'
ModuleNotFoundError: No module named 'zhihu_fiction.storage'
```

### Task 2: Add Integration Compatibility Namespace

**Files:**
- Create: `zhihu_fiction/integrations/__init__.py`
- Create: `zhihu_fiction/integrations/browser_automation.py`
- Create: `zhihu_fiction/integrations/zhihu_browser.py`
- Create: `zhihu_fiction/integrations/bailian_video.py`

- [x] **Step 1: Add the package namespace**

Create `zhihu_fiction.integrations` with explicit submodule names in `__all__`.

- [x] **Step 2: Re-export browser automation**

Expose `Automator`, `AutomatorError`, and `LoginTimeout` from `zhihu_fiction.automator`.

- [x] **Step 3: Re-export Zhihu publishing automation**

Expose `ZhihuPublisher`, `PublishError`, and `LoginRequired` from `zhihu_fiction.automator_zhihu`.

- [x] **Step 4: Re-export Bailian video provider**

Expose `BailianVideoProvider`, config, job types, provider factory and config loader from `zhihu_fiction.drama.video`.

### Task 3: Add Storage Compatibility Namespace

**Files:**
- Create: `zhihu_fiction/storage/__init__.py`
- Create: `zhihu_fiction/storage/pipeline_storage.py`
- Create: `zhihu_fiction/storage/object_storage.py`

- [x] **Step 1: Add the package namespace**

Create `zhihu_fiction.storage` with explicit submodule names in `__all__`.

- [x] **Step 2: Re-export pipeline storage**

Expose `PipelineStorage` from `zhihu_fiction.pipeline_storage`.

- [x] **Step 3: Re-export object storage adapters**

Expose `LocalObjectStorage`, `MinioObjectStorage`, and `create_object_storage` from `zhihu_fiction.app.services.object_storage`.

### Task 4: Verify Compatibility

**Files:**
- Read-only verification over tests and release checks.

- [x] **Step 1: Verify focused tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_integration_storage_imports.py zhihu_fiction/tests/test_core_imports.py zhihu_fiction/tests/test_fiction_imports.py zhihu_fiction/tests/test_web_imports.py -q
```

Expected:

```text
7 passed
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

### Task 5: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase implements only the Phase 5 integration/storage namespace from the architecture cleanup design and does not move provider or storage implementation bodies.

- [x] **Step 2: Quality review**

Check explicit `__all__`, small compatibility modules, no new external API calls, no local cookie reads during import, and no runtime data staging.

- [x] **Step 3: Git hygiene review**

Stage only the new namespaces, focused test, and this plan. Do not stage `data/auth`, output files, or nested MCP repository changes.

# Zhihu Fiction Core Extraction Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the `zhihu_fiction.core` namespace without breaking existing imports.

**Architecture:** This phase creates compatibility re-export modules for shared configuration, LLM construction, content helpers and standalone tools. It does not move implementation bodies yet, because downstream modules still import the legacy root paths.

**Tech Stack:** Python packages, pytest, compatibility shims.

---

### Task 1: Lock the New Core Import Contract

**Files:**
- Create: `zhihu_fiction/tests/test_core_imports.py`

- [x] **Step 1: Add a failing import compatibility test**

Assert that `zhihu_fiction.core.config`, `zhihu_fiction.core.llm`, `zhihu_fiction.core.base`, and `zhihu_fiction.core.tools` expose the same public objects as the legacy root modules.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py -q
```

Expected initial failure:

```text
ModuleNotFoundError: No module named 'zhihu_fiction.core'
```

### Task 2: Add Core Compatibility Namespace

**Files:**
- Create: `zhihu_fiction/core/__init__.py`
- Create: `zhihu_fiction/core/config.py`
- Create: `zhihu_fiction/core/llm.py`
- Create: `zhihu_fiction/core/base.py`
- Create: `zhihu_fiction/core/tools.py`

- [x] **Step 1: Add the package namespace**

Create `zhihu_fiction.core` and list the compatibility modules in `__all__`.

- [x] **Step 2: Re-export shared configuration**

Expose `APP_ROOT`, `MODEL_ALIASES`, `AgentConfig`, `Settings`, and `load_settings` from the legacy `zhihu_fiction.config` module.

- [x] **Step 3: Re-export LLM construction**

Expose `create_llm` from the legacy `zhihu_fiction.llm` module.

- [x] **Step 4: Re-export shared content helpers**

Expose `normalize_content` and `extract_story_body` from the legacy `zhihu_fiction.base` module.

- [x] **Step 5: Re-export standalone tools**

Expose the existing standalone LangChain tool objects from the legacy `zhihu_fiction.tools` module.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests and release checks.

- [x] **Step 1: Verify the focused test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py -q
```

Expected:

```text
1 passed
```

- [x] **Step 2: Verify release artifact checks still pass**

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

Confirm this phase implements only the Phase 2 compatibility namespace from the architecture cleanup design and does not move source files or change external behavior.

- [x] **Step 2: Quality review**

Check that modules are small, import-only, explicit in `__all__`, and do not introduce new runtime side effects beyond the legacy modules they re-export.

- [x] **Step 3: Git hygiene review**

Stage only the new core modules, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

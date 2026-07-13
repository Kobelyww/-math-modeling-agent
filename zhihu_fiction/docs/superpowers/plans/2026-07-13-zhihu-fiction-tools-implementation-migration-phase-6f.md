# Zhihu Fiction Tools Implementation Migration Phase 6F Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fiction workflow LangChain tools into `zhihu_fiction.fiction.tools`.

**Architecture:** The original architecture draft listed `tools.py` under `core`, but the implementation depends on scraping and skill storage, so its real boundary is the fiction domain. This phase makes `zhihu_fiction.fiction.tools` the source of truth while keeping `zhihu_fiction.tools` and `zhihu_fiction.core.tools` as compatibility exports.

**Tech Stack:** Python, LangChain tool decorators, pytest, compatibility shims.

---

### Task 1: Lock Fiction Tools Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`
- Modify: `zhihu_fiction/tests/test_core_imports.py`

- [x] **Step 1: Add failing fiction namespace assertions**

Assert that `zhihu_fiction.fiction.tools` is importable and exposes the same tool objects as the legacy `zhihu_fiction.tools` module.

- [x] **Step 2: Add failing implementation ownership assertions**

Assert that the underlying decorated tool functions for `save_article` and `scrape_hot` come from `zhihu_fiction.fiction.tools`.

- [x] **Step 3: Run tests and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py zhihu_fiction/tests/test_core_imports.py -q
```

Expected initial failures:

```text
ImportError: cannot import name 'tools' from 'zhihu_fiction.fiction'
AssertionError: assert 'zhihu_fiction.tools' == 'zhihu_fiction.fiction.tools'
```

### Task 2: Move Tools Implementation

**Files:**
- Create: `zhihu_fiction/fiction/tools.py`
- Modify: `zhihu_fiction/fiction/__init__.py`
- Modify: `zhihu_fiction/tools.py`
- Modify: `zhihu_fiction/core/tools.py`

- [x] **Step 1: Move standalone tool definitions to `fiction/tools.py`**

Move scraping, skill reading, article saving, and current-time LangChain tools into the fiction namespace.

- [x] **Step 2: Update fiction package exports**

Add `tools` to `zhihu_fiction.fiction.__all__`.

- [x] **Step 3: Convert legacy `tools.py` into a shim**

Re-export the same public objects from `zhihu_fiction.tools`.

- [x] **Step 4: Keep `core.tools` as compatibility only**

Re-export from `zhihu_fiction.fiction.tools` so existing `zhihu_fiction.core.tools` imports keep working without making `core` the implementation owner.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify namespace tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py zhihu_fiction/tests/test_core_imports.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 2: Verify fiction workflow tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agents.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_cli_drama.py -q
```

Expected:

```text
16 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase intentionally places tool implementation in the fiction domain because the tool module depends on scraper and skill-store behavior.

- [x] **Step 2: Quality review**

Check that old modules are small compatibility shims, decorated LangChain tool identities remain stable, runtime paths still use `APP_ROOT / "output"`, and no runtime data is staged.

- [x] **Step 3: Git hygiene review**

Stage only the tools migration files, focused tests, and this plan. Do not stage runtime data or nested MCP repository changes.

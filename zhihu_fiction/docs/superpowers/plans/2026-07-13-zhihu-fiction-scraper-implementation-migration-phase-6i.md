# Zhihu Fiction Scraper Implementation Migration Phase 6I Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Zhihu scraping implementation into `zhihu_fiction.fiction.scraper`.

**Architecture:** This phase continues the fiction-domain implementation migration. `zhihu_fiction.fiction.scraper` becomes the source of truth for Zhihu hot-list scraping, topic search, answer fetching, scraped file storage helpers, and manual entry. `zhihu_fiction.scraper` remains a compatibility shim for existing CLI, pipeline, and external imports.

**Tech Stack:** Python, requests, BeautifulSoup, pytest, compatibility shims.

---

### Task 1: Lock Scraper Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that scraper functions are available from both old and new paths, but their implementation module is `zhihu_fiction.fiction.scraper`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.scraper' == 'zhihu_fiction.fiction.scraper'
```

### Task 2: Move Scraper Implementation

**Files:**
- Modify: `zhihu_fiction/fiction/scraper.py`
- Modify: `zhihu_fiction/scraper.py`

- [x] **Step 1: Move scraping implementation to `fiction/scraper.py`**

Move API request helpers, cache helpers, hot-list parsing, topic search, answer fetching, scraped file helpers, and manual entry into the fiction namespace.

- [x] **Step 2: Use migrated dependencies**

Import `APP_ROOT` from `zhihu_fiction.core.config`.

- [x] **Step 3: Convert legacy `scraper.py` into a shim**

Re-export scraper public constants and functions from the legacy module so existing imports keep working.

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

- [x] **Step 2: Verify scraper-adjacent behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agents.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_cli_drama.py zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: all selected tests pass.

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only Zhihu scraping under the approved architecture design and does not change cache directories, output formats, CLI commands, or pipeline behavior.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, migrated dependencies point to `core`, public exports remain explicit, and no runtime scraped/auth data are staged.

- [x] **Step 3: Git hygiene review**

Stage only the scraper migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

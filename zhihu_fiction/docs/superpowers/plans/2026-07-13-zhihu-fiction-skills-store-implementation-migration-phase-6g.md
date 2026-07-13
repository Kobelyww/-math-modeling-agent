# Zhihu Fiction Skills Store Implementation Migration Phase 6G Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fiction skill-card storage implementation into `zhihu_fiction.fiction.skills_store`.

**Architecture:** This phase continues the fiction-domain implementation migration. `zhihu_fiction.fiction.skills_store` becomes the source of truth for `SkillsStore`, while `zhihu_fiction.skills_store` remains a compatibility shim for existing imports.

**Tech Stack:** Python file IO, Markdown skill cards, pytest, compatibility shims.

---

### Task 1: Lock Skills Store Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing ownership assertion**

Assert that `SkillsStore` is available from both old and new paths, but its implementation module is `zhihu_fiction.fiction.skills_store`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.skills_store' == 'zhihu_fiction.fiction.skills_store'
```

### Task 2: Move Skills Store Implementation

**Files:**
- Modify: `zhihu_fiction/fiction/skills_store.py`
- Modify: `zhihu_fiction/skills_store.py`

- [x] **Step 1: Move `SkillsStore` to `fiction/skills_store.py`**

Move skill listing, reading, searching, saving, deleting, summarizing and agent-context generation into the fiction namespace.

- [x] **Step 2: Preserve default skills directory**

Keep `SKILLS_DIR = APP_ROOT / "data" / "skills"` so existing runtime paths stay unchanged.

- [x] **Step 3: Convert legacy `skills_store.py` into a shim**

Re-export `SKILLS_DIR` and `SkillsStore` from the legacy module so existing imports keep working.

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

- [x] **Step 2: Verify skill-store-adjacent behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agents.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_server_app_factory.py -q
```

Expected:

```text
27 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only skill-card storage under the approved architecture design and does not change file formats, runtime directories, API routes, or CLI commands.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, `SKILLS_DIR` remains stable, fuzzy matching behavior remains identical, and no runtime skill-card files are staged.

- [x] **Step 3: Git hygiene review**

Stage only the skills-store migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

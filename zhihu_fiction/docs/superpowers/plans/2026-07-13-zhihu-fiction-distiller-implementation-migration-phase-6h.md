# Zhihu Fiction Distiller Implementation Migration Phase 6H Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fiction skill distillation implementation into `zhihu_fiction.fiction.distiller`.

**Architecture:** This phase continues the fiction-domain implementation migration. `zhihu_fiction.fiction.distiller` becomes the source of truth for prompt constants, `distill_single`, `distill_aggregate`, and `Distiller`, while `zhihu_fiction.distiller` remains a compatibility shim for existing imports.

**Tech Stack:** Python, LangChain chat models, Markdown skill cards, pytest, compatibility shims.

---

### Task 1: Lock Distiller Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `Distiller`, `distill_single`, and `distill_aggregate` are available from both old and new paths, but their implementation module is `zhihu_fiction.fiction.distiller`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.distiller' == 'zhihu_fiction.fiction.distiller'
```

### Task 2: Move Distiller Implementation

**Files:**
- Modify: `zhihu_fiction/fiction/distiller.py`
- Modify: `zhihu_fiction/distiller.py`

- [x] **Step 1: Move distillation implementation to `fiction/distiller.py`**

Move prompt constants, JSON parsing helpers, feature distillation, aggregate card generation, and the `Distiller` class into the fiction namespace.

- [x] **Step 2: Use migrated dependencies**

Import settings and LLM construction from `zhihu_fiction.core`, and import `SkillsStore` from `zhihu_fiction.fiction.skills_store`.

- [x] **Step 3: Convert legacy `distiller.py` into a shim**

Re-export distiller public objects from the legacy module so existing imports keep working.

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

- [x] **Step 2: Verify distiller-adjacent behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agents.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_cli_drama.py zhihu_fiction/tests/test_server_app_factory.py -q
```

Expected:

```text
32 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only skill distillation under the approved architecture design and does not change prompt content, output formats, runtime directories, API routes, or CLI commands.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, migrated dependencies point to `core`/`fiction`, LLM content normalization remains equivalent, and no runtime skill-card files are staged.

- [x] **Step 3: Git hygiene review**

Stage only the distiller migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

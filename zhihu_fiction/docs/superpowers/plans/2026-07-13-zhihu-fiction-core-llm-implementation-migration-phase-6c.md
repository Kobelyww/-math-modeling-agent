# Zhihu Fiction Core LLM Implementation Migration Phase 6C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move LLM construction implementation into `zhihu_fiction.core.llm`.

**Architecture:** This phase continues the gradual implementation migration under the approved architecture cleanup design. `zhihu_fiction.core.llm` becomes the source of truth for `create_llm`, while `zhihu_fiction.llm` remains a compatibility shim for existing imports.

**Tech Stack:** Python, LangChain DeepSeek adapter, pytest, compatibility shims.

---

### Task 1: Lock Core LLM Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_core_imports.py`

- [x] **Step 1: Add failing ownership assertion**

Assert that `create_llm` is available from both old and new paths, but its implementation module is `zhihu_fiction.core.llm`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.llm' == 'zhihu_fiction.core.llm'
```

### Task 2: Move LLM Implementation

**Files:**
- Modify: `zhihu_fiction/core/llm.py`
- Modify: `zhihu_fiction/llm.py`

- [x] **Step 1: Move `create_llm` to `core/llm.py`**

Move the `ChatDeepSeek` construction logic into `zhihu_fiction.core.llm`.

- [x] **Step 2: Import settings from core config**

Use `zhihu_fiction.core.config.Settings` as the type source.

- [x] **Step 3: Convert legacy `llm.py` into a shim**

Re-export `create_llm` from `zhihu_fiction.llm` so existing imports keep working.

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

- [x] **Step 2: Verify LLM-adjacent app tests pass**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_app_settings.py zhihu_fiction/tests/test_pipeline.py -q
```

Expected:

```text
23 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only LLM construction under the approved architecture design and does not change model settings, API key behavior, or public imports.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, missing API key behavior stays identical, no new dependencies are added, and no external API call happens during import.

- [x] **Step 3: Git hygiene review**

Stage only the LLM migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

# Zhihu Fiction Agents Implementation Migration Phase 6L Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fiction agent orchestration implementation into `zhihu_fiction.fiction.agents`.

**Architecture:** This phase completes the fiction-domain implementation migration for the novel generation main chain. `zhihu_fiction.fiction.agents` becomes the source of truth for prompt constants, tool factories, DeepAgent middleware, novel coordinator creation, drama-video coordinator creation, and `ReviewerAgent`. `zhihu_fiction.agents` remains a compatibility alias for existing tests, CLI, web services, and external imports.

**Tech Stack:** Python, LangChain tools/messages, DeepAgent middleware, pytest, module alias compatibility.

---

### Task 1: Lock Agents Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `create_coordinator`, `create_drama_video_coordinator`, `ReviewerAgent`, and test-visible tool factories are available from both old and new paths, but their implementation module is `zhihu_fiction.fiction.agents`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.agents' == 'zhihu_fiction.fiction.agents'
```

### Task 2: Move Agents Implementation

**Files:**
- Modify: `zhihu_fiction/fiction/agents.py`
- Modify: `zhihu_fiction/agents.py`

- [x] **Step 1: Move agent implementation to `fiction/agents.py`**

Move prompt constants, tool factories, stage-gate middleware, final-output middleware, novel coordinator factory, drama-video coordinator factory, and `ReviewerAgent` into the fiction namespace.

- [x] **Step 2: Use migrated dependencies**

Import normalization from `zhihu_fiction.core`, skill storage from `zhihu_fiction.fiction`, and moderation from `zhihu_fiction.fiction.pipeline`.

- [x] **Step 3: Convert legacy `agents.py` into a module alias**

Alias `zhihu_fiction.agents` to `zhihu_fiction.fiction.agents` so old imports and monkeypatch-style compatibility continue to target the real implementation module.

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

- [x] **Step 2: Verify agents and main-chain behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_agents.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_pipeline_ip_memory.py zhihu_fiction/tests/test_cli_drama.py zhihu_fiction/tests/test_drama_video_ip_memory_integration.py zhihu_fiction/tests/test_server_app_factory.py -q
```

Expected: all selected tests pass.

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only agent implementation under the approved architecture design and does not change prompt text, tool names, middleware state machine semantics, route behavior, CLI commands, or persisted formats.

- [x] **Step 2: Quality review**

Check that the old module is a compatibility alias, migrated dependencies point to `core`/`fiction`, private tool factories remain importable for existing tests, and runtime data are not staged.

- [x] **Step 3: Git hygiene review**

Stage only the agents migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

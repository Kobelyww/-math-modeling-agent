# Zhihu Fiction Orchestrator Implementation Migration Phase 6K Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move fiction workflow orchestration implementation into `zhihu_fiction.fiction.orchestrator`.

**Architecture:** This phase continues the fiction-domain implementation migration. `zhihu_fiction.fiction.orchestrator` becomes the source of truth for `WorkflowResult`, `StageResult`, Coordinator invocation, drama-video stage coordination, and CLI-compatible orchestration wrappers. `zhihu_fiction.orchestrator` remains a compatibility shim for existing CLI, web services, tests, and external imports.

**Tech Stack:** Python, DeepAgent/LangGraph coordinator invocations, pytest, compatibility shims.

---

### Task 1: Lock Orchestrator Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `run_coordinator`, `WorkflowResult`, and `StageResult` are available from both old and new paths, but their implementation module is `zhihu_fiction.fiction.orchestrator`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.orchestrator' == 'zhihu_fiction.fiction.orchestrator'
```

### Task 2: Move Orchestrator Implementation

**Files:**
- Modify: `zhihu_fiction/fiction/orchestrator.py`
- Modify: `zhihu_fiction/orchestrator.py`
- Modify: `zhihu_fiction/fiction/agents.py`

- [x] **Step 1: Move orchestration implementation to `fiction/orchestrator.py`**

Move workflow result records, Coordinator output parsing, novel Coordinator invocation, drama-video stage Coordinator invocation, `create_orchestrator`, and `OrchestratorCompat` into the fiction namespace.

- [x] **Step 2: Use migrated dependencies**

Import settings, LLM construction, and normalization from `zhihu_fiction.core`; import coordinator factories and skill store from `zhihu_fiction.fiction`.

- [x] **Step 3: Preserve drama-video coordinator compatibility**

Expose `create_drama_video_coordinator` through `zhihu_fiction.fiction.agents` so the migrated orchestrator can depend on the fiction namespace while old imports keep working.

- [x] **Step 4: Convert legacy `orchestrator.py` into a shim**

Re-export orchestration public objects from the legacy module so existing imports keep working.

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

- [x] **Step 2: Verify orchestrator-adjacent behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_pipeline_ip_memory.py zhihu_fiction/tests/test_cli_drama.py zhihu_fiction/tests/test_drama_video_ip_memory_integration.py zhihu_fiction/tests/test_server_app_factory.py -q
```

Expected: all selected tests pass.

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only workflow orchestration under the approved architecture design and does not change prompts, output parsing markers, API routes, CLI commands, or persisted formats.

- [x] **Step 2: Quality review**

Check that the old module is a small compatibility shim, migrated dependencies point to `core`/`fiction`, hidden compatibility exports are preserved, and runtime data are not staged.

- [x] **Step 3: Git hygiene review**

Stage only the orchestrator migration files, focused test, compatibility export, and this plan. Do not stage runtime data or nested MCP repository changes.

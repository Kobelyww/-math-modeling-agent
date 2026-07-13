# Zhihu Fiction Legacy Alias Compatibility Audit Phase 6M Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make migrated legacy root modules behave as aliases of their `zhihu_fiction.fiction` implementation modules.

**Architecture:** Earlier phases moved fiction-domain implementations from root modules into `zhihu_fiction.fiction`. This phase tightens compatibility so legacy imports such as `zhihu_fiction.scraper`, `zhihu_fiction.distiller`, and `zhihu_fiction.orchestrator` resolve to the same module objects as their implementation modules. That preserves monkeypatch-style tests, mutable module globals, and old integration code that imports modules rather than individual symbols.

**Tech Stack:** Python import system, `sys.modules` aliasing, pytest, compatibility shims.

---

### Task 1: Lock Legacy Alias Semantics

**Files:**
- Modify: `zhihu_fiction/tests/test_fiction_imports.py`

- [x] **Step 1: Add failing module identity assertions**

Assert that each migrated legacy module is the same module object as its fiction implementation module:

- `zhihu_fiction.agents`
- `zhihu_fiction.distiller`
- `zhihu_fiction.orchestrator`
- `zhihu_fiction.pipeline`
- `zhihu_fiction.scraper`
- `zhihu_fiction.skills_store`
- `zhihu_fiction.tools`

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert <module 'zhihu_fiction.distiller' ...> is <module 'zhihu_fiction.fiction.distiller' ...>
```

### Task 2: Convert Remaining Re-export Shims To Aliases

**Files:**
- Modify: `zhihu_fiction/distiller.py`
- Modify: `zhihu_fiction/orchestrator.py`
- Modify: `zhihu_fiction/scraper.py`
- Modify: `zhihu_fiction/skills_store.py`
- Modify: `zhihu_fiction/tools.py`

- [x] **Step 1: Replace re-export shims with `sys.modules` aliases**

Each legacy module imports its implementation module and assigns it to `sys.modules[__name__]`.

- [x] **Step 2: Preserve explicit import compatibility**

Existing `from zhihu_fiction.<module> import <symbol>` imports continue to work because the legacy module resolves to the implementation module.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify alias test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_fiction_imports.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 2: Verify architecture and main-chain behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_core_imports.py zhihu_fiction/tests/test_fiction_imports.py zhihu_fiction/tests/test_web_imports.py zhihu_fiction/tests/test_agents.py zhihu_fiction/tests/test_pipeline.py zhihu_fiction/tests/test_pipeline_ip_memory.py zhihu_fiction/tests/test_cli_drama.py zhihu_fiction/tests/test_drama_video_ip_memory_integration.py zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: all selected tests pass.

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase changes only legacy compatibility layers and tests; it does not move business logic, change prompts, routes, output formats, or persisted files.

- [x] **Step 2: Quality review**

Check that alias modules are minimal, import semantics are uniform across migrated root modules, and no runtime data or secrets are staged.

- [x] **Step 3: Git hygiene review**

Stage only legacy alias files, focused import test, and this plan. Do not stage runtime data, auth files, or nested MCP repository changes.

# Zhihu Fiction Runtime Secret Tracking Cleanup Phase 6P Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove tracked runtime authentication data from the main repository while preserving local developer state.

**Architecture:** Runtime authentication/session files belong under ignored local data directories, not source control. `.gitignore` already excludes `zhihu_fiction/data/auth/`, but `zhihu_fiction/data/auth/zhihu_session.json` was still tracked from an earlier state. This phase locks the release contract so auth/workspace/object/output runtime paths cannot remain tracked.

**Tech Stack:** Git index hygiene, pytest release contract checks.

---

### Task 1: Lock Runtime Data Tracking Rule

**Files:**
- Modify: `zhihu_fiction/tests/test_release_artifacts.py`

- [x] **Step 1: Add failing release test**

Assert that these runtime paths have no tracked files:

- `zhihu_fiction/data/auth`
- `zhihu_fiction/data/workspace`
- `zhihu_fiction/data/objects`
- `zhihu_fiction/output`

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py::test_runtime_secret_and_generated_paths_are_not_tracked -q
```

Expected initial failure:

```text
zhihu_fiction/data/auth/zhihu_session.json
```

### Task 2: Remove Auth Session From Git Tracking

**Files:**
- Remove from Git index only: `zhihu_fiction/data/auth/zhihu_session.json`

- [x] **Step 1: Remove the tracked auth session from the index**

Run:

```bash
git rm --cached zhihu_fiction/data/auth/zhihu_session.json
```

This preserves the local working-tree file because only Git tracking is removed.

- [x] **Step 2: Verify the local session file remains present**

Confirm `zhihu_fiction/data/auth/zhihu_session.json` still exists locally after index removal.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over release tests.

- [x] **Step 1: Verify runtime tracking test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py::test_runtime_secret_and_generated_paths_are_not_tracked -q
```

Expected:

```text
1 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase removes only runtime auth tracking and adds a release guard; it does not delete local auth state, change application code, or alter runtime behavior.

- [x] **Step 2: Quality review**

Check that `.gitignore` already excludes the runtime path, the test covers other generated runtime locations, and the local auth file remains present.

- [x] **Step 3: Git hygiene review**

Stage only the index removal, release artifact test, and this plan. Do not stage nested MCP repository changes.

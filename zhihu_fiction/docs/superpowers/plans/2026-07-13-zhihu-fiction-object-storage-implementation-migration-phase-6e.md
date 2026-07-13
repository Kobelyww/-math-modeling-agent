# Zhihu Fiction Object Storage Implementation Migration Phase 6E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move object storage implementation into `zhihu_fiction.storage.object_storage`.

**Architecture:** This phase continues the gradual implementation migration under the approved architecture cleanup design. `zhihu_fiction.storage.object_storage` becomes the source of truth for local and MinIO object storage adapters, while `zhihu_fiction.app.services.object_storage` remains a Web-layer compatibility shim.

**Tech Stack:** Python file IO, optional MinIO client adapter, pytest, compatibility shims.

---

### Task 1: Lock Object Storage Ownership

**Files:**
- Modify: `zhihu_fiction/tests/test_integration_storage_imports.py`

- [x] **Step 1: Add failing ownership assertions**

Assert that `LocalObjectStorage`, `MinioObjectStorage`, and `create_object_storage` are available from both old and new paths, but their implementation module is `zhihu_fiction.storage.object_storage`.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_integration_storage_imports.py -q
```

Expected initial failure:

```text
AssertionError: assert 'zhihu_fiction.app.services.object_storage' == 'zhihu_fiction.storage.object_storage'
```

### Task 2: Move Object Storage Implementation

**Files:**
- Modify: `zhihu_fiction/storage/object_storage.py`
- Modify: `zhihu_fiction/app/services/object_storage.py`

- [x] **Step 1: Move storage adapter bodies to `storage/object_storage.py`**

Move `LocalObjectStorage`, `MinioObjectStorage`, `create_object_storage`, and private key-cleaning logic into the storage namespace.

- [x] **Step 2: Convert Web service module into a shim**

Re-export object storage adapters from `zhihu_fiction.app.services.object_storage` so existing Web imports keep working.

### Task 3: Verify Compatibility

**Files:**
- Read-only verification over tests.

- [x] **Step 1: Verify storage import test passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_integration_storage_imports.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 2: Verify object storage behavior passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_object_storage.py zhihu_fiction/tests/test_drama_video_execution.py zhihu_fiction/tests/test_web_imports.py -q
```

Expected:

```text
26 passed
```

### Task 4: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase migrates only object storage implementation under the approved architecture design and does not change storage URI format, environment variable names, Web routes, or runtime data paths.

- [x] **Step 2: Quality review**

Check that the old Web service module is a small compatibility shim, local path traversal checks remain identical, MinIO construction behavior remains identical, and no runtime data is staged.

- [x] **Step 3: Git hygiene review**

Stage only the object storage migration files, focused test, and this plan. Do not stage runtime data or nested MCP repository changes.

# Zhihu Fiction Release Compose Contract Phase 6O Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate and commit the release Compose interpolation contract that was left as dirty release artifacts.

**Architecture:** This phase treats `zhihu_fiction/.env.production.example` as the documented default production-like Compose env file and `zhihu_fiction/tests/test_release_artifacts.py` as the release contract. The Dockerfile, Compose file, deployment docs, and env example already align on override knobs for local/staging recovery: Python image, web port, Redis port, MinIO ports, and the Compose env-file selector.

**Tech Stack:** Docker Compose contract checks, pytest, release documentation.

---

### Task 1: Audit Dirty Release Files

**Files:**
- Review: `zhihu_fiction/.env.production.example`
- Review: `zhihu_fiction/tests/test_release_artifacts.py`

- [x] **Step 1: Inspect current diff**

Confirm the dirty files add release interpolation defaults and contract tests for Docker/Compose recovery knobs.

- [x] **Step 2: Check for secrets**

Confirm the env example contains empty API keys and local default MinIO credentials only; no real API key, production token, or session file is included.

### Task 2: Verify Release Contract

**Files:**
- Read-only verification over existing release files.

- [x] **Step 1: Run release artifact tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected:

```text
9 passed
```

- [x] **Step 2: Confirm Compose/Docker/docs alignment**

Verify the tests pass against:

- `Dockerfile`
- `docker-compose.yml`
- `docs/release/DEPLOYMENT.md`
- `zhihu_fiction/.env.production.example`

### Task 3: Review

**Files:**
- Read-only verification over changed files.

- [x] **Step 1: Spec review**

Confirm this phase commits release configuration and tests only; it does not change application runtime behavior, prompts, API routes, or generated data.

- [x] **Step 2: Quality review**

Check that release override names are explicit, tests cover both static file content and `docker compose --env-file ... config`, and env values are examples rather than secrets.

- [x] **Step 3: Git hygiene review**

Stage only the env example, release artifact test, and this plan. Do not stage auth session data, nested MCP repository changes, or unrelated files.

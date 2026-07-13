# Zhihu Fiction Architecture Cleanup Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish `zhihu_fiction` architecture guardrails before moving source files.

**Architecture:** Phase 1 is a freeze-and-guard pass. It adds documentation for current and target structure, updates the README so users understand the architecture direction, and hardens ignore rules for runtime-only files without moving business code.

**Tech Stack:** Markdown, Git ignore rules, existing Python/FastAPI project layout.

---

### Task 1: Add Architecture Guide

**Files:**
- Create: `zhihu_fiction/docs/architecture.md`

- [x] **Step 1: Document current top-level responsibilities**

Write a guide that separates source modules, runtime data, generated output, tests, static assets, docs, and nested MCP service boundaries.

- [x] **Step 2: Document the target architecture**

Summarize the staged target modules: `core`, `fiction`, `drama`, `workspace`, `ip_memory`, `publishing`, `integrations`, `web`, and `storage`.

- [x] **Step 3: Document migration rules**

State that API paths, CLI commands, `uvicorn zhihu_fiction.server:app`, and compatibility shims must remain stable during migration.

### Task 2: Harden Runtime Ignore Rules

**Files:**
- Modify: `.gitignore`

- [x] **Step 1: Add MCP runtime-only directories**

Add ignore entries for local browser/cookie/search output under `zhihu_fiction/mcp_server` while keeping the nested repository boundary intact.

- [x] **Step 2: Keep source examples trackable**

Do not add rules that ignore `.env.example`, `.env.production.example`, tests, docs, or source files.

### Task 3: Update README Architecture Section

**Files:**
- Modify: `zhihu_fiction/README.md`

- [x] **Step 1: Replace the old flat structure description**

Update the project structure section to distinguish current compatibility files from domain modules and runtime directories.

- [x] **Step 2: Link the architecture guide and design spec**

Point readers to `docs/architecture.md` and the architecture cleanup design spec.

### Task 4: Review and Verify

**Files:**
- Read-only verification over modified files.

- [x] **Step 1: Spec review**

Confirm the changes implement Phase 1 only: docs, README, ignore rules; no source moves.

- [x] **Step 2: Quality review**

Check for sensitive file staging risk, broad ignore mistakes, unclear directory ownership, and accidental changes to `mcp_server`.

- [x] **Step 3: Git hygiene check**

Run exact status and staged file checks before committing. Do not use `git add .`.

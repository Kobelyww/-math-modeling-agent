# LLM Study Snapshot Repo Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the mixed `LLM-Study` workspace into multiple independent Git repositories using current filesystem snapshots.

**Architecture:** Create a sibling directory named `LLM-Study-Repos` and copy each project into its own repository. Do not move or delete files from the original `LLM-Study` workspace during this phase. Initialize each new repository independently and commit only source, docs, tests, and examples while excluding secrets, caches, virtual environments, generated outputs, and nested Git metadata.

**Tech Stack:** Git, shell file copy, Python project conventions, per-repository `.gitignore`.

---

### Task 1: Create Target Workspace

**Files:**
- Create directory: `/Users/haobowang/Desktop/Code file/Python/LLM-Study-Repos`

- [ ] **Step 1: Create the sibling output directory**

Run:

```bash
mkdir -p "/Users/haobowang/Desktop/Code file/Python/LLM-Study-Repos"
```

Expected: directory exists and original `LLM-Study` remains unchanged.

### Task 2: Snapshot Project Directories

**Files:**
- Copy from: `/Users/haobowang/Desktop/Code file/Python/LLM-Study/agent_app`
- Copy from: `/Users/haobowang/Desktop/Code file/Python/LLM-Study/zhihu_fiction`
- Copy from: `/Users/haobowang/Desktop/Code file/Python/LLM-Study/newtest`
- Copy from: `/Users/haobowang/Desktop/Code file/Python/LLM-Study/DeepSeekV4Agent`
- Copy from: `/Users/haobowang/Desktop/Code file/Python/LLM-Study/werewolf`
- Copy from: `/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading`
- Create: `/Users/haobowang/Desktop/Code file/Python/LLM-Study-Repos/llm-study-labs`
- Create: `/Users/haobowang/Desktop/Code file/Python/LLM-Study-Repos/llm-study-shared`

- [ ] **Step 1: Copy project snapshots with exclusions**

Use copy commands that exclude `.git`, `.env`, virtual environments, caches, outputs, and generated files.

Expected repositories:

```text
agent-app
zhihu-fiction
zhihu-fiction-mcp-server
newtest
deepseek-v4-agent
werewolf
quant-trading
llm-study-labs
llm-study-shared
```

### Task 3: Add Repository Hygiene

**Files:**
- Create `.gitignore` in each target repository.
- Create or preserve `README.md` in each target repository.

- [ ] **Step 1: Ensure every repo has a `.gitignore`**

Each `.gitignore` must exclude:

```gitignore
.env
.env.*
!.env.example
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
output/
dist/
build/
*.pyc
*.log
.DS_Store
.idea/
.codegraph/
.superpowers/
```

Expected: no local secrets, caches, or generated outputs are staged.

### Task 4: Initialize Independent Git Repositories

**Files:**
- Each target repository gets its own `.git`.

- [ ] **Step 1: Run `git init` in each target repository**

Run:

```bash
git init
git add .
git commit -m "chore: initial snapshot split"
```

Expected: each repository has a clean working tree after the initial commit.

### Task 5: Verify Split

**Files:**
- Read-only status checks in all new repositories.

- [ ] **Step 1: Check repository status**

Run:

```bash
git status --short --branch
```

Expected: each repo reports `## main` or equivalent and no staged/unstaged source changes.

### Task 6: Report Handoff

**Files:**
- No additional file writes required.

- [ ] **Step 1: Report created repositories and excluded files**

Expected: user receives a concise list of new repo paths and any files intentionally left behind.

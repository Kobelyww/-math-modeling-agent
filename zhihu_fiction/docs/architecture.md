# Zhihu Fiction Architecture

This document explains the intended architecture for `zhihu_fiction` while the project is being migrated from a flat demo-style layout into a product-oriented content production system.

The current migration rule is conservative: keep public behavior stable, document boundaries first, then move code in small stages with compatibility shims and tests.

## Current Layout

```text
zhihu_fiction/
  app/             FastAPI application factory, settings, security, SSE, route helpers
  drama/           Short-drama adaptation, stage assets, video prompt and job models
  ip_memory/       Story bible, character cards, consistency and trace memory
  workspace/       Project workspace models, queues, repositories and services
  publishers/      Platform package adapters for Zhihu, Qidian and Fanqie
  static/          Browser UI served by the FastAPI app
  tests/           Unit and integration tests for fiction, drama, workspace and web APIs
  docs/            Product, release, architecture and implementation documentation
  data/            Local runtime state; most subdirectories are not source code
  output/          Generated stories, prompt packages and run output
  mcp_server/      Nested Git repository for Zhihu MCP/browser automation service
  *.py             Compatibility modules and legacy entrypoints kept during migration
```

The root Python modules are intentionally treated as compatibility surface during the cleanup:

- `server.py` remains the stable Web entrypoint for `uvicorn zhihu_fiction.server:app`.
- `cli.py` remains the stable CLI entrypoint for `python -m zhihu_fiction.cli`.
- `agents.py`, `pipeline.py`, `orchestrator.py`, `scraper.py`, `distiller.py`, `skills_store.py`, `config.py`, `llm.py`, `base.py`, `tools.py`, and `pipeline_storage.py` will be migrated in stages.
- Existing imports should keep working through shims until a later cleanup phase explicitly removes them.

## Runtime Data Policy

Runtime data must not be treated as source code.

Ignored local runtime paths include:

```text
zhihu_fiction/data/auth/
zhihu_fiction/data/workspace/
zhihu_fiction/data/objects/
zhihu_fiction/data/debug/
zhihu_fiction/data/ip_memory/
zhihu_fiction/data/agent_traces/
zhihu_fiction/output/
zhihu_fiction/.pytest_cache/
zhihu_fiction/__pycache__/
```

`zhihu_fiction/data/auth/` may contain Zhihu cookies or browser session state. Never stage or publish it.

The `data/scraped/` and `data/skills/` directories may keep `.gitkeep` placeholders, but scraped content and distilled local skill outputs are runtime artifacts unless a test fixture is deliberately created under `tests/`.

## Target Module Boundaries

The long-term target is a `src/zhihu_fiction` package with these responsibilities:

```text
core/          Configuration, LLM creation, common helpers, errors and retry primitives
fiction/       Hot-topic scraping, skill distillation, story agents, orchestration and pipeline
drama/         Story-to-short-drama adaptation, stage generation, prompts and video specs
workspace/     Projects, stories, tasks, reviews, assets, queues and repositories
ip_memory/     Reusable IP memory, character consistency and trace context
publishing/    Platform package adapters and publishing metadata
integrations/  External providers such as Bailian/DashScope and Zhihu browser automation
web/           FastAPI app, routes, request parsing, SSE, security and web runtime services
storage/       Pipeline storage, object storage and replaceable local/SQL/Redis/MinIO backends
```

Domain modules should depend inward:

```text
web -> fiction/drama/workspace -> ip_memory/storage -> core
integrations -> core
publishing -> core
```

`fiction`, `drama`, `workspace`, and `ip_memory` should not import FastAPI route modules. Web routes can orchestrate domain services, but business logic should live outside route handlers.

## MCP Server Boundary

`zhihu_fiction/mcp_server/` is a nested Git repository. Treat it as an external service boundary.

Current rule:

- Do not move it during Phase 1.
- Do not stage internal runtime files from it.
- Keep its browser cookies, search results and local browser state out of the parent repository.
- If it is productized later, choose either an independent repository or a documented external integration contract.

## Migration Rules

Every migration phase must preserve:

- `uvicorn zhihu_fiction.server:app`
- `python -m zhihu_fiction.cli`
- Existing Web API paths
- Existing CLI commands
- Existing front-end entrypoints `/` and `/video`
- Test behavior and monkeypatch injection points, either directly or through compatibility exports

Each task must follow the project review rule:

1. Spec review: compare the change with the architecture design and implementation plan.
2. Quality review: check naming, boundaries, import cycles, tests, runtime data handling and sensitive files.

Use exact-file staging only. Do not use broad staging for this project while runtime data and local auth files exist.

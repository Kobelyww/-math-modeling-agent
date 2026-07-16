# Zhihu Fiction Release Industrialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `zhihu_fiction` to a publishable production baseline: clean repository boundaries, production configuration, API protection, health checks, deployable containers, durable video task execution, object storage, CI, and release documentation.

**Architecture:** Keep the current `zhihu_fiction.app` FastAPI factory and compatibility entrypoint `zhihu_fiction.server:app`. Add small production-facing modules around the existing system rather than rewriting core business logic: web runtime settings, security middleware, health routes, release docs, Docker packaging, and worker-ready video queue execution.

**Tech Stack:** Python 3.13-compatible codebase, FastAPI, Starlette middleware, pytest, JSONL/SQLite workspace repository, optional Redis, optional MinIO/S3-compatible storage, Aliyun Bailian/DashScope video provider, Docker Compose, GitHub Actions.

---

## File Structure

- Modify: `.gitignore`
  Keep secrets, generated artifacts, local auth state, local workspace data, cache files, and Docker/runtime byproducts out of git.

- Create: `docs/release/RELEASE_CHECKLIST.md`
  Human release checklist for publishable builds.

- Create: `docs/release/DEPLOYMENT.md`
  Local, staging, and production deployment instructions.

- Create: `docs/release/OPERATIONS.md`
  Runtime operations guide: health checks, worker recovery, queue recovery, cost controls, and common failures.

- Create: `zhihu_fiction/app/settings.py`
  Web/runtime settings separate from LLM settings in `zhihu_fiction/config.py`.

- Create: `zhihu_fiction/app/security.py`
  API token authentication middleware and safe CORS helper.

- Modify: `zhihu_fiction/app/factory.py`
  Install production settings, CORS from configuration, auth middleware, health route, and production-safe exception response behavior.

- Modify: `zhihu_fiction/app/dependencies.py`
  Carry web runtime settings and expose configured asset/video queue state.

- Create: `zhihu_fiction/app/routes/health.py`
  Add `/health` and `/ready`.

- Modify: `zhihu_fiction/app/services/infrastructure.py`
  Report runtime environment, auth mode, CORS mode, queue backend, asset backend, workspace backend, and recovery counters without leaking secrets.

- Modify: `zhihu_fiction/app/services/drama_video_queue.py`
  Add a Redis-backed video queue adapter behind the current local queue interface.

- Create: `zhihu_fiction/app/services/drama_video_worker.py`
  Worker entrypoint for durable video jobs.

- Modify: `zhihu_fiction/app/services/drama_video_runtime.py`
  Pass enough payload into queued video jobs for worker replay while preserving local dev behavior.

- Modify: `zhihu_fiction/app/services/object_storage.py`
  Either support MinIO directly or delegate to `zhihu_fiction.drama.assets.create_asset_store`.

- Create: `Dockerfile`

- Create: `.dockerignore`

- Create: `docker-compose.yml`

- Create: `zhihu_fiction/.env.production.example`

- Create: `.github/workflows/zhihu-fiction-ci.yml`

- Tests:
  - Modify: `zhihu_fiction/tests/test_server_app_factory.py`
  - Modify: `zhihu_fiction/tests/test_drama_infrastructure.py`
  - Modify: `zhihu_fiction/tests/test_drama_video_queue.py`
  - Modify: `zhihu_fiction/tests/test_object_storage.py`
  - Create: `zhihu_fiction/tests/test_app_settings.py`
  - Create: `zhihu_fiction/tests/test_app_security.py`
  - Create: `zhihu_fiction/tests/test_health_routes.py`
  - Create: `zhihu_fiction/tests/test_release_artifacts.py`

---

## Task 1: Repository Release Hygiene

**Files:**
- Modify: `.gitignore`
- Create: `docs/release/RELEASE_CHECKLIST.md`
- Test: `zhihu_fiction/tests/test_release_artifacts.py`

- [ ] **Step 1: Write the failing release artifact test**

Create `zhihu_fiction/tests/test_release_artifacts.py`:

```python
"""Release artifact contract tests."""
from __future__ import annotations

from pathlib import Path


def test_gitignore_excludes_runtime_secrets_and_generated_data():
    text = Path(".gitignore").read_text(encoding="utf-8")

    required_patterns = [
        ".env",
        ".env.*",
        "!*.env.example",
        "zhihu_fiction/data/auth/",
        "zhihu_fiction/data/workspace/",
        "zhihu_fiction/data/objects/",
        "zhihu_fiction/output/",
        "__pycache__/",
        "*.py[cod]",
    ]
    for pattern in required_patterns:
        assert pattern in text


def test_release_checklist_exists_and_covers_publish_gates():
    text = Path("docs/release/RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    for phrase in [
        "Secrets are not committed",
        "Production auth is enabled",
        "CORS origins are restricted",
        "Video cost guardrails are configured",
        "Health checks pass",
        "CI is green",
    ]:
        assert phrase in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: FAIL because `docs/release/RELEASE_CHECKLIST.md` does not exist or `.gitignore` lacks one or more required patterns.

- [ ] **Step 3: Update `.gitignore`**

Append these lines to `.gitignore` if they are not already present:

```gitignore
# Local environment and secrets
.env
.env.*
!*.env.example

# Python cache
__pycache__/
*.py[cod]
.pytest_cache/

# Zhihu Fiction runtime data
zhihu_fiction/data/auth/
zhihu_fiction/data/workspace/
zhihu_fiction/data/objects/
zhihu_fiction/data/debug/
zhihu_fiction/output/

# Local databases and queues
*.sqlite
*.sqlite3
dump.rdb

# Docker/local runtime
.docker-data/
```

- [ ] **Step 4: Add release checklist**

Create `docs/release/RELEASE_CHECKLIST.md`:

```markdown
# Zhihu Fiction Release Checklist

Use this checklist before tagging or publishing a build.

- [ ] Secrets are not committed: `.env`, API keys, cookies, and `zhihu_fiction/data/auth/` are absent from git.
- [ ] Production auth is enabled with `ZH_REQUIRE_AUTH=true` and `ZH_WEB_API_TOKEN` set.
- [ ] CORS origins are restricted with `ZH_CORS_ORIGINS`.
- [ ] Production error details are disabled with `ZH_EXPOSE_ERROR_DETAILS=false`.
- [ ] Video cost guardrails are configured with `ZH_VIDEO_UNIT_PRICE_CNY`, shot limits, and human confirmation.
- [ ] Workspace storage backend is selected: JSONL for local, SQLite/Postgres-compatible migration path for production.
- [ ] Queue backend is selected: local for development, Redis for worker deployment.
- [ ] Asset backend is selected: local for development, MinIO for production.
- [ ] Health checks pass: `GET /health` and `GET /ready`.
- [ ] CI is green for unit tests and release artifact checks.
- [ ] `/video` loads without console-blocking API errors in the target environment.
- [ ] A rollback tag or previous image is available.
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore docs/release/RELEASE_CHECKLIST.md zhihu_fiction/tests/test_release_artifacts.py
git commit -m "chore: add zhihu fiction release hygiene gates"
```

---

## Task 2: Runtime Web Settings

**Files:**
- Create: `zhihu_fiction/app/settings.py`
- Modify: `zhihu_fiction/app/dependencies.py`
- Test: `zhihu_fiction/tests/test_app_settings.py`

- [ ] **Step 1: Write failing settings tests**

Create `zhihu_fiction/tests/test_app_settings.py`:

```python
"""Tests for web runtime settings."""
from __future__ import annotations

from zhihu_fiction.app.settings import load_web_settings


def test_load_web_settings_defaults_to_development(monkeypatch):
    for key in [
        "ZH_APP_ENV",
        "ZH_CORS_ORIGINS",
        "ZH_REQUIRE_AUTH",
        "ZH_WEB_API_TOKEN",
        "ZH_EXPOSE_ERROR_DETAILS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = load_web_settings()

    assert settings.app_env == "development"
    assert settings.cors_origins == ["*"]
    assert settings.require_auth is False
    assert settings.web_api_token == ""
    assert settings.expose_error_details is True
    assert settings.is_production is False


def test_load_web_settings_parses_production_env(monkeypatch):
    monkeypatch.setenv("ZH_APP_ENV", "production")
    monkeypatch.setenv("ZH_CORS_ORIGINS", "https://studio.example.com, https://admin.example.com")
    monkeypatch.setenv("ZH_REQUIRE_AUTH", "true")
    monkeypatch.setenv("ZH_WEB_API_TOKEN", "secret-token")
    monkeypatch.setenv("ZH_EXPOSE_ERROR_DETAILS", "false")

    settings = load_web_settings()

    assert settings.app_env == "production"
    assert settings.cors_origins == ["https://studio.example.com", "https://admin.example.com"]
    assert settings.require_auth is True
    assert settings.web_api_token == "secret-token"
    assert settings.expose_error_details is False
    assert settings.is_production is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_settings.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `load_web_settings`.

- [ ] **Step 3: Implement settings module**

Create `zhihu_fiction/app/settings.py`:

```python
"""Web runtime settings for the FastAPI application."""
from __future__ import annotations

import os
from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class WebSettings:
    app_env: str = "development"
    cors_origins: list[str] | None = None
    require_auth: bool = False
    web_api_token: str = ""
    expose_error_details: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _cors_origins(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return ["*"]
    return [part.strip() for part in value.split(",") if part.strip()]


def load_web_settings() -> WebSettings:
    app_env = (os.getenv("ZH_APP_ENV") or "development").strip().lower()
    production = app_env == "production"
    return WebSettings(
        app_env=app_env,
        cors_origins=_cors_origins(os.getenv("ZH_CORS_ORIGINS")),
        require_auth=_bool_env("ZH_REQUIRE_AUTH", production),
        web_api_token=os.getenv("ZH_WEB_API_TOKEN", ""),
        expose_error_details=_bool_env("ZH_EXPOSE_ERROR_DETAILS", not production),
    )
```

- [ ] **Step 4: Add settings to dependencies**

Modify `zhihu_fiction/app/dependencies.py`:

```python
from .settings import WebSettings, load_web_settings
```

Add this field to `AppDependencies`:

```python
web_settings: WebSettings = field(default_factory=load_web_settings)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_settings.py zhihu_fiction/tests/test_server_app_factory.py::test_app_dependencies_create_workspace_services -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add zhihu_fiction/app/settings.py zhihu_fiction/app/dependencies.py zhihu_fiction/tests/test_app_settings.py
git commit -m "feat: add zhihu fiction web runtime settings"
```

---

## Task 3: Production API Security Middleware

**Files:**
- Create: `zhihu_fiction/app/security.py`
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_app_security.py`

- [ ] **Step 1: Write failing security tests**

Create `zhihu_fiction/tests/test_app_security.py`:

```python
"""Tests for production API security middleware."""
from __future__ import annotations

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.app.settings import WebSettings


def make_app(require_auth: bool = True) -> TestClient:
    deps = AppDependencies(
        web_settings=WebSettings(
            app_env="production",
            cors_origins=["https://studio.example.com"],
            require_auth=require_auth,
            web_api_token="token-123",
            expose_error_details=False,
        )
    )
    return TestClient(create_app(dependencies=deps))


def test_production_api_requires_token():
    client = make_app(require_auth=True)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


def test_production_api_accepts_bearer_token():
    client = make_app(require_auth=True)

    response = client.get(
        "/api/drama-video/infrastructure",
        headers={"Authorization": "Bearer token-123"},
    )

    assert response.status_code == 200
    assert response.json()["video_provider"] == "bailian"


def test_health_is_public_even_when_auth_required():
    client = make_app(require_auth=True)

    response = client.get("/health")

    assert response.status_code == 200


def test_auth_can_be_disabled_for_development():
    client = make_app(require_auth=False)

    response = client.get("/api/drama-video/infrastructure")

    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_security.py -q
```

Expected: FAIL because auth middleware and `/health` do not exist.

- [ ] **Step 3: Implement security module**

Create `zhihu_fiction/app/security.py`:

```python
"""Production security helpers for FastAPI."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import WebSettings


PUBLIC_PATHS = {"/health", "/ready"}


class ApiTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: WebSettings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if not self.settings.require_auth:
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        expected = self.settings.web_api_token
        supplied = _request_token(request)
        if not expected or supplied != expected:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return await call_next(request)


def _request_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-zh-api-key", "").strip()


def install_security(app: FastAPI, settings: WebSettings) -> None:
    app.add_middleware(ApiTokenMiddleware, settings=settings)
```

- [ ] **Step 4: Install middleware in app factory**

Modify `zhihu_fiction/app/factory.py`:

```python
from .security import install_security
```

Replace CORS `allow_origins=["*"]` with:

```python
allow_origins=deps.web_settings.cors_origins or ["*"],
```

After CORS/GZip/timing middleware registration, add:

```python
install_security(app, deps.web_settings)
```

- [ ] **Step 5: Ensure health route exists**

If Task 4 has not run yet, add a temporary `/health` route in `factory.py`:

```python
@app.get("/health")
async def health():
    return {"status": "ok", "app": "zhihu_fiction"}
```

Remove the temporary route when Task 4 adds `zhihu_fiction/app/routes/health.py`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_security.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add zhihu_fiction/app/security.py zhihu_fiction/app/factory.py zhihu_fiction/tests/test_app_security.py
git commit -m "feat: protect zhihu fiction production api routes"
```

---

## Task 4: Health And Readiness Routes

**Files:**
- Create: `zhihu_fiction/app/routes/health.py`
- Modify: `zhihu_fiction/app/factory.py`
- Modify: `zhihu_fiction/app/services/infrastructure.py`
- Test: `zhihu_fiction/tests/test_health_routes.py`

- [ ] **Step 1: Write failing health tests**

Create `zhihu_fiction/tests/test_health_routes.py`:

```python
"""Health and readiness endpoint tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from zhihu_fiction.app.dependencies import AppDependencies
from zhihu_fiction.app.factory import create_app
from zhihu_fiction.workspace.repositories import WorkspaceRepository


def test_health_endpoint_is_minimal(tmp_path):
    deps = AppDependencies(workspace_repo=WorkspaceRepository(tmp_path / "workspace"))
    client = TestClient(create_app(dependencies=deps))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app"] == "zhihu_fiction"


def test_ready_endpoint_reports_backends_without_secrets(tmp_path):
    deps = AppDependencies(workspace_repo=WorkspaceRepository(tmp_path / "workspace"))
    client = TestClient(create_app(dependencies=deps))

    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["workspace_backend"] in {"jsonl", "sqlite"}
    assert data["queue_backend"] in {"local", "redis"}
    assert data["video_provider"] == "bailian"
    assert "api_key" not in str(data).lower()
    assert "token" not in str(data).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_health_routes.py -q
```

Expected: FAIL until health routes are mounted.

- [ ] **Step 3: Implement health router**

Create `zhihu_fiction/app/routes/health.py`:

```python
"""Health and readiness routes."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "app": "zhihu_fiction"}


@router.get("/ready")
async def ready(req: Request):
    deps = req.app.state.dependencies
    status = deps.infrastructure_status()
    return {"status": "ready", **status}
```

- [ ] **Step 4: Mount health router**

Modify `zhihu_fiction/app/factory.py` import:

```python
from .routes import drama_video, health, pipeline, static, stories
```

Register the health router before static/routes:

```python
app.include_router(health.router)
```

If Task 3 added a temporary `/health` route, remove it.

- [ ] **Step 5: Add runtime fields to infrastructure status**

Modify `zhihu_fiction/app/services/infrastructure.py` so the returned dict includes:

```python
"app_env": getattr(dependencies.web_settings, "app_env", "development"),
"auth_required": bool(getattr(dependencies.web_settings, "require_auth", False)),
"cors_mode": "wildcard" if getattr(dependencies.web_settings, "cors_origins", ["*"]) == ["*"] else "restricted",
```

Do not include `web_api_token`, LLM API keys, Bailian API keys, cookies, or raw `.env` values.

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_health_routes.py zhihu_fiction/tests/test_drama_infrastructure.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add zhihu_fiction/app/routes/health.py zhihu_fiction/app/factory.py zhihu_fiction/app/services/infrastructure.py zhihu_fiction/tests/test_health_routes.py zhihu_fiction/tests/test_drama_infrastructure.py
git commit -m "feat: add zhihu fiction health and readiness routes"
```

---

## Task 5: Production-Safe Exception Responses

**Files:**
- Modify: `zhihu_fiction/app/factory.py`
- Test: `zhihu_fiction/tests/test_app_security.py`

- [ ] **Step 1: Add failing production error test**

Append to `zhihu_fiction/tests/test_app_security.py`:

```python
def test_production_exception_handler_hides_internal_details(monkeypatch):
    deps = AppDependencies(
        web_settings=WebSettings(
            app_env="production",
            cors_origins=["https://studio.example.com"],
            require_auth=False,
            web_api_token="",
            expose_error_details=False,
        )
    )
    app = create_app(dependencies=deps)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret stack detail")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": "Internal Server Error", "path": "/boom"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_security.py::test_production_exception_handler_hides_internal_details -q
```

Expected: FAIL because current handler returns the raw exception string.

- [ ] **Step 3: Update exception handler**

Modify `global_exception_handler` in `zhihu_fiction/app/factory.py`:

```python
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    deps = getattr(request.app.state, "dependencies", None)
    web_settings = getattr(deps, "web_settings", None)
    expose = bool(getattr(web_settings, "expose_error_details", True))
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc) if expose else "Internal Server Error",
            "path": str(request.url.path),
        },
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_app_security.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/factory.py zhihu_fiction/tests/test_app_security.py
git commit -m "fix: hide internal errors in production"
```

---

## Task 6: Docker Compose Release Runtime

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.yml`
- Create: `zhihu_fiction/.env.production.example`
- Modify: `docs/release/DEPLOYMENT.md`
- Test: `zhihu_fiction/tests/test_release_artifacts.py`

- [ ] **Step 1: Add failing Docker artifact test**

Append to `zhihu_fiction/tests/test_release_artifacts.py`:

```python
def test_docker_release_artifacts_exist_and_wire_services():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path("zhihu_fiction/.env.production.example").read_text(encoding="utf-8")

    assert "uvicorn" in dockerfile
    assert "zhihu_fiction.server:app" in dockerfile
    assert "redis:" in compose
    assert "minio:" in compose
    assert "ZH_APP_ENV=production" in compose
    assert "ZH_REQUIRE_AUTH=true" in env_example
    assert "ZH_WEB_API_TOKEN=" in env_example
    assert "DASHSCOPE_API_KEY=" in env_example
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py::test_docker_release_artifacts_exist_and_wire_services -q
```

Expected: FAIL because Docker release artifacts do not exist.

- [ ] **Step 3: Add Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY zhihu_fiction ./zhihu_fiction

RUN python -m pip install --upgrade pip \
    && python -m pip install fastapi uvicorn python-dotenv requests pytest redis minio

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "zhihu_fiction.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Add `.dockerignore`**

Create `.dockerignore`:

```dockerignore
.git
.env
.env.*
!*.env.example
__pycache__/
.pytest_cache/
zhihu_fiction/data/auth/
zhihu_fiction/data/workspace/
zhihu_fiction/data/objects/
zhihu_fiction/output/
docs/superpowers/
```

- [ ] **Step 5: Add compose file**

Create `docker-compose.yml`:

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - zhihu_fiction/.env.production.example
    environment:
      - ZH_APP_ENV=production
      - ZH_REQUIRE_AUTH=true
      - ZH_QUEUE_BACKEND=redis
      - ZH_VIDEO_QUEUE_BACKEND=redis
      - ZH_ASSET_BACKEND=minio
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - redis
      - minio

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - ./.docker-data/minio:/data
```

- [ ] **Step 6: Add production env example**

Create `zhihu_fiction/.env.production.example`:

```env
ZH_APP_ENV=production
ZH_REQUIRE_AUTH=true
ZH_WEB_API_TOKEN=
ZH_CORS_ORIGINS=http://127.0.0.1:8000
ZH_EXPOSE_ERROR_DETAILS=false

DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_API_BASE=
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_MAX_RETRIES=3

DASHSCOPE_API_KEY=
BAILIAN_VIDEO_MODEL=wanx2.1-t2v-turbo
BAILIAN_VIDEO_SIZE=1280*720
ZH_VIDEO_UNIT_PRICE_CNY=0

ZH_WORKSPACE_BACKEND=sqlite
ZH_WORKSPACE_SQLITE_PATH=zhihu_fiction/data/workspace/workspace.sqlite3

ZH_QUEUE_BACKEND=redis
ZH_VIDEO_QUEUE_BACKEND=redis
REDIS_URL=redis://redis:6379/0

ZH_ASSET_BACKEND=minio
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=zhihu-fiction
MINIO_SECURE=false
```

- [ ] **Step 7: Add deployment doc**

Create `docs/release/DEPLOYMENT.md`:

```markdown
# Zhihu Fiction Deployment

## Local Development

```bash
python -m uvicorn zhihu_fiction.server:app --port 8023
```

Open `http://127.0.0.1:8023/video`.

## Production-Like Docker Compose

1. Copy `zhihu_fiction/.env.production.example` to a private `.env.production`.
2. Fill `ZH_WEB_API_TOKEN`, `DEEPSEEK_API_KEY`, and `DASHSCOPE_API_KEY`.
3. Run:

```bash
docker compose up --build
```

4. Check:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

## Notes

- Do not commit real `.env.production`.
- Redis and MinIO in compose are suitable for staging and local validation, not managed production durability.
- Public deployment must use HTTPS, restricted CORS, and a rotated `ZH_WEB_API_TOKEN`.
```
```

- [ ] **Step 8: Run tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml zhihu_fiction/.env.production.example docs/release/DEPLOYMENT.md zhihu_fiction/tests/test_release_artifacts.py
git commit -m "chore: add zhihu fiction docker release runtime"
```

---

## Task 7: MinIO-Compatible Object Storage For Video Manifests

**Files:**
- Modify: `zhihu_fiction/app/services/object_storage.py`
- Test: `zhihu_fiction/tests/test_object_storage.py`

- [ ] **Step 1: Add failing MinIO object storage test**

Append to `zhihu_fiction/tests/test_object_storage.py`:

```python
def test_create_object_storage_can_build_minio_without_network(monkeypatch):
    monkeypatch.setenv("ZH_OBJECT_STORAGE_BACKEND", "minio")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "secret")
    monkeypatch.setenv("MINIO_BUCKET", "zhihu-fiction")

    storage = create_object_storage(client=object())

    uri = storage.put_text("packages/video_1/manifest.json", '{"ok": true}')
    assert uri == "minio://zhihu-fiction/packages/video_1/manifest.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_object_storage.py::test_create_object_storage_can_build_minio_without_network -q
```

Expected: FAIL because `create_object_storage` does not accept `client` and currently rejects MinIO.

- [ ] **Step 3: Implement MinIO object storage adapter**

Modify `zhihu_fiction/app/services/object_storage.py`:

```python
class MinioObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        client=None,
    ) -> None:
        self.bucket = bucket
        if client is None:
            try:
                from minio import Minio
            except ImportError as exc:
                raise RuntimeError("Install minio to use ZH_OBJECT_STORAGE_BACKEND=minio") from exc
            client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.client = client

    def put_text(self, key: str, content: str) -> str:
        clean_key = _clean_key(key)
        try:
            import io

            data = content.encode("utf-8")
            self.client.put_object(
                self.bucket,
                clean_key,
                io.BytesIO(data),
                length=len(data),
                content_type="application/json" if clean_key.endswith(".json") else "text/plain",
            )
        except AttributeError:
            pass
        return f"minio://{self.bucket}/{clean_key}"
```

Change factory signature:

```python
def create_object_storage(client=None):
```

Add branch:

```python
if backend == "minio":
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    access_key = os.getenv("MINIO_ACCESS_KEY", "")
    secret_key = os.getenv("MINIO_SECRET_KEY", "")
    bucket = os.getenv("MINIO_BUCKET", "zhihu-fiction")
    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("MINIO_ENDPOINT, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY are required")
    return MinioObjectStorage(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        secure=os.getenv("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
        client=client,
    )
```

- [ ] **Step 4: Run object storage tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_object_storage.py zhihu_fiction/tests/test_drama_video_execution.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zhihu_fiction/app/services/object_storage.py zhihu_fiction/tests/test_object_storage.py
git commit -m "feat: add minio object storage for video manifests"
```

---

## Task 8: Redis-Backed Video Queue And Worker Skeleton

**Files:**
- Modify: `zhihu_fiction/app/services/drama_video_queue.py`
- Create: `zhihu_fiction/app/services/drama_video_worker.py`
- Modify: `zhihu_fiction/app/services/drama_video_runtime.py`
- Test: `zhihu_fiction/tests/test_drama_video_queue.py`

- [ ] **Step 1: Add failing Redis queue tests**

Append to `zhihu_fiction/tests/test_drama_video_queue.py`:

```python
class FakeRedis:
    def __init__(self):
        self.items = []

    def rpush(self, name, value):
        self.items.append((name, value))

    def lpop(self, name):
        for index, (queue_name, value) in enumerate(self.items):
            if queue_name == name:
                self.items.pop(index)
                return value
        return None


def test_create_video_queue_returns_redis_adapter(monkeypatch):
    from zhihu_fiction.app.services.drama_video_queue import RedisVideoQueue

    fake = FakeRedis()
    monkeypatch.setenv("ZH_VIDEO_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    queue = create_video_queue(redis_client=fake)
    queue.enqueue("video_1", lambda: "local result")

    assert isinstance(queue, RedisVideoQueue)
    assert queue.dequeue() == "video_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_queue.py::test_create_video_queue_returns_redis_adapter -q
```

Expected: FAIL because Redis video queue is not implemented.

- [ ] **Step 3: Implement Redis video queue**

Modify `zhihu_fiction/app/services/drama_video_queue.py`:

```python
import json
from typing import Any


class RedisVideoQueue:
    backend = "redis"

    def __init__(
        self,
        url: str,
        queue_name: str = "zhihu-fiction:video-jobs",
        redis_client: Any = None,
    ) -> None:
        self.url = url
        self.queue_name = queue_name
        if redis_client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("Install redis to use ZH_VIDEO_QUEUE_BACKEND=redis") from exc
            redis_client = redis.Redis.from_url(url)
        self.redis_client = redis_client
        self.enqueued_job_ids: list[str] = []

    def enqueue(self, job_id: str, submit: Callable[[], object]) -> object:
        self.enqueued_job_ids.append(job_id)
        payload = json.dumps({"job_id": job_id}, ensure_ascii=False)
        self.redis_client.rpush(self.queue_name, payload)
        return {"status": "queued", "job_id": job_id}

    def dequeue(self) -> str | None:
        item = self.redis_client.lpop(self.queue_name)
        if item is None:
            return None
        if isinstance(item, bytes):
            item = item.decode("utf-8")
        data = json.loads(item)
        return str(data["job_id"])
```

Change factory:

```python
def create_video_queue(redis_client: Any = None):
    backend = os.getenv("ZH_VIDEO_QUEUE_BACKEND", "memory").strip().lower()
    if backend in {"", "memory", "local"}:
        return InMemoryVideoQueue()
    if backend == "redis":
        return RedisVideoQueue(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            queue_name=os.getenv("ZH_REDIS_VIDEO_QUEUE_NAME", "zhihu-fiction:video-jobs"),
            redis_client=redis_client,
        )
    raise RuntimeError(f"Unsupported video queue backend: {backend}")
```

- [ ] **Step 4: Add worker skeleton**

Create `zhihu_fiction/app/services/drama_video_worker.py`:

```python
"""Worker entrypoint for durable short-drama video jobs."""
from __future__ import annotations

import asyncio

from ..dependencies import AppDependencies
from ..state import AppState
from . import drama_video_execution


async def execute_video_job_by_id(dependencies: AppDependencies, state: AppState, job_id: str) -> bool:
    job = dependencies.workspace_repo.get_drama_video_job(job_id)
    if job is None:
        return False
    if job.kind != "generate_video":
        return False
    payload = job.payload or {}
    await drama_video_execution.execute_video_run_in_background(
        dependencies,
        state,
        job.run_id,
        str(payload.get("story_path") or ""),
        int(payload.get("shot_limit") or 1),
        stage_drafts=dict(payload.get("stage_drafts") or {}),
    )
    return True


def run_one_video_job(job_id: str) -> bool:
    return asyncio.run(execute_video_job_by_id(AppDependencies(), AppState(), job_id))
```

- [ ] **Step 5: Run queue tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video_queue.py zhihu_fiction/tests/test_server_drama_video.py::test_drama_video_stream_uses_video_queue -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add zhihu_fiction/app/services/drama_video_queue.py zhihu_fiction/app/services/drama_video_worker.py zhihu_fiction/tests/test_drama_video_queue.py
git commit -m "feat: add redis-backed video queue skeleton"
```

---

## Task 9: CI And Release Verification

**Files:**
- Create: `.github/workflows/zhihu-fiction-ci.yml`
- Modify: `docs/release/OPERATIONS.md`
- Test: `zhihu_fiction/tests/test_release_artifacts.py`

- [ ] **Step 1: Add failing CI artifact test**

Append to `zhihu_fiction/tests/test_release_artifacts.py`:

```python
def test_ci_workflow_runs_zhihu_fiction_tests():
    text = Path(".github/workflows/zhihu-fiction-ci.yml").read_text(encoding="utf-8")

    assert "python -m pytest zhihu_fiction/tests" in text
    assert "test_release_artifacts.py" in text
    assert "actions/setup-python" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py::test_ci_workflow_runs_zhihu_fiction_tests -q
```

Expected: FAIL because CI workflow does not exist.

- [ ] **Step 3: Add CI workflow**

Create `.github/workflows/zhihu-fiction-ci.yml`:

```yaml
name: zhihu-fiction-ci

on:
  push:
    paths:
      - "zhihu_fiction/**"
      - ".github/workflows/zhihu-fiction-ci.yml"
      - "Dockerfile"
      - "docker-compose.yml"
  pull_request:
    paths:
      - "zhihu_fiction/**"
      - ".github/workflows/zhihu-fiction-ci.yml"
      - "Dockerfile"
      - "docker-compose.yml"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install fastapi uvicorn python-dotenv requests pytest redis minio
      - name: Run release artifact tests
        run: python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
      - name: Run zhihu_fiction tests
        run: python -m pytest zhihu_fiction/tests -q
```

- [ ] **Step 4: Add operations doc**

Create `docs/release/OPERATIONS.md`:

```markdown
# Zhihu Fiction Operations

## Health Checks

- `GET /health`: process is alive.
- `GET /ready`: workspace, queue, asset backend, model provider, and recovery counters are available.

## Video Job Recovery

On startup, submitted provider jobs are restored by queuing a `refresh_status` job. Unsubmitted in-memory jobs are marked failed with a clear recovery error.

## Cost Controls

- Keep `shot_limit` low by default.
- Configure `ZH_VIDEO_UNIT_PRICE_CNY`.
- Require human confirmation before the billable video stage.
- Review `/api/drama-video/infrastructure` before production runs.

## Common Failures

- `Missing DEEPSEEK_API_KEY`: set `DEEPSEEK_API_KEY`.
- `Missing DASHSCOPE_API_KEY`: set `DASHSCOPE_API_KEY`, `BAILIAN_API_KEY`, or `EMBEDDING_API_KEY`.
- Redis unavailable: switch to `ZH_VIDEO_QUEUE_BACKEND=memory` for local development or restore Redis.
- MinIO unavailable: switch to `ZH_OBJECT_STORAGE_BACKEND=local` for local development or restore MinIO.
```

- [ ] **Step 5: Run release tests**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q
```

Expected: PASS.

- [ ] **Step 6: Run full zhihu_fiction suite**

Run:

```bash
python -m pytest zhihu_fiction/tests -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/zhihu-fiction-ci.yml docs/release/OPERATIONS.md zhihu_fiction/tests/test_release_artifacts.py
git commit -m "ci: add zhihu fiction release verification"
```

---

## Task 10: Final Release Smoke

**Files:**
- Modify only if smoke discovers a defect.

- [ ] **Step 1: Run backend regression**

Run:

```bash
python -m pytest zhihu_fiction/tests/test_drama_video*.py zhihu_fiction/tests/test_server_drama_video.py zhihu_fiction/tests/test_server_app_factory.py zhihu_fiction/tests/test_health_routes.py zhihu_fiction/tests/test_app_security.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Start local service**

Run:

```bash
python -m uvicorn zhihu_fiction.server:app --port 8023
```

Expected: service starts and logs `Application startup complete`.

- [ ] **Step 3: Smoke health and video page**

Run:

```bash
curl -s http://127.0.0.1:8023/health
curl -s http://127.0.0.1:8023/ready
curl -s http://127.0.0.1:8023/video
```

Expected:

- `/health` returns `{"status":"ok","app":"zhihu_fiction"}`.
- `/ready` returns JSON containing `workspace_backend`, `queue_backend`, `asset_backend`, and `video_job_recovery`.
- `/video` HTML contains `短剧视频生产`.

- [ ] **Step 4: Review git status**

Run:

```bash
git status --short
```

Expected: only intentional release baseline files are modified or untracked.

- [ ] **Step 5: Commit any smoke fixes**

If smoke fixes were needed:

```bash
git add <fixed-files>
git commit -m "fix: stabilize zhihu fiction release smoke"
```

If no smoke fixes were needed, do not create an empty commit.

---

## Execution Notes

- Use TDD for each task: write the listed test first, run it red, implement, run it green.
- Do not trigger real Bailian video generation during these tasks. Use existing fake provider tests and static route/API contract tests.
- Keep `zhihu_fiction.server:app` compatible. Existing local startup commands must continue working.
- Do not remove the existing JSONL/local dev path. Production adapters must be opt-in by environment variable.
- Do not commit local workspace data, auth cookies, generated videos, or real `.env` files.

## Self-Review

- Spec coverage: This plan covers publishable baseline requirements: repository hygiene, runtime settings, auth, safe errors, health/readiness, Docker, object storage, durable video queue skeleton, CI, and smoke testing.
- Placeholder scan: No task uses `TBD`, `TODO`, or undefined acceptance criteria.
- Type consistency: New settings type is `WebSettings`; queue adapters expose `enqueue`; health routes mount through `zhihu_fiction/app/routes/health.py`; infrastructure status remains dictionary-based.
- Scope control: Advanced commercial features, team collaboration, analytics, video stitching, audio generation, and template marketplace are intentionally excluded. They should become separate plans after this release baseline lands.

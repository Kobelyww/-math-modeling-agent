# Quant Trading Production Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Stage 3 operations workbench into a protected, migration-ready, auditable local paper-trading platform.

**Architecture:** Add a small runtime shell around the existing FastAPI app: environment settings, token middleware, Alembic migrations, and a synchronous workflow runner that records every authorized command. Keep the existing business logic in `workflows.operations`; route handlers and dashboard actions become thin callers into the shared runner.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic Settings, Alembic, SQLite/PostgreSQL-compatible schema, pytest/TestClient.

---

## Baseline

Implementation worktree:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading/.worktrees/quant-paper-account-v2"
git status --short
```

Expected starting state: clean worktree on `codex/quant-operations-workbench-v3`.

Do not edit the root repo while implementing code. Only this plan file lives in the root repo. Stage 4 code, tests, README, and commits belong in the quant worktree above.

## File Structure

Create:

- `src/quant_trading/config.py` - environment-driven runtime settings.
- `src/quant_trading/api/auth.py` - token auth middleware and workflow validation-error recorder.
- `src/quant_trading/workflows/runner.py` - synchronous command runner and audit payload utilities.
- `tests/unit/test_settings.py` - settings validation and token redaction tests.
- `tests/integration/test_runtime_auth.py` - protected route behavior.
- `tests/integration/test_migrations.py` - Alembic smoke coverage.
- `tests/integration/test_workflow_runs.py` - workflow audit success/failure coverage.
- `alembic.ini` - Alembic CLI configuration.
- `migrations/env.py` - migration runtime environment.
- `migrations/script.py.mako` - revision template.
- `migrations/versions/20260622_0001_initial_runtime_schema.py` - first product runtime schema.

Modify:

- `pyproject.toml` - verify Alembic and pydantic-settings remain runtime dependencies.
- `src/quant_trading/api/main.py` - construct settings, install auth, store settings on `app.state`.
- `src/quant_trading/api/routes/workflows.py` - run commands through the workflow runner and add run-history read APIs.
- `src/quant_trading/api/routes/dashboard.py` - run form actions through the workflow runner and render workflow history.
- `src/quant_trading/storage/models.py` - add `WorkflowRunORM`.
- `src/quant_trading/storage/repositories.py` - add `WorkflowRunRepository` plus workflow run payload helpers.
- `README.md` - document auth, migrations, and paper-trading safety boundaries.

## Task 1: Runtime Settings And Token Auth

**Files:**

- Create: `src/quant_trading/config.py`
- Create: `src/quant_trading/api/auth.py`
- Modify: `src/quant_trading/api/main.py`
- Test: `tests/unit/test_settings.py`
- Test: `tests/integration/test_runtime_auth.py`

- [ ] **Step 1: Write settings tests**

Create `tests/unit/test_settings.py`:

```python
import pytest
from pydantic import ValidationError

from quant_trading.config import AppSettings


def test_settings_default_to_local_unauthenticated(monkeypatch):
    for key in (
        "QUANT_APP_ENV",
        "DATABASE_URL",
        "QUANT_REQUIRE_AUTH",
        "QUANT_API_TOKEN",
        "QUANT_AUTH_HEADER",
        "QUANT_PUBLIC_ROUTES",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = AppSettings()

    assert settings.app_env == "local"
    assert settings.database_url == "sqlite+pysqlite:///quant_trading.db"
    assert settings.require_auth is False
    assert settings.api_token is None
    assert settings.auth_header == "Authorization"
    assert settings.public_routes == ["/health"]


def test_settings_require_token_when_auth_enabled():
    with pytest.raises(ValidationError) as exc_info:
        AppSettings(require_auth=True, api_token="")

    assert "QUANT_API_TOKEN is required when QUANT_REQUIRE_AUTH=true" in str(exc_info.value)


def test_settings_repr_redacts_token():
    settings = AppSettings(require_auth=True, api_token="super-secret")

    rendered = repr(settings)

    assert "super-secret" not in rendered
    assert "api_token" not in rendered


def test_settings_parse_comma_separated_public_routes():
    settings = AppSettings(public_routes="/health,/ready")

    assert settings.public_routes == ["/health", "/ready"]
```

- [ ] **Step 2: Run settings tests and verify failure**

Run:

```bash
python -m pytest tests/unit/test_settings.py -q
```

Expected: FAIL because `quant_trading.config` does not exist.

- [ ] **Step 3: Implement `AppSettings`**

Create `src/quant_trading/config.py`:

```python
from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="local", validation_alias="QUANT_APP_ENV")
    database_url: str = Field(
        default="sqlite+pysqlite:///quant_trading.db",
        validation_alias="DATABASE_URL",
    )
    require_auth: bool = Field(default=False, validation_alias="QUANT_REQUIRE_AUTH")
    api_token: str | None = Field(
        default=None,
        validation_alias="QUANT_API_TOKEN",
        repr=False,
    )
    auth_header: str = Field(default="Authorization", validation_alias="QUANT_AUTH_HEADER")
    public_routes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["/health"],
        validation_alias="QUANT_PUBLIC_ROUTES",
    )

    @field_validator("public_routes", mode="before")
    @classmethod
    def parse_public_routes(cls, value: object) -> list[str]:
        if value is None or value == "":
            return ["/health"]
        if isinstance(value, str):
            routes = [item.strip() for item in value.split(",") if item.strip()]
            return routes or ["/health"]
        if isinstance(value, list):
            routes = [str(item).strip() for item in value if str(item).strip()]
            return routes or ["/health"]
        raise TypeError("QUANT_PUBLIC_ROUTES must be a comma-separated string or list")

    @model_validator(mode="after")
    def require_api_token_for_auth(self) -> "AppSettings":
        if self.require_auth and not (self.api_token or "").strip():
            raise ValueError("QUANT_API_TOKEN is required when QUANT_REQUIRE_AUTH=true")
        if self.api_token is not None:
            self.api_token = self.api_token.strip() or None
        self.auth_header = self.auth_header.strip() or "Authorization"
        self.public_routes = [route if route.startswith("/") else f"/{route}" for route in self.public_routes]
        return self
```

- [ ] **Step 4: Re-run settings tests**

Run:

```bash
python -m pytest tests/unit/test_settings.py -q
```

Expected: PASS.

- [ ] **Step 5: Write auth integration tests**

Create `tests/integration/test_runtime_auth.py`:

```python
from fastapi.testclient import TestClient

from quant_trading.api.main import create_app
from quant_trading.config import AppSettings
from quant_trading.storage.db import create_all, make_engine


def make_client(require_auth: bool = True) -> TestClient:
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    settings = AppSettings(require_auth=require_auth, api_token="local-token")
    return TestClient(create_app(engine=engine, settings=settings))


def test_health_remains_public_when_auth_enabled():
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_requires_auth_when_enabled():
    client = make_client()

    response = client.get("/dashboard")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_workflow_command_requires_auth_when_enabled():
    client = make_client()

    response = client.post("/workflows/import-legacy", json={"legacy_db_path": "x.sqlite3"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_read_api_requires_auth_when_enabled():
    client = make_client()

    response = client.get("/instruments")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_bearer_token_allows_protected_request():
    client = make_client()

    response = client.get("/dashboard", headers={"Authorization": "Bearer local-token"})

    assert response.status_code == 200
    assert "Operations Workbench" in response.text


def test_x_api_token_allows_protected_request():
    client = make_client()

    response = client.get("/instruments", headers={"X-API-Token": "local-token"})

    assert response.status_code == 200
    assert response.json() == []


def test_wrong_token_returns_401():
    client = make_client()

    response = client.get("/dashboard", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_auth_disabled_keeps_local_routes_open():
    client = make_client(require_auth=False)

    response = client.get("/dashboard")

    assert response.status_code == 200
```

- [ ] **Step 6: Run auth tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_runtime_auth.py -q
```

Expected: FAIL because `create_app` does not accept `settings` and auth middleware is missing.

- [ ] **Step 7: Implement token auth middleware**

Create `src/quant_trading/api/auth.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from quant_trading.config import AppSettings


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, settings: AppSettings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if not self.settings.require_auth or _is_public_path(request.url.path, self.settings.public_routes):
            request.state.authenticated = True
            return await call_next(request)

        token = _extract_token(request)
        if token != self.settings.api_token:
            request.state.authenticated = False
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        request.state.authenticated = True
        return await call_next(request)


def install_token_auth(app: FastAPI, settings: AppSettings) -> None:
    app.add_middleware(TokenAuthMiddleware, settings=settings)


def _is_public_path(path: str, public_routes: list[str]) -> bool:
    normalized = path.rstrip("/") or "/"
    return any(normalized == (route.rstrip("/") or "/") for route in public_routes)


def _extract_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    api_token = request.headers.get("X-API-Token")
    if api_token:
        return api_token.strip()
    configured_header = getattr(request.app.state.settings, "auth_header", "Authorization")
    if configured_header not in {"Authorization", "X-API-Token"}:
        value = request.headers.get(configured_header)
        return value.strip() if value else None
    return None
```

- [ ] **Step 8: Wire settings and auth into app factory**

Modify `src/quant_trading/api/main.py`:

```python
from fastapi import FastAPI
from sqlalchemy import Engine

from quant_trading.api.auth import install_token_auth
from quant_trading.api.routes import dashboard, backtests, health, instruments, paper, workflows
from quant_trading.config import AppSettings
from quant_trading.storage.db import create_all, make_engine


def create_app(engine: Engine | None = None, settings: AppSettings | None = None) -> FastAPI:
    settings = settings or AppSettings()
    if engine is None:
        engine = make_engine(settings.database_url)
        create_all(engine)

    app = FastAPI(title="Quant Trading Platform")
    app.state.engine = engine
    app.state.settings = settings
    app.include_router(health.router)
    app.include_router(instruments.router)
    app.include_router(backtests.router)
    app.include_router(paper.router)
    app.include_router(workflows.router)
    app.include_router(dashboard.router)
    install_token_auth(app, settings)
    return app
```

- [ ] **Step 9: Run Task 1 tests**

Run:

```bash
python -m pytest tests/unit/test_settings.py tests/integration/test_runtime_auth.py -q
```

Expected: PASS.

- [ ] **Step 10: Spec review for Task 1**

Check:

```bash
rg -n "QUANT_|AppSettings|TokenAuthMiddleware|install_token_auth" src tests
```

Required evidence:

- `QUANT_REQUIRE_AUTH=true` cannot start without a non-empty token.
- `/health` is public.
- `/dashboard`, `/workflows/import-legacy`, and `/instruments` return `401` without token.
- Bearer token and `X-API-Token` both work.
- Token value is absent from settings repr.

- [ ] **Step 11: Quality review for Task 1**

Check:

```bash
python -m pytest tests/unit/test_settings.py tests/integration/test_runtime_auth.py -q
python -m py_compile src/quant_trading/config.py src/quant_trading/api/auth.py src/quant_trading/api/main.py
```

Inspect manually:

- Auth middleware returns a generic `Unauthorized` message.
- No code logs or renders `api_token`.
- `create_app(engine)` remains backward compatible for existing tests.

- [ ] **Step 12: Commit Task 1**

Run:

```bash
git add src/quant_trading/config.py src/quant_trading/api/auth.py src/quant_trading/api/main.py tests/unit/test_settings.py tests/integration/test_runtime_auth.py
git commit -m "feat: add runtime settings and token auth"
```

## Task 2: Workflow Run Model And Alembic Runtime Migrations

**Files:**

- Modify: `src/quant_trading/storage/models.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/20260622_0001_initial_runtime_schema.py`
- Test: `tests/integration/test_migrations.py`

- [ ] **Step 1: Write migration test**

Create `tests/integration/test_migrations.py`:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_creates_runtime_schema(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "runtime.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    tables = set(inspect(engine).get_table_names())

    assert "workflow_runs" in tables
    assert "instruments" in tables
    assert "market_bars" in tables
    assert "backtest_runs" in tables
    assert "paper_accounts" in tables
    assert "paper_runs" in tables
```

- [ ] **Step 2: Run migration test and verify failure**

Run:

```bash
python -m pytest tests/integration/test_migrations.py -q
```

Expected: FAIL because `alembic.ini` and revisions do not exist.

- [ ] **Step 3: Add `WorkflowRunORM` to metadata**

Modify `src/quant_trading/storage/models.py` imports:

```python
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
```

Add after `RiskDecisionORM`:

```python
class WorkflowRunORM(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    command_name: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    request_payload: Mapped[str] = mapped_column(Text, default="{}")
    result_payload: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Add Alembic config**

Create `alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = src
sqlalchemy.url = sqlite+pysqlite:///quant_trading.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5: Add Alembic environment**

Create `migrations/env.py`:

```python
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from quant_trading.storage.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Generate initial runtime schema revision**

Create `migrations/versions/`, then generate the initial revision from `Base.metadata` after `WorkflowRunORM` exists:

```bash
DATABASE_URL=sqlite+pysqlite:////private/tmp/quant-stage4-autogen-empty.sqlite3 \
  PYTHONPATH=src alembic revision --autogenerate \
  --rev-id 20260622_0001 \
  -m "initial runtime schema"
```

Rename the generated file to `migrations/versions/20260622_0001_initial_runtime_schema.py` if Alembic uses a different slug.

Open the revision and verify it contains static `op.create_table` calls for all current Stage 3 tables from `src/quant_trading/storage/models.py` plus `workflow_runs`. The file must not call `Base.metadata.create_all()`.

The `workflow_runs` section must contain these columns and indexes:

```python
op.create_table(
    "workflow_runs",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("command_name", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("request_payload", sa.Text(), nullable=False, server_default="{}"),
    sa.Column("result_payload", sa.Text(), nullable=False, server_default="{}"),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("created_object_type", sa.String(length=64), nullable=True),
    sa.Column("created_object_id", sa.Integer(), nullable=True),
    sa.Column("started_at", sa.DateTime(), nullable=False),
    sa.Column("finished_at", sa.DateTime(), nullable=True),
    sa.Column("duration_ms", sa.Integer(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
)
op.create_index("ix_workflow_runs_command_name", "workflow_runs", ["command_name"])
op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
```

The revision header must be:

```python
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260622_0001"
down_revision = None
branch_labels = None
depends_on = None
```

The downgrade order must drop dependent tables before parent tables and include at least this order:

```python
def downgrade() -> None:
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_command_name", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_table("risk_decisions")
    op.drop_table("portfolio_snapshots")
    op.drop_table("cash_ledger")
    op.drop_table("paper_positions")
    op.drop_table("paper_fills")
    op.drop_table("paper_orders")
    op.drop_table("paper_runs")
    op.drop_table("paper_accounts")
    op.drop_table("backtest_fills")
    op.drop_table("backtest_orders")
    op.drop_table("backtest_equity_points")
    op.drop_table("backtest_runs")
    op.drop_table("market_bars")
    op.drop_table("instruments")
```

- [ ] **Step 7: Run migration test**

Run:

```bash
python -m pytest tests/integration/test_migrations.py -q
```

Expected: PASS.

- [ ] **Step 8: Spec review for Task 2**

Check:

```bash
DATABASE_URL=sqlite+pysqlite:////private/tmp/quant-stage4-migration.sqlite3 PYTHONPATH=src alembic upgrade head
python - <<'PY'
from sqlalchemy import create_engine, inspect
engine = create_engine("sqlite+pysqlite:////private/tmp/quant-stage4-migration.sqlite3", future=True)
print(sorted(inspect(engine).get_table_names()))
PY
```

Required evidence:

- `workflow_runs`, existing read-model tables, backtest tables, and paper tables exist.
- `migrations/env.py` reads `DATABASE_URL`.
- Migration works from an empty SQLite database.

- [ ] **Step 9: Quality review for Task 2**

Check:

```bash
python -m pytest tests/integration/test_migrations.py -q
python -m py_compile src/quant_trading/storage/models.py migrations/env.py migrations/versions/20260622_0001_initial_runtime_schema.py
```

Inspect manually:

- The migration is static and deterministic.
- It does not import mutable ORM classes inside `upgrade()`.
- Index names match `downgrade()`.

- [ ] **Step 10: Commit Task 2**

Run:

```bash
git add alembic.ini migrations/env.py migrations/script.py.mako migrations/versions/20260622_0001_initial_runtime_schema.py tests/integration/test_migrations.py
git add src/quant_trading/storage/models.py
git commit -m "feat: add alembic runtime schema"
```

## Task 3: Workflow Run Repository And Runner

**Files:**

- Modify: `src/quant_trading/storage/repositories.py`
- Create: `src/quant_trading/workflows/runner.py`
- Test: `tests/integration/test_workflow_runner.py`

- [ ] **Step 1: Write focused workflow runner tests**

Create `tests/integration/test_workflow_runner.py`:

```python
import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.models import WorkflowRunORM
from quant_trading.workflows.runner import (
    WorkflowCommandRunner,
    record_failed_workflow_command,
    workflow_payload_dumps,
)


def make_engine_with_schema():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return engine


def workflow_runs(engine):
    with session_scope(engine) as session:
        return list(session.scalars(select(WorkflowRunORM).order_by(WorkflowRunORM.id)).all())


def test_runner_records_successful_command():
    engine = make_engine_with_schema()

    result = WorkflowCommandRunner(engine).run(
        "paper_create_account",
        {"name": "Audit Paper", "initial_cash": Decimal("100000")},
        lambda: {"account_id": 7, "name": "Audit Paper"},
    )

    assert result == {"account_id": 7, "name": "Audit Paper"}
    runs = workflow_runs(engine)
    assert len(runs) == 1
    run = runs[0]
    assert run.command_name == "paper_create_account"
    assert run.status == "succeeded"
    assert run.created_object_type == "paper_account"
    assert run.created_object_id == 7
    assert json.loads(run.request_payload)["initial_cash"] == "100000"
    assert json.loads(run.result_payload)["account_id"] == 7
    assert run.finished_at is not None
    assert run.duration_ms is not None


def test_runner_records_failed_command_and_reraises():
    engine = make_engine_with_schema()

    with pytest.raises(ValueError, match="no market bars found"):
        WorkflowCommandRunner(engine).run(
            "backtest_ma_cross",
            {"symbol": "NO_SUCH"},
            lambda: (_raise_value_error("no market bars found for symbol: NO_SUCH")),
        )

    run = workflow_runs(engine)[0]
    assert run.command_name == "backtest_ma_cross"
    assert run.status == "failed"
    assert "no market bars found" in run.error_message
    assert json.loads(run.result_payload) == {}


def test_record_failed_workflow_command_does_not_raise():
    engine = make_engine_with_schema()

    record_failed_workflow_command(
        engine,
        "paper_create_account",
        {"validation_error_count": 1},
        "request validation failed",
    )

    run = workflow_runs(engine)[0]
    assert run.command_name == "paper_create_account"
    assert run.status == "failed"
    assert run.error_message == "request validation failed"


def test_runner_serializes_decimal_values_as_strings():
    payload = json.loads(workflow_payload_dumps({"cash": Decimal("100000.00")}))

    assert payload == {"cash": "100000"}


def _raise_value_error(message: str):
    raise ValueError(message)
```

- [ ] **Step 2: Run workflow runner tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_workflow_runner.py -q
```

Expected: FAIL because `WorkflowRunRepository`, `WorkflowCommandRunner`, and `record_failed_workflow_command` do not exist.

- [ ] **Step 3: Add workflow run repository**

Modify `src/quant_trading/storage/repositories.py` imports:

```python
from datetime import datetime
from sqlalchemy import select
from quant_trading.storage.models import InstrumentORM, MarketBarORM, WorkflowRunORM
```

Add:

```python
class WorkflowRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_running(self, command_name: str, request_payload: str, started_at: datetime) -> WorkflowRunORM:
        row = WorkflowRunORM(
            command_name=command_name,
            status="running",
            request_payload=request_payload,
            result_payload="{}",
            started_at=started_at,
            created_at=started_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def mark_succeeded(
        self,
        row: WorkflowRunORM,
        result_payload: str,
        finished_at: datetime,
        duration_ms: int,
        created_object_type: str | None,
        created_object_id: int | None,
    ) -> WorkflowRunORM:
        row.status = "succeeded"
        row.result_payload = result_payload
        row.error_message = None
        row.finished_at = finished_at
        row.duration_ms = duration_ms
        row.created_object_type = created_object_type
        row.created_object_id = created_object_id
        self.session.flush()
        return row

    def mark_failed(
        self,
        row: WorkflowRunORM,
        error_message: str,
        finished_at: datetime,
        duration_ms: int,
    ) -> WorkflowRunORM:
        row.status = "failed"
        row.error_message = error_message
        row.finished_at = finished_at
        row.duration_ms = duration_ms
        self.session.flush()
        return row

    def list_recent(
        self,
        *,
        status: str | None = None,
        command_name: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRunORM]:
        statement = select(WorkflowRunORM).order_by(WorkflowRunORM.id.desc()).limit(limit)
        if status:
            statement = statement.where(WorkflowRunORM.status == status)
        if command_name:
            statement = statement.where(WorkflowRunORM.command_name == command_name)
        return list(self.session.scalars(statement).all())

    def get(self, workflow_run_id: int) -> WorkflowRunORM | None:
        return self.session.get(WorkflowRunORM, workflow_run_id)
```

- [ ] **Step 4: Add synchronous workflow runner**

Create `src/quant_trading/workflows/runner.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
import json
import time
from typing import Any, TypeVar

from sqlalchemy import Engine

from quant_trading.storage.db import session_scope
from quant_trading.storage.repositories import WorkflowRunRepository

T = TypeVar("T")

COMMAND_CREATED_OBJECTS = {
    "backtest_ma_cross": ("backtest_run", "run_id"),
    "paper_create_account": ("paper_account", "account_id"),
    "paper_start_ma_cross_run": ("paper_run", "run_id"),
    "paper_run_tick": ("paper_run", "run_id"),
}


class WorkflowCommandRunner:
    def __init__(self, engine: Engine):
        self.engine = engine

    def run(self, command_name: str, request_payload: dict[str, Any], callback: Callable[[], T]) -> T:
        started_at = datetime.utcnow()
        started_counter = time.perf_counter()
        with session_scope(self.engine) as session:
            run = WorkflowRunRepository(session).create_running(
                command_name=command_name,
                request_payload=workflow_payload_dumps(request_payload),
                started_at=started_at,
            )
            workflow_run_id = run.id

        try:
            result = callback()
        except Exception as exc:
            finished_at = datetime.utcnow()
            duration_ms = _duration_ms(started_counter)
            with session_scope(self.engine) as session:
                repo = WorkflowRunRepository(session)
                run = repo.get(workflow_run_id)
                if run is not None:
                    repo.mark_failed(
                        run,
                        error_message=sanitize_workflow_error(exc),
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                    )
            raise

        finished_at = datetime.utcnow()
        duration_ms = _duration_ms(started_counter)
        result_payload = result if isinstance(result, dict) else {"result": result}
        created_type, created_id = infer_created_object(command_name, result_payload)
        with session_scope(self.engine) as session:
            repo = WorkflowRunRepository(session)
            run = repo.get(workflow_run_id)
            if run is not None:
                repo.mark_succeeded(
                    run,
                    result_payload=workflow_payload_dumps(result_payload),
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    created_object_type=created_type,
                    created_object_id=created_id,
                )
        return result


def infer_created_object(command_name: str, result_payload: dict[str, Any]) -> tuple[str | None, int | None]:
    mapping = COMMAND_CREATED_OBJECTS.get(command_name)
    if not mapping:
        return None, None
    object_type, id_key = mapping
    raw_id = result_payload.get(id_key)
    return object_type, int(raw_id) if raw_id is not None else None


def workflow_payload_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True)


def sanitize_workflow_error(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message[:1000]


def record_failed_workflow_command(
    engine: Engine,
    command_name: str,
    request_payload: dict[str, Any],
    error_message: str,
) -> None:
    started_at = datetime.utcnow()
    started_counter = time.perf_counter()
    with session_scope(engine) as session:
        repo = WorkflowRunRepository(session)
        run = repo.create_running(
            command_name=command_name,
            request_payload=workflow_payload_dumps(request_payload),
            started_at=started_at,
        )
        repo.mark_failed(
            run,
            error_message=error_message[:1000],
            finished_at=datetime.utcnow(),
            duration_ms=_duration_ms(started_counter),
        )


def _duration_ms(started_counter: float) -> int:
    return max(0, int((time.perf_counter() - started_counter) * 1000))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
```

- [ ] **Step 5: Run workflow runner tests**

Run:

```bash
python -m pytest tests/integration/test_workflow_runner.py -q
```

Expected: PASS.

- [ ] **Step 6: Spec review for Task 3**

Check:

```bash
rg -n "WorkflowRunORM|WorkflowRunRepository|WorkflowCommandRunner|workflow_payload_dumps|record_failed_workflow_command" src tests
```

Required evidence:

- The data model has all fields from the Stage 4 spec.
- Runner creates `running`, then updates to `succeeded` or `failed`.
- Decimal/date/datetime payload values are JSON-safe.
- Created object mapping covers backtest, account, paper run, and tick commands.

- [ ] **Step 7: Quality review for Task 3**

Check:

```bash
python -m pytest tests/integration/test_workflow_runner.py -q
python -m py_compile src/quant_trading/storage/repositories.py src/quant_trading/workflows/runner.py
```

Inspect manually:

- Runner opens short database sessions and does not keep one session open while business logic runs.
- Error messages are bounded to 1000 characters.
- No auth token fields are accepted by or stored in runner payloads.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add src/quant_trading/storage/repositories.py src/quant_trading/workflows/runner.py tests/integration/test_workflow_runner.py
git commit -m "feat: record workflow command runs"
```

## Task 4: Command APIs And Workflow Run Read APIs

**Files:**

- Modify: `src/quant_trading/api/routes/workflows.py`
- Modify: `src/quant_trading/api/auth.py`
- Modify: `src/quant_trading/api/main.py`
- Test: `tests/integration/test_workflows_api.py`
- Test: `tests/integration/test_workflow_runs.py`
- Test: `tests/integration/test_runtime_auth.py`

- [ ] **Step 1: Create command audit integration tests**

Create `tests/integration/test_workflow_runs.py`:

```python
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from quant_trading.api.main import create_app
from quant_trading.config import AppSettings
from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.models import WorkflowRunORM


def make_client(require_auth: bool = False):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    settings = AppSettings(require_auth=require_auth, api_token="local-token")
    return TestClient(create_app(engine=engine, settings=settings)), engine


def workflow_runs(engine):
    with session_scope(engine) as session:
        return list(session.scalars(select(WorkflowRunORM).order_by(WorkflowRunORM.id)).all())


def test_successful_import_creates_succeeded_workflow_run(legacy_sqlite_db: Path):
    client, engine = make_client()

    response = client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    assert response.status_code == 200
    runs = workflow_runs(engine)
    assert len(runs) == 1
    run = runs[0]
    assert run.command_name == "import_legacy"
    assert run.status == "succeeded"
    assert run.error_message is None
    assert json.loads(run.request_payload)["legacy_db_path"] == str(legacy_sqlite_db)
    assert json.loads(run.result_payload) == {"imported_symbols": 1, "imported_bars": 121}
    assert run.finished_at is not None
    assert run.duration_ms is not None


def test_backtest_workflow_run_references_backtest_run(legacy_sqlite_db: Path):
    client, engine = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    response = client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "000001",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "initial_cash": "100000",
        },
    )

    assert response.status_code == 200
    run = workflow_runs(engine)[-1]
    assert run.command_name == "backtest_ma_cross"
    assert run.status == "succeeded"
    assert run.created_object_type == "backtest_run"
    assert run.created_object_id == response.json()["run_id"]


def test_paper_commands_record_created_objects(legacy_sqlite_db: Path):
    client, engine = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})
    account_response = client.post(
        "/workflows/paper/accounts",
        json={"name": "Audit Paper", "initial_cash": "100000"},
    )
    run_response = client.post(
        "/workflows/paper/runs/ma-cross",
        json={
            "account_id": account_response.json()["account_id"],
            "symbol": "000001",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
        },
    )
    tick_response = client.post(f"/workflows/paper/runs/{run_response.json()['run_id']}/tick")

    assert account_response.status_code == 200
    assert run_response.status_code == 200
    assert tick_response.status_code == 200
    by_command = {run.command_name: run for run in workflow_runs(engine)}
    assert by_command["paper_create_account"].created_object_type == "paper_account"
    assert by_command["paper_create_account"].created_object_id == account_response.json()["account_id"]
    assert by_command["paper_start_ma_cross_run"].created_object_type == "paper_run"
    assert by_command["paper_start_ma_cross_run"].created_object_id == run_response.json()["run_id"]
    assert by_command["paper_run_tick"].created_object_type == "paper_run"
    assert by_command["paper_run_tick"].created_object_id == tick_response.json()["run_id"]


def test_failed_unknown_symbol_backtest_creates_failed_workflow_run(legacy_sqlite_db: Path):
    client, engine = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    response = client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "NO_SUCH",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "initial_cash": "100000",
        },
    )

    assert response.status_code == 400
    run = workflow_runs(engine)[-1]
    assert run.command_name == "backtest_ma_cross"
    assert run.status == "failed"
    assert "no market bars found" in run.error_message
    assert json.loads(run.result_payload) == {}


def test_validation_failure_creates_failed_workflow_run_for_authorized_command():
    client, engine = make_client()

    response = client.post(
        "/workflows/paper/accounts",
        json={"name": "   ", "initial_cash": "100000"},
    )

    assert response.status_code in {400, 422}
    run = workflow_runs(engine)[0]
    assert run.command_name == "paper_create_account"
    assert run.status == "failed"
    assert run.error_message == "request validation failed"


def test_auth_failure_does_not_create_workflow_run():
    client, engine = make_client(require_auth=True)

    response = client.post(
        "/workflows/paper/accounts",
        json={"name": "Audit Paper", "initial_cash": "100000"},
    )

    assert response.status_code == 401
    assert workflow_runs(engine) == []
```

- [ ] **Step 2: Extend command API tests for run-history endpoints**

Append to `tests/integration/test_workflows_api.py`:

```python
def test_workflow_run_read_api_lists_and_gets_runs(legacy_sqlite_db: Path):
    client, _ = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    list_response = client.get("/workflows/runs")

    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["command_name"] == "import_legacy"
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["error_message"] is None
    assert rows[0]["result_payload"]["imported_bars"] == 121

    detail_response = client.get(f"/workflows/runs/{rows[0]['id']}")

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == rows[0]["id"]


def test_workflow_run_read_api_filters_by_status_and_command(legacy_sqlite_db: Path):
    client, _ = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})
    client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "NO_SUCH",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "initial_cash": "100000",
        },
    )

    response = client.get("/workflows/runs", params={"status": "failed", "command_name": "backtest_ma_cross"})

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["command_name"] == "backtest_ma_cross"


def test_workflow_run_read_api_returns_404_for_missing_run():
    client, _ = make_client()

    response = client.get("/workflows/runs/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "workflow run not found"
```

- [ ] **Step 3: Run workflow API tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_workflows_api.py tests/integration/test_workflow_runs.py -q
```

Expected: FAIL because command routes do not call the runner and read endpoints do not exist.

- [ ] **Step 4: Add payload and response helpers in workflow routes**

Modify `src/quant_trading/api/routes/workflows.py` imports:

```python
import json
from datetime import date, datetime
from typing import Any

from quant_trading.storage.db import session_scope
from quant_trading.storage.models import WorkflowRunORM
from quant_trading.storage.repositories import WorkflowRunRepository
from quant_trading.workflows.runner import WorkflowCommandRunner
```

Add helpers:

```python
def _runner(request: Request) -> WorkflowCommandRunner:
    return WorkflowCommandRunner(_engine(request))


def _workflow_run_payload(row: WorkflowRunORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "command_name": row.command_name,
        "status": row.status,
        "request_payload": _json_loads(row.request_payload),
        "result_payload": _json_loads(row.result_payload),
        "error_message": row.error_message,
        "created_object_type": row.created_object_type,
        "created_object_id": row.created_object_id,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "duration_ms": row.duration_ms,
        "created_at": _iso(row.created_at),
    }


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {"value": loaded}


def _iso(value: date | datetime | None) -> str | None:
    return None if value is None else value.isoformat()
```

- [ ] **Step 5: Wrap existing command route callbacks**

Modify the existing POST routes in `src/quant_trading/api/routes/workflows.py`:

```python
@router.post("/import-legacy")
def import_legacy(payload: ImportLegacyRequest, request: Request) -> dict:
    return _run_command(
        lambda: _runner(request).run(
            "import_legacy",
            payload.model_dump(mode="json"),
            lambda: import_legacy_data(_engine(request), payload.legacy_db_path),
        )
    )
```

Use the same pattern for:

```python
@router.post("/backtests/ma-cross")
def run_backtest(payload: MACrossBacktestRequest, request: Request) -> dict:
    return _run_command(
        lambda: _runner(request).run(
            "backtest_ma_cross",
            payload.model_dump(mode="json"),
            lambda: run_ma_cross_backtest(
                _engine(request),
                symbol=payload.symbol,
                short_window=payload.short_window,
                long_window=payload.long_window,
                order_size=payload.order_size,
                initial_cash=payload.initial_cash,
            ),
        )
    )


@router.post("/paper/accounts")
def create_account(payload: CreatePaperAccountRequest, request: Request) -> dict:
    return _run_command(
        lambda: _runner(request).run(
            "paper_create_account",
            payload.model_dump(mode="json"),
            lambda: create_paper_account(
                _engine(request),
                name=payload.name,
                initial_cash=payload.initial_cash,
                base_currency=payload.base_currency,
            ),
        )
    )


@router.post("/paper/runs/ma-cross")
def start_paper_run(payload: CreateMACrossPaperRunRequest, request: Request) -> dict:
    return _run_command(
        lambda: _runner(request).run(
            "paper_start_ma_cross_run",
            payload.model_dump(mode="json"),
            lambda: start_ma_cross_paper_run(
                _engine(request),
                account_id=payload.account_id,
                symbol=payload.symbol,
                short_window=payload.short_window,
                long_window=payload.long_window,
                order_size=payload.order_size,
                max_order_value=payload.max_order_value,
            ),
        )
    )


@router.post("/paper/runs/{run_id}/tick")
def run_tick(run_id: int, request: Request) -> dict:
    return _run_command(
        lambda: _runner(request).run(
            "paper_run_tick",
            {"run_id": run_id},
            lambda: run_paper_tick(_engine(request), run_id),
        )
    )
```

- [ ] **Step 6: Add workflow run read endpoints**

Add to `src/quant_trading/api/routes/workflows.py`:

```python
@router.get("/runs")
def list_workflow_runs(
    request: Request,
    status: str | None = None,
    command_name: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with session_scope(_engine(request)) as session:
        rows = WorkflowRunRepository(session).list_recent(
            status=status,
            command_name=command_name,
            limit=limit,
        )
        return [_workflow_run_payload(row) for row in rows]


@router.get("/runs/{workflow_run_id}")
def get_workflow_run(workflow_run_id: int, request: Request) -> dict[str, Any]:
    with session_scope(_engine(request)) as session:
        row = WorkflowRunRepository(session).get(workflow_run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="workflow run not found")
        return _workflow_run_payload(row)
```

- [ ] **Step 7: Add validation-error recording for workflow command paths**

Modify `src/quant_trading/api/auth.py` to expose command name inference:

```python
COMMAND_PATH_PATTERNS = [
    ("POST", "/workflows/import-legacy", "import_legacy"),
    ("POST", "/workflows/backtests/ma-cross", "backtest_ma_cross"),
    ("POST", "/workflows/paper/accounts", "paper_create_account"),
    ("POST", "/workflows/paper/runs/ma-cross", "paper_start_ma_cross_run"),
]


def workflow_command_name_for_path(method: str, path: str) -> str | None:
    if method == "POST" and path.startswith("/workflows/paper/runs/") and path.endswith("/tick"):
        return "paper_run_tick"
    for candidate_method, candidate_path, command_name in COMMAND_PATH_PATTERNS:
        if method == candidate_method and path == candidate_path:
            return command_name
    return None
```

Modify `src/quant_trading/api/main.py` to install a validation exception handler:

```python
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from quant_trading.api.auth import install_token_auth, workflow_command_name_for_path
from quant_trading.workflows.runner import record_failed_workflow_command


async def workflow_validation_exception_handler(request: Request, exc: RequestValidationError):
    command_name = workflow_command_name_for_path(request.method, request.url.path)
    if command_name and getattr(request.state, "authenticated", False):
        record_failed_workflow_command(
            request.app.state.engine,
            command_name,
            {"path": request.url.path, "validation_error_count": len(exc.errors())},
            "request validation failed",
        )
    return JSONResponse(status_code=400, content={"detail": jsonable_encoder(exc.errors())})
```

Then add in `create_app` before `return app`:

```python
app.add_exception_handler(RequestValidationError, workflow_validation_exception_handler)
```

- [ ] **Step 8: Run command API and workflow run tests**

Run:

```bash
python -m pytest tests/integration/test_workflows_api.py tests/integration/test_workflow_runs.py tests/integration/test_runtime_auth.py -q
```

Expected: PASS.

- [ ] **Step 9: Spec review for Task 4**

Check:

```bash
python -m pytest tests/integration/test_workflows_api.py tests/integration/test_workflow_runs.py tests/integration/test_runtime_auth.py -q
```

Required evidence:

- All Stage 3 command responses remain unwrapped.
- `GET /workflows/runs` returns newest workflow runs with payloads and timing fields.
- `GET /workflows/runs/{id}` returns one run or `404`.
- Failed unknown-symbol backtest creates a failed run.
- Authorized validation failure creates a failed run and still returns `400`.
- Auth failure still creates no workflow run because middleware returns before command execution.

- [ ] **Step 10: Quality review for Task 4**

Check:

```bash
python -m py_compile src/quant_trading/api/routes/workflows.py src/quant_trading/api/auth.py src/quant_trading/api/main.py
```

Inspect manually:

- `limit` is bounded to `1..100`.
- Query filters are exact match only.
- Response shape uses parsed JSON objects, not raw JSON strings.
- `HTTPException` mapping for `FileNotFoundError` and `ValueError` remains the same as Stage 3.

- [ ] **Step 11: Commit Task 4**

Run:

```bash
git add src/quant_trading/api/routes/workflows.py src/quant_trading/api/auth.py src/quant_trading/api/main.py tests/integration/test_workflows_api.py tests/integration/test_workflow_runs.py tests/integration/test_runtime_auth.py
git commit -m "feat: expose workflow run audit APIs"
```

## Task 5: Dashboard Workflow History

**Files:**

- Modify: `src/quant_trading/api/routes/dashboard.py`
- Test: `tests/integration/test_dashboard.py`
- Test: `tests/integration/test_workflow_runs.py`

- [ ] **Step 1: Extend dashboard tests**

Append to `tests/integration/test_dashboard.py`:

```python
def test_dashboard_displays_workflow_run_history(legacy_sqlite_db: Path):
    client, _ = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "Workflow Runs" in html
    assert "import_legacy" in html
    assert "succeeded" in html
    assert "Environment" in html
    assert "Auth" in html


def test_failed_dashboard_action_creates_visible_failed_workflow_run(legacy_sqlite_db: Path):
    client, _ = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    response = client.post(
        "/dashboard/actions/backtests/ma-cross",
        data={
            "symbol": "NO_SUCH",
            "short_window": "3",
            "long_window": "8",
            "order_size": "50",
            "initial_cash": "100000",
        },
    )

    assert response.status_code == 400
    assert "no market bars found" in response.text
    assert "Workflow Runs" in response.text
    assert "backtest_ma_cross" in response.text
    assert "failed" in response.text
```

- [ ] **Step 2: Run dashboard tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_dashboard.py -q
```

Expected: FAIL because dashboard does not render workflow history and dashboard actions do not use the runner.

- [ ] **Step 3: Import workflow runner and repository in dashboard**

Modify `src/quant_trading/api/routes/dashboard.py` imports:

```python
from quant_trading.storage.models import (
    BacktestRunORM,
    CashLedgerORM,
    InstrumentORM,
    MarketBarORM,
    PaperAccountORM,
    PaperFillORM,
    PaperOrderORM,
    PaperPositionORM,
    PaperRunORM,
    PortfolioSnapshotORM,
    RiskDecisionORM,
    WorkflowRunORM,
)
from quant_trading.storage.repositories import WorkflowRunRepository
from quant_trading.workflows.runner import WorkflowCommandRunner
```

- [ ] **Step 4: Run dashboard form actions through the workflow runner**

Replace `_run_dashboard_action` with:

```python
def _run_dashboard_action(
    request: Request,
    command_name: str,
    request_payload: dict[str, Any],
    callback: Callable[[], T],
    notice: str,
) -> HTMLResponse | RedirectResponse:
    try:
        WorkflowCommandRunner(request.app.state.engine).run(
            command_name,
            request_payload,
            callback,
        )
    except Exception as exc:
        return _dashboard_response(request, error=str(exc), status_code=400)
    return RedirectResponse(f"/dashboard?notice={quote(notice)}", status_code=303)
```

Update each dashboard action call. Example for backtests:

```python
return _run_dashboard_action(
    request,
    "backtest_ma_cross",
    {
        "symbol": str(form.get("symbol", "")),
        "short_window": str(form.get("short_window", "")),
        "long_window": str(form.get("long_window", "")),
        "order_size": str(form.get("order_size", "")),
        "initial_cash": str(form.get("initial_cash", "")),
    },
    lambda: run_ma_cross_backtest(
        request.app.state.engine,
        symbol=str(form.get("symbol", "")),
        short_window=int(str(form.get("short_window", ""))),
        long_window=int(str(form.get("long_window", ""))),
        order_size=int(str(form.get("order_size", ""))),
        initial_cash=Decimal(str(form.get("initial_cash", ""))),
    ),
    "Backtest started",
)
```

Use command names:

- `import_legacy`
- `backtest_ma_cross`
- `paper_create_account`
- `paper_start_ma_cross_run`
- `paper_run_tick`

Remove the manual blank-name early return in `dashboard_create_account`; let `create_paper_account()` raise so the runner records the failed command.

- [ ] **Step 5: Add workflow history and runtime state to dashboard state**

Modify `_collect_state`:

```python
settings = request.app.state.settings
return {
    "db_label": engine.url.render_as_string(hide_password=True),
    "app_env": settings.app_env,
    "auth_enabled": settings.require_auth,
    "instrument_count": session.scalar(select(func.count(InstrumentORM.id))) or 0,
    "latest_bar": session.scalar(select(func.max(MarketBarORM.timestamp))),
    "workflow_runs": WorkflowRunRepository(session).list_recent(limit=20),
    "backtests": _latest(session, BacktestRunORM),
    "accounts": _latest(session, PaperAccountORM),
    "runs": _latest(session, PaperRunORM),
    "positions": _latest(session, PaperPositionORM),
    "orders": _latest(session, PaperOrderORM),
    "fills": _latest(session, PaperFillORM),
    "risk_decisions": _latest(session, RiskDecisionORM),
    "ledger": _latest(session, CashLedgerORM),
    "snapshots": _latest(session, PortfolioSnapshotORM),
}
```

Update the meta section to include environment and auth:

```python
<section class="meta">
  <div class="metric"><span>Database</span>{_e(state["db_label"])}</div>
  <div class="metric"><span>Environment</span>{_e(state["app_env"])}</div>
  <div class="metric"><span>Auth</span>{_e("enabled" if state["auth_enabled"] else "disabled")}</div>
  <div class="metric"><span>Instruments</span>{_e(state["instrument_count"])}</div>
  <div class="metric"><span>Latest Imported Bar</span>{_e(state["latest_bar"] or "none")}</div>
</section>
```

- [ ] **Step 6: Render workflow runs table**

Add before the existing Backtest Runs table:

```python
{_table(
    "Workflow Runs",
    ["ID", "Command", "Status", "Started", "Duration", "Created Object", "Error"],
    state["workflow_runs"],
    lambda r: [
        f"#{r.id}",
        r.command_name,
        r.status,
        r.started_at,
        f"{r.duration_ms} ms" if r.duration_ms is not None else "",
        _object_ref(r),
        r.error_message or "",
    ],
)}
```

Add helper:

```python
def _object_ref(row: WorkflowRunORM) -> str:
    if not row.created_object_type or row.created_object_id is None:
        return ""
    return f"{row.created_object_type} #{row.created_object_id}"
```

Enhance row CSS by adding to the style block:

```css
.status-failed { color: #8a1f1f; font-weight: 600; }
```

Update `_table` to apply `status-failed` to cells whose value is exactly `failed`:

```python
cell_class = ' class="status-failed"' if value == "failed" else ""
f"<td{cell_class}>{_e(value)}</td>"
```

- [ ] **Step 7: Run dashboard tests**

Run:

```bash
python -m pytest tests/integration/test_dashboard.py tests/integration/test_workflow_runs.py -q
```

Expected: PASS.

- [ ] **Step 8: Spec review for Task 5**

Check:

```bash
python -m pytest tests/integration/test_dashboard.py -q
```

Required evidence:

- Dashboard renders recent workflow runs.
- Failed dashboard command returns HTML with status `400`.
- The failed command appears in the workflow history table.
- Dashboard displays environment and auth state but never displays token value.

- [ ] **Step 9: Quality review for Task 5**

Check:

```bash
python -m py_compile src/quant_trading/api/routes/dashboard.py
```

Inspect manually:

- Form values are captured as strings in request payloads.
- Int/Decimal conversion happens inside the runner callback, so conversion failures are recorded.
- The server-rendered dashboard remains dependency-free.

- [ ] **Step 10: Commit Task 5**

Run:

```bash
git add src/quant_trading/api/routes/dashboard.py tests/integration/test_dashboard.py tests/integration/test_workflow_runs.py
git commit -m "feat: show workflow run history on dashboard"
```

## Task 6: Documentation And Final Verification

**Files:**

- Modify: `README.md`
- Test: full suite and Docker Compose config.

- [ ] **Step 1: Update README runtime configuration section**

Add a section named `Production Runtime And Safety MVP` to `README.md`:

```markdown
## Production Runtime And Safety MVP

Stage 4 hardens the local operations workbench for protected paper-trading use. It still does not place real broker orders.

| Variable | Default | Purpose |
| --- | --- | --- |
| `QUANT_APP_ENV` | `local` | Environment label shown in the dashboard. |
| `DATABASE_URL` | `sqlite+pysqlite:///quant_trading.db` | SQLAlchemy database URL used by the API and Alembic. |
| `QUANT_REQUIRE_AUTH` | `false` | Enables token protection for dashboard, read APIs, and workflow commands. |
| `QUANT_API_TOKEN` | empty | Required when `QUANT_REQUIRE_AUTH=true`. |
| `QUANT_AUTH_HEADER` | `Authorization` | Optional custom header name. `Authorization: Bearer ...` and `X-API-Token` are always supported. |
| `QUANT_PUBLIC_ROUTES` | `/health` | Comma-separated public paths. |

Protected local run:

```bash
QUANT_REQUIRE_AUTH=true QUANT_API_TOKEN=local-token \
PYTHONPATH=src python -m uvicorn --factory quant_trading.api.main:create_app \
  --host 127.0.0.1 --port 8000
```

Authenticated examples:

```bash
curl -H "Authorization: Bearer local-token" http://127.0.0.1:8000/dashboard
curl -H "X-API-Token: local-token" http://127.0.0.1:8000/workflows/runs
```

Schema migration:

```bash
DATABASE_URL=sqlite+pysqlite:///quant_trading.db PYTHONPATH=src alembic upgrade head
```

`create_all()` remains useful for tests and quick local experiments. Production-like local runs should use Alembic so schema state is explicit. Older SQLite files created before this migration stage may need backup and recreation or a manual migration.
```

- [ ] **Step 2: Document workflow run audit records**

Add:

```markdown
Workflow command APIs and dashboard actions write audit rows to `workflow_runs`.

Tracked commands:

- `import_legacy`
- `backtest_ma_cross`
- `paper_create_account`
- `paper_start_ma_cross_run`
- `paper_run_tick`

Read audit history:

```bash
curl -H "Authorization: Bearer local-token" http://127.0.0.1:8000/workflows/runs
curl -H "Authorization: Bearer local-token" http://127.0.0.1:8000/workflows/runs/1
```

Audit rows include status, summarized request payload, result payload, error message, created object reference, start time, finish time, and duration. API tokens are never stored in workflow payloads.
```

- [ ] **Step 3: Run focused regression tests**

Run:

```bash
python -m pytest \
  tests/unit/test_settings.py \
  tests/integration/test_runtime_auth.py \
  tests/integration/test_migrations.py \
  tests/integration/test_workflows_api.py \
  tests/integration/test_workflow_runs.py \
  tests/integration/test_dashboard.py \
  tests/integration/test_operations_workflow_e2e.py \
  tests/integration/test_paper_lifecycle.py \
  tests/integration/test_paper_jobs.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 5: Run Compose config check**

Run:

```bash
docker compose config
```

Expected: command exits `0` and renders the Compose configuration.

- [ ] **Step 6: Optional local protected-mode smoke**

Run:

```bash
DATABASE_URL=sqlite+pysqlite:////private/tmp/quant-stage4-smoke.sqlite3 \
QUANT_REQUIRE_AUTH=true \
QUANT_API_TOKEN=local-token \
PYTHONPATH=src python -m uvicorn --factory quant_trading.api.main:create_app \
  --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/dashboard
curl -i -H "Authorization: Bearer local-token" http://127.0.0.1:8000/dashboard
```

Expected:

- `/health` returns `200`.
- unauthenticated `/dashboard` returns `401`.
- authenticated `/dashboard` returns `200`.

- [ ] **Step 7: Spec review for Task 6**

Check all Stage 4 acceptance criteria against evidence:

```bash
python -m pytest -q
docker compose config
rg -n "Production Runtime And Safety MVP|QUANT_REQUIRE_AUTH|alembic upgrade head|workflow_runs|does not place real" README.md
```

Required evidence:

- Auth and migrations are documented.
- README states this is still paper trading and no real orders are placed.
- Full test suite and Compose config pass.

- [ ] **Step 8: Quality review for Task 6**

Review:

```bash
git diff -- README.md
git diff --stat
```

Inspect manually:

- README commands include `PYTHONPATH=src`.
- No token examples use a real secret.
- No unrelated files are changed.

- [ ] **Step 9: Commit Task 6**

Run:

```bash
git add README.md
git commit -m "docs: document production runtime safety"
```

## Final Stage 4 Gate

- [ ] **Step 1: Run final verification**

Run from the quant worktree:

```bash
python -m pytest -q
docker compose config
git status --short
```

Expected:

- `python -m pytest -q` passes.
- `docker compose config` exits `0`.
- `git status --short` is clean after commits.

- [ ] **Step 2: Two-round final review**

Spec review:

- Confirm every Stage 4 goal from `docs/superpowers/specs/2026-06-22-quant-trading-production-runtime-design.md` maps to tests, code, or README.
- Confirm non-goals remain out of scope: no real broker, no async queue, no scheduler, no multi-user auth, no OAuth, no frontend framework.

Quality review:

- Confirm route handlers are thin and business logic stays in `workflows.operations`.
- Confirm workflow runner owns audit state transitions.
- Confirm dashboard errors are escaped by `_e()`.
- Confirm auth token is not logged, rendered, or stored in workflow payloads.
- Confirm Alembic migration and ORM agree on the `workflow_runs` schema.

- [ ] **Step 3: Push implementation branch when user confirms**

Run only after user asks to upload/push:

```bash
git push origin codex/quant-operations-workbench-v3
```

## Execution Options

Recommended execution mode:

1. **Subagent-Driven** - Dispatch one fresh subagent per task, then perform the required Spec review and quality review after each task.
2. **Inline Execution** - Execute this plan in-session using checkpoints and the same two-review gate after each task.

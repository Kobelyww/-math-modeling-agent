# Quant Trading Production Runtime And Safety Design

Date: 2026-06-22
Status: Ready for user review
Scope: Stage 4 for `quant-trading`: harden the Stage 3 operations workbench into a safer, auditable, migration-ready local paper-trading platform before adding broker adapters or broader market-data ingestion.

## Context

Stage 3 made the core local workflow usable:

```text
import legacy data -> run MA Cross backtest -> create paper account/run -> trigger paper tick -> inspect results
```

It added synchronous workflow command APIs, a server-rendered `/dashboard`, HTTP end-to-end workflow coverage, and README instructions. That is enough for a local operator to run the product loop, but not enough for a platform that can safely move toward real-market usage.

Current gaps that block the next level of product readiness:

- Command APIs and dashboard actions are unauthenticated.
- Existing database lifecycle still relies on `create_all()`, which creates missing tables but does not safely upgrade existing databases.
- Workflow commands return HTTP responses but do not persist an auditable command execution history.
- Failed imports, failed backtests, and failed paper ticks are not visible as first-class operational records.
- The dashboard shows trading state, but not command execution history, duration, failure messages, or result ids.
- There is no durable runtime settings layer that clearly controls local vs protected operation.

Stage 4 should solve those platform-runtime gaps while keeping real-money trading out of scope.

## Goals

- Add an explicit runtime settings layer for environment-driven production behavior.
- Add token-based protection for command APIs and dashboard surfaces.
- Add Alembic migration infrastructure and a first migration that represents the current schema plus Stage 4 additions.
- Persist workflow command runs for imports, backtests, paper account creation, paper run creation, and paper ticks.
- Record command status, input summary, result payload, error message, start time, finish time, and duration.
- Make command failure auditable even when the HTTP request returns a non-2xx response.
- Show workflow run history and failures in the dashboard.
- Preserve synchronous command execution for this stage, but make the data model compatible with future queued execution.
- Keep Stage 3 command response contracts stable where possible.
- Keep all existing read APIs and paper-trading invariants working.
- Document secure local operation and migration usage in the README.

## Non-Goals

- No real broker, exchange, or live order placement.
- No asynchronous worker orchestration in this stage.
- No automatic scheduler daemon.
- No multi-user account model or role-based authorization.
- No OAuth, session cookies, password login, or browser user management.
- No arbitrary Python strategy upload.
- No new frontend framework.
- No broad market-data provider expansion; that is a separate data-source stage.

## Recommended Approach

Use a production-runtime hardening stage:

1. Introduce `AppSettings` for database URL, auth behavior, API token, environment label, and public-route policy.
2. Add a FastAPI dependency/middleware layer that protects the dashboard, read APIs, and command APIs when auth is enabled.
3. Add Alembic to the runtime workflow with a repository-local migration environment.
4. Add a `workflow_runs` table for synchronous command audit records.
5. Wrap existing workflow command execution in a small command recorder that writes `running`, `succeeded`, and `failed` states.
6. Extend dashboard state to include recent workflow runs and failure messages.

This is the most direct path from local demo toward a platform that can be trusted operationally. It avoids prematurely building broker integrations before the platform can answer basic production questions:

- Who is allowed to trigger commands?
- What command ran?
- What input did it receive?
- Did it succeed or fail?
- Which persistent object did it create?
- What database schema version is expected?

Rejected alternatives:

- **Broker adapter first:** exciting, but unsafe without auth, migrations, and audit records.
- **Async queue first:** useful later, but adding queue semantics before durable command records makes failure diagnosis harder.
- **Full user login system:** too large for this stage; a single API token is enough for protected local and private deployments.
- **Data-source expansion first:** valuable, but it increases operational volume before the platform can track command history and failures.

## Architecture

Stage 4 adds runtime safety and command auditability around the existing workflow layer.

```text
FastAPI app
  api/main.py                    app factory, settings, route wiring
  api/auth.py                    token auth dependency and route policy
  api/routes/workflows.py        command APIs wrapped with workflow run recording
  api/routes/dashboard.py        dashboard plus recent workflow run history
  api/routes/*                   read APIs protected when auth is enabled

Runtime and persistence
  config.py                      AppSettings loaded from environment
  workflows/operations.py        existing command business logic
  workflows/runner.py            command run recorder and sync execution wrapper
  storage/models.py              WorkflowRunORM
  storage/repositories.py        workflow run query helpers
  migrations/                    Alembic environment and revisions
```

Command routes should remain thin. They validate request payloads, call the workflow runner, and return the underlying command result. The workflow runner owns audit state transitions and exception recording.

## Runtime Settings

Add a settings object using `pydantic-settings`, which is already a dependency.

Environment variables:

```text
QUANT_APP_ENV=local
DATABASE_URL=sqlite+pysqlite:///quant_trading.db
QUANT_REQUIRE_AUTH=false
QUANT_API_TOKEN=
QUANT_AUTH_HEADER=Authorization
QUANT_PUBLIC_ROUTES=/health
```

Rules:

- `QUANT_REQUIRE_AUTH=false` keeps local development friction low.
- `QUANT_REQUIRE_AUTH=true` requires `QUANT_API_TOKEN` to be set and non-empty at app startup.
- When auth is enabled, requests must provide one of:
  - `Authorization: Bearer <token>`
  - `X-API-Token: <token>`
- `/health` stays public.
- `/dashboard`, dashboard actions, workflow command APIs, and read APIs require auth when enabled.
- Auth failures return `401` with a generic message.
- Auth must not log or render token values.

The dashboard should display the app environment label and whether auth is enabled, but never display the token.

## Alembic Migration Design

Add repository-local Alembic infrastructure:

```text
alembic.ini
migrations/env.py
migrations/script.py.mako
migrations/versions/<revision>_initial_runtime_schema.py
```

The migration environment should:

- Import `quant_trading.storage.models.Base.metadata`.
- Read `DATABASE_URL` from environment.
- Work for SQLite and PostgreSQL.
- Support `alembic upgrade head`.

The first migration should create all current Stage 3 tables plus the new `workflow_runs` table. It does not need to support migrating arbitrary legacy hand-created databases in this stage, but README must clearly document:

- New deployments should run `alembic upgrade head`.
- Existing local SQLite databases created by older `create_all()` may need backup/recreate or manual migration.
- `create_all()` remains acceptable for tests, but production-like local runs should use Alembic.

## Workflow Run Data Model

Add `WorkflowRunORM`.

```text
id
command_name
status
request_payload
result_payload
error_message
created_object_type
created_object_id
started_at
finished_at
duration_ms
created_at
```

Command names for this stage:

```text
import_legacy
backtest_ma_cross
paper_create_account
paper_start_ma_cross_run
paper_run_tick
```

Statuses:

```text
running
succeeded
failed
```

Payload rules:

- `request_payload` is JSON text.
- `result_payload` is JSON text.
- Large or sensitive values should be summarized.
- API tokens must never be stored.
- `legacy_db_path` may be stored because this is a local file path, but errors should not expose secrets.
- Decimal values should be stored as strings.

Created object mapping:

- `backtest_ma_cross` sets `created_object_type = "backtest_run"` and `created_object_id = run_id`.
- `paper_create_account` sets `created_object_type = "paper_account"` and `created_object_id = account_id`.
- `paper_start_ma_cross_run` sets `created_object_type = "paper_run"` and `created_object_id = run_id`.
- `paper_run_tick` sets `created_object_type = "paper_run"` and `created_object_id = run_id`.
- `import_legacy` may leave created object fields empty and use result counts.

## Workflow Runner

Add a synchronous workflow runner.

Responsibilities:

- Create a `workflow_runs` row with `running` before command execution.
- Execute the existing command callback.
- On success:
  - persist result payload,
  - infer created object type/id,
  - set status to `succeeded`,
  - set `finished_at` and `duration_ms`.
- On expected failure:
  - persist a sanitized error message,
  - set status to `failed`,
  - set `finished_at` and `duration_ms`,
  - re-raise the exception so existing HTTP status mapping still works.
- On unexpected failure:
  - persist the failure,
  - re-raise the exception.

The runner should not know strategy internals. It records commands and delegates actual business behavior to `workflows.operations`.

## Command API Changes

Existing Stage 3 endpoint paths remain stable:

```http
POST /workflows/import-legacy
POST /workflows/backtests/ma-cross
POST /workflows/paper/accounts
POST /workflows/paper/runs/ma-cross
POST /workflows/paper/runs/{run_id}/tick
```

Each route should execute through the workflow runner.

Responses should remain the command result payload, not a wrapper, to avoid breaking Stage 3 clients.

Add read endpoints:

```http
GET /workflows/runs
GET /workflows/runs/{workflow_run_id}
```

`GET /workflows/runs` supports optional filters:

```text
status
command_name
limit
```

Default ordering: newest first.

The response includes command name, status, object reference, timing fields, error message, and result summary.

## Dashboard Changes

The dashboard should add an operations history section:

- Recent workflow runs table.
- Status, command name, started time, duration, created object, and error message.
- Visible failure state for failed commands.
- Auth enabled/disabled indicator.
- App environment label.

Dashboard action behavior:

- Success still redirects to `/dashboard` with a notice.
- Failure returns status `400` with dashboard HTML and visible error text.
- The failed command also appears in the workflow history table.

The UI remains server-rendered and operational. This stage should not introduce a frontend build chain.

## Error Handling

Expected command failures:

- Invalid input: `400`
- Missing account/run/symbol/data: `400` or `404` based on existing route policy
- Missing legacy import path: `404`
- Unauthorized: `401`

Every command failure after auth succeeds should create a failed `workflow_runs` row.

Auth failures should not create workflow run rows because no command was authorized.

Unexpected errors may still return `500` in local development, but should persist a failed workflow run when they happen inside a command execution wrapper.

## Testing Strategy

Stage 4 requires tests at five levels.

### Settings Tests

Required coverage:

- Defaults produce local unauthenticated mode.
- `QUANT_REQUIRE_AUTH=true` without token fails app startup or settings validation.
- Token values are not included in settings string representations.

### Auth Tests

Required coverage:

- `/health` is public.
- `/dashboard` requires auth when enabled.
- `/workflows/import-legacy` requires auth when enabled.
- Existing read APIs require auth when enabled.
- `Authorization: Bearer <token>` succeeds.
- `X-API-Token: <token>` succeeds.
- Wrong or missing token returns `401`.

### Migration Tests

Required coverage:

- Alembic configuration loads metadata.
- `alembic upgrade head` works against a temporary SQLite database.
- The upgraded database includes `workflow_runs` and key existing tables.

### Workflow Run Tests

Required coverage:

- Successful import creates a succeeded workflow run with result counts.
- Successful backtest creates a succeeded workflow run referencing `backtest_run`.
- Successful paper account creation references `paper_account`.
- Successful paper run creation references `paper_run`.
- Successful paper tick references `paper_run`.
- Failed unknown-symbol backtest creates a failed workflow run with error message.
- Failed dashboard action creates a failed workflow run visible on `/dashboard`.
- Auth failures do not create workflow run rows.

### Regression Tests

Required coverage:

- Existing Stage 3 HTTP end-to-end workflow still passes.
- Paper tick idempotency remains intact.
- Command API response payloads remain backward compatible.
- `python -m pytest -q` passes.
- `docker compose config` passes.

## Documentation

README should add:

- Environment variable table for auth and app settings.
- Local protected-mode example:

```bash
QUANT_REQUIRE_AUTH=true QUANT_API_TOKEN=local-token \
PYTHONPATH=src python -m uvicorn --factory quant_trading.api.main:create_app --host 127.0.0.1 --port 8000
```

- Example authenticated curl:

```bash
curl -H "Authorization: Bearer local-token" http://127.0.0.1:8000/dashboard
```

- Alembic usage:

```bash
DATABASE_URL=sqlite+pysqlite:///quant_trading.db alembic upgrade head
```

- Explanation that `create_all()` is for tests and simple local experimentation, while Alembic is the upgrade path for production-like runs.
- Explicit reminder that this platform still does not place real orders.

## Acceptance Criteria

- Auth can be enabled with environment variables and protects dashboard, command APIs, and read APIs while leaving `/health` public.
- Missing token or wrong token returns `401`.
- Correct bearer token and `X-API-Token` both work.
- Alembic can create the schema on an empty SQLite database.
- All workflow command routes persist `workflow_runs` records for success and failure.
- Command API response shapes remain compatible with Stage 3.
- Dashboard displays recent workflow run history and failed command messages.
- Failed dashboard commands are visible in workflow history.
- Stage 3 HTTP workflow test still passes.
- `python -m pytest -q` passes.
- `docker compose config` passes.
- README documents auth, migrations, and local-only paper-trading safety boundaries.

## Residual Risks

- Synchronous commands can still block the API process on large imports or backtests. The workflow run table makes this visible but does not solve queueing.
- A single API token is not a multi-user security model. It is acceptable for private/local deployment but not for public SaaS.
- Dashboard error rendering remains intentionally direct for local operations. A public deployment needs sanitized error presentation.
- Alembic migration coverage starts from the current productized schema. Older ad hoc SQLite files may require manual handling.
- Real broker integration remains blocked until auth, migrations, audit history, and paper command contracts are stable.

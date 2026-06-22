# Quant Trading Operations Workbench Design

Date: 2026-06-22
Status: Ready for user review
Scope: Stage 3 for `quant-trading`: turn the existing research and persistent paper-trading backend into an operator-usable workflow through command APIs and a lightweight server-rendered dashboard.

## Context

Stage 1 rebuilt the project into a product-shaped Python package with normalized storage, legacy data import, a portfolio backtest engine, risk rules, FastAPI read routes, Docker Compose, and legacy Django code moved under `legacy/`.

Stage 2 added persistent paper-trading accounts and runs:

- Paper accounts, runs, orders, fills, positions, cash ledger rows, risk decisions, and snapshots.
- Explicit lifecycle methods: `create_account()`, `start_run()`, and `run_one_tick(run_id, ...)`.
- Idempotent tick processing and account-level locking for paper run execution.
- Read APIs for paper accounts, runs, positions, ledger, orders, fills, risk decisions, and snapshots.
- A paper tick job wrapper for persisted MA Cross paper runs.

The platform is still not operator-usable as a product workflow. A developer can call Python functions or read APIs, but a user cannot complete the core loop from a browser or a small set of command endpoints:

```text
import data -> run backtest -> create paper account/run -> run tick -> inspect results
```

Stage 3 should make that loop real without adding premature broker integration, a full frontend framework, or arbitrary strategy execution.

## Goals

- Provide command APIs for the core workflow:
  - Import the legacy SQLite data source into the normalized schema.
  - Run a MA Cross backtest.
  - Create a paper account.
  - Create a MA Cross paper run with explicit parameters.
  - Trigger one paper tick for an existing run.
- Provide a lightweight operations dashboard that exposes the same workflow through browser forms and status tables.
- Keep all commands auditable by returning persisted ids and summary fields.
- Preserve existing read APIs and paper-trading invariants.
- Keep execution synchronous in this milestone so the workflow is deterministic and easy to test.
- Document a local end-to-end workflow in the README.

## Non-Goals

- No real broker or exchange order placement.
- No automatic scheduler daemon.
- No arbitrary Python strategy upload or execution.
- No full React or Next.js frontend.
- No multi-strategy or multi-symbol paper execution beyond the existing single-symbol MA Cross path.
- No authentication or multi-user authorization in this milestone.
- No Alembic migration implementation in this milestone, though README should continue to warn that `create_all()` does not alter existing databases.

## Recommended Approach

Use route A: add command APIs plus a server-rendered FastAPI dashboard.

This is the fastest path from backend capability to a usable local product loop. The current stack already has FastAPI, SQLAlchemy, task functions, tests, and Docker Compose. A server-rendered dashboard avoids a frontend build step and keeps the milestone focused on operational workflow instead of UI infrastructure.

Rejected alternatives:

- Full React frontend: useful later, but premature while the command contracts are still settling.
- RQ-first asynchronous workflow: realistic later, but it adds queue state, polling, and failure recovery before the synchronous workflow is proven.
- CLI-only operations: simpler to implement, but it does not make the platform feel like a product or help inspect state visually.

## Architecture

Stage 3 adds two new API surfaces while reusing existing engines and repositories.

```text
FastAPI app
  api/routes/workflows.py   command APIs for import/backtest/paper actions
  api/routes/dashboard.py   server-rendered operator page
  api/routes/paper.py       existing persisted read APIs
  api/routes/backtests.py   existing backtest read APIs
  jobs/tasks.py             reusable synchronous task functions
```

The command routes should stay thin. They validate request payloads, call existing task or engine code, and return persisted ids plus summaries. They should not duplicate backtest or paper execution logic.

The dashboard should use the same database state as the API routes. It can submit HTML forms directly to command endpoints and display compact tables by querying ORM rows server-side. It should be an operational console, not a marketing page.

## Command API Design

All Stage 3 command endpoints are synchronous and return JSON.

### Import Legacy Data

```http
POST /workflows/import-legacy
```

Request body:

```json
{
  "legacy_db_path": "legacy/django_app/db.sqlite3"
}
```

Response:

```json
{
  "imported_symbols": 1,
  "imported_bars": 121
}
```

The endpoint uses the current application database engine and calls `import_legacy_sqlite()`. It must not require callers to provide a database URL because the API already owns the runtime engine.

### Run MA Cross Backtest

```http
POST /workflows/backtests/ma-cross
```

Request body:

```json
{
  "symbol": "000001",
  "short_window": 5,
  "long_window": 20,
  "order_size": 100,
  "initial_cash": "100000"
}
```

Response:

```json
{
  "run_id": 1,
  "symbol": "000001",
  "strategy_name": "ma_cross",
  "final_equity": "100123.45",
  "equity_points": 121
}
```

Validation rules:

- `short_window > 0`
- `long_window > short_window`
- `order_size > 0`
- `initial_cash > 0`

The endpoint should construct `MACrossStrategy` with the request parameters and call `BacktestEngine.run()`.

### Create Paper Account

```http
POST /workflows/paper/accounts
```

Request body:

```json
{
  "name": "Local Paper",
  "initial_cash": "100000",
  "base_currency": "CNY"
}
```

Response:

```json
{
  "account_id": 1,
  "name": "Local Paper",
  "initial_cash": "100000",
  "base_currency": "CNY"
}
```

Validation rules:

- `name` must be non-empty after trimming.
- `initial_cash > 0`.
- `base_currency` defaults to `CNY`.

### Create MA Cross Paper Run

```http
POST /workflows/paper/runs/ma-cross
```

Request body:

```json
{
  "account_id": 1,
  "symbol": "000001",
  "short_window": 5,
  "long_window": 20,
  "order_size": 100,
  "max_order_value": "100000"
}
```

Response:

```json
{
  "run_id": 1,
  "account_id": 1,
  "symbol": "000001",
  "strategy_name": "ma_cross",
  "status": "running"
}
```

The endpoint should create `MACrossStrategy` and call `PaperTradingEngine.start_run()` with `StrategyStatus.APPROVED`. The strategy parameters must be persisted through the existing Stage 2 `strategy_config` behavior so the paper tick job can reconstruct the same strategy.

### Run One Paper Tick

```http
POST /workflows/paper/runs/{run_id}/tick
```

Response:

```json
{
  "run_id": 1,
  "account_id": 1,
  "processed_at": "2026-05-01",
  "orders_created": 1,
  "orders_filled": 1,
  "orders_rejected": 0,
  "fills_created": 1,
  "snapshot_created": true,
  "risk_decision_count": 1,
  "idempotent_noop": false
}
```

The endpoint should call the existing `run_paper_tick_task()` using the app database URL when available, or a shared helper that runs the same reconstruction logic against the app engine. The design must avoid building a separate code path with different strategy defaults.

## Dashboard Design

The dashboard is a single server-rendered page:

```http
GET /dashboard
```

It should show:

- Service status and database URL label.
- Instrument count and latest imported bar date.
- Backtest runs table with id, symbol, strategy, final equity, status.
- Paper accounts table with id, name, base currency, initial cash, status.
- Paper runs table with id, account id, symbol, strategy, status, last processed date.
- Latest paper positions, orders, fills, risk decisions, cash ledger rows, and snapshots.

It should include forms for:

- Import legacy data.
- Run MA Cross backtest.
- Create paper account.
- Create MA Cross paper run.
- Trigger one paper tick for a run.

The UI should be dense and operational:

- No landing-page hero.
- No decorative cards nested inside cards.
- Tables should be compact and scan-friendly.
- Forms should have clear labels, default values, and submit buttons.
- Error messages should be shown as plain operational feedback.

The first dashboard may use inline CSS inside a template file to avoid a frontend build chain. If static assets are introduced later, they should live under `src/quant_trading/api/static/`.

## Error Handling

Command endpoints should convert expected domain errors into HTTP responses:

- Missing account, run, symbol, or market bars: `404` or `400` with a clear message.
- Invalid parameters: `422` through request validation where possible.
- Unsupported strategy for job execution: `400`.
- Unexpected execution errors: let FastAPI return `500` in local development.

The dashboard should show command errors without hiding the underlying message. This is a local operations console, so clarity matters more than polished abstraction.

## Testing Strategy

Stage 3 must add tests at three levels.

### Command API Tests

Use `TestClient(create_app(engine))` with an in-memory SQLite database.

Required coverage:

- Import legacy data endpoint imports the fixture and returns counts.
- MA Cross backtest endpoint creates a persisted run.
- Paper account endpoint creates an account and initial deposit ledger.
- MA Cross paper run endpoint persists strategy config.
- Paper tick endpoint creates or no-ops as expected.
- Invalid command payloads return non-2xx responses.

### Dashboard Tests

Required coverage:

- `GET /dashboard` returns `200`.
- HTML includes the main workflow forms.
- HTML includes data from seeded accounts/runs/backtests.

### End-to-End Workflow Test

Required coverage:

```text
POST import legacy
POST run backtest
POST create paper account
POST create paper run
POST run tick
GET paper account/run/order/fill/position/ledger/risk/snapshot APIs
GET dashboard
```

The test proves a local user can complete the core workflow without calling internal Python functions.

## Documentation

README should add a "Run The Workbench" section:

```bash
python -m uvicorn quant_trading.api.main:app --host 127.0.0.1 --port 8000
```

Then point users to:

```text
http://127.0.0.1:8000/dashboard
```

README should include the command API endpoints and a short local workflow example.

## Acceptance Criteria

- A local user can open `/dashboard` and complete the core workflow through browser forms.
- A test can complete the same workflow through HTTP command APIs.
- Existing read APIs still work.
- Paper tick idempotency still holds when triggered through the command API.
- `python -m pytest -q` passes.
- `docker compose config` passes.
- The work remains limited to local research and paper trading; README does not imply real-money readiness.

## Residual Risks

- Synchronous commands can block the API process for larger datasets. This is acceptable for the MVP and should be replaced by queued jobs later.
- There is no authentication. This is acceptable for local use only; deployment must add auth before exposing command endpoints.
- The dashboard is intentionally simple. It should prove workflow usability before investing in a full frontend.

# Quant Trading Operations Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local operations workbench where a user can import legacy market data, run a MA Cross backtest, create a paper account/run, trigger one paper tick, and inspect results through HTTP APIs and a lightweight FastAPI dashboard.

**Architecture:** Add a thin workflow service layer that owns command execution and is reused by job tasks, API routes, and dashboard actions. Keep the API synchronous for this milestone, keep MA Cross as the only supported command strategy, and render the dashboard server-side without adding a frontend build chain.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, existing backtest/paper/risk engines, pytest, Docker Compose.

---

## Baseline And Working Directory

Implement from the Stage 2 quant repo branch:

```text
/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading/.worktrees/quant-paper-account-v2
```

Before implementation, create an isolated Stage 3 worktree from `codex/quant-paper-account-v2` using `superpowers:using-git-worktrees`; do not implement directly in the root checkout or touch the user-owned dirty file `legacy/django_app/quant_web/settings.py`.

All paths below are relative to the quant repo worktree unless explicitly stated.

## File Structure

Create:

- `src/quant_trading/workflows/__init__.py` exports workflow functions.
- `src/quant_trading/workflows/operations.py` contains reusable synchronous workflow commands and payload formatting.
- `src/quant_trading/api/routes/workflows.py` exposes JSON command APIs under `/workflows/...`.
- `src/quant_trading/api/routes/dashboard.py` renders `/dashboard` and handles HTML form actions by calling the workflow service layer.
- `tests/integration/test_workflows_service.py` covers the service layer and job reuse path.
- `tests/integration/test_workflows_api.py` covers command API validation and responses.
- `tests/integration/test_dashboard.py` covers dashboard rendering and form workflow actions.
- `tests/integration/test_operations_workflow_e2e.py` proves the whole HTTP workflow.

Modify:

- `src/quant_trading/jobs/tasks.py` to delegate import, MA Cross backtest, and paper tick execution to the workflow service layer.
- `src/quant_trading/api/main.py` to include `workflows.router` and `dashboard.router`.
- `README.md` to document the local workbench, command APIs, and paper-trading scope.

Do not add React, Next.js, RQ workflow orchestration, broker adapters, arbitrary strategy upload, auth, or Alembic migrations in this stage.

## Review Rule

After every implementation task, run both reviews required by `AGENTS.md` before proceeding:

1. Spec review: compare the task output against `docs/superpowers/specs/2026-06-22-quant-trading-operations-workbench-design.md`.
2. Quality review: inspect code quality, naming, boundary cases, and test coverage.

Record both review results in the implementation log or task handoff before the next task starts.

---

### Task 1: Workflow Service Layer

**Files:**
- Create: `src/quant_trading/workflows/__init__.py`
- Create: `src/quant_trading/workflows/operations.py`
- Modify: `src/quant_trading/jobs/tasks.py`
- Test: `tests/integration/test_workflows_service.py`
- Test: `tests/integration/test_paper_jobs.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/integration/test_workflows_service.py`:

```python
from decimal import Decimal
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.models import CashLedgerORM, PaperRunORM
from quant_trading.workflows.operations import (
    create_paper_account,
    import_legacy_data,
    run_ma_cross_backtest,
    run_paper_tick,
    start_ma_cross_paper_run,
)


def make_test_engine():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return engine


def test_workflow_service_runs_core_local_loop(legacy_sqlite_db: Path):
    engine = make_test_engine()

    imported = import_legacy_data(engine, legacy_sqlite_db)
    backtest = run_ma_cross_backtest(
        engine=engine,
        symbol="000001",
        short_window=3,
        long_window=8,
        order_size=50,
        initial_cash=Decimal("100000"),
    )
    account = create_paper_account(
        engine=engine,
        name="Desk Paper",
        initial_cash=Decimal("100000"),
        base_currency="CNY",
    )
    run = start_ma_cross_paper_run(
        engine=engine,
        account_id=account["account_id"],
        symbol="000001",
        short_window=3,
        long_window=8,
        order_size=50,
        max_order_value=Decimal("100000"),
    )
    tick = run_paper_tick(engine=engine, run_id=run["run_id"])
    second_tick = run_paper_tick(engine=engine, run_id=run["run_id"])

    assert imported == {"imported_symbols": 1, "imported_bars": 121}
    assert backtest["run_id"] == 1
    assert backtest["symbol"] == "000001"
    assert backtest["strategy_name"] == "ma_cross"
    assert Decimal(backtest["final_equity"]) > Decimal("0")
    assert backtest["equity_points"] == 121
    assert account == {
        "account_id": 1,
        "name": "Desk Paper",
        "initial_cash": "100000",
        "base_currency": "CNY",
    }
    assert run == {
        "run_id": 1,
        "account_id": 1,
        "symbol": "000001",
        "strategy_name": "ma_cross",
        "status": "running",
    }
    assert tick["run_id"] == 1
    assert tick["account_id"] == 1
    assert tick["snapshot_created"] is True
    assert tick["idempotent_noop"] is False
    assert second_tick["idempotent_noop"] is True
    assert second_tick["orders_created"] == 0


def test_workflow_service_persists_strategy_and_risk_config(legacy_sqlite_db: Path):
    engine = make_test_engine()
    import_legacy_data(engine, legacy_sqlite_db)
    account = create_paper_account(engine, "Config Paper", Decimal("100000"), "CNY")

    run = start_ma_cross_paper_run(
        engine=engine,
        account_id=account["account_id"],
        symbol="000001",
        short_window=4,
        long_window=12,
        order_size=75,
        max_order_value=Decimal("12345.67"),
    )

    with session_scope(engine) as session:
        row = session.get(PaperRunORM, run["run_id"])
        assert row is not None
        assert json.loads(row.strategy_config) == {
            "strategy_name": "ma_cross",
            "short_window": 4,
            "long_window": 12,
            "order_size": 75,
        }
        assert json.loads(row.risk_config) == {"max_order_value": "12345.67"}


def test_workflow_service_rejects_invalid_values(legacy_sqlite_db: Path):
    engine = make_test_engine()
    import_legacy_data(engine, legacy_sqlite_db)

    with pytest.raises(ValueError, match="name is required"):
        create_paper_account(engine, "   ", Decimal("100000"), "CNY")

    with pytest.raises(ValueError, match="long_window must be greater than short_window"):
        run_ma_cross_backtest(engine, "000001", 20, 5, 100, Decimal("100000"))

    with pytest.raises(ValueError, match="initial_cash must be positive"):
        create_paper_account(engine, "Bad Cash", Decimal("0"), "CNY")


def test_create_paper_account_writes_initial_deposit_ledger():
    engine = make_test_engine()
    account = create_paper_account(engine, "Ledger Paper", Decimal("100000"), "CNY")

    with session_scope(engine) as session:
        rows = session.scalars(
            select(CashLedgerORM).where(CashLedgerORM.account_id == account["account_id"])
        ).all()

    assert len(rows) == 1
    assert rows[0].event_type == "initial_deposit"
    assert rows[0].amount == Decimal("100000.000000")
    assert rows[0].cash_after == Decimal("100000.000000")
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_workflows_service.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'quant_trading.workflows'`.

- [ ] **Step 3: Implement reusable workflow commands**

Create `src/quant_trading/workflows/__init__.py`:

```python
from quant_trading.workflows.operations import (
    create_paper_account,
    import_legacy_data,
    run_ma_cross_backtest,
    run_paper_tick,
    start_ma_cross_paper_run,
)

__all__ = [
    "create_paper_account",
    "import_legacy_data",
    "run_ma_cross_backtest",
    "run_paper_tick",
    "start_ma_cross_paper_run",
]
```

Create `src/quant_trading/workflows/operations.py`:

```python
from decimal import Decimal
import json
from pathlib import Path

from sqlalchemy import Engine

from quant_trading.backtest.engine import BacktestEngine
from quant_trading.core.enums import StrategyStatus
from quant_trading.paper.engine import PaperTickSummary, PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import (
    MaxOrderValueRule,
    NoTradeWithoutDataRule,
    PriceSanityRule,
    StrategyStatusRule,
)
from quant_trading.storage.db import session_scope
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.storage.models import PaperRunORM
from quant_trading.strategy.builtin.ma_cross import MACrossStrategy


DEFAULT_COMMISSION_RATE = Decimal("0.0003")
DEFAULT_SLIPPAGE_RATE = Decimal("0.001")
DEFAULT_MAX_ORDER_VALUE = Decimal("100000")


def import_legacy_data(engine: Engine, legacy_db_path: str | Path) -> dict:
    result = import_legacy_sqlite(Path(legacy_db_path), engine)
    return {
        "imported_symbols": result.imported_symbols,
        "imported_bars": result.imported_bars,
    }


def run_ma_cross_backtest(
    engine: Engine,
    symbol: str,
    short_window: int,
    long_window: int,
    order_size: int,
    initial_cash: Decimal,
) -> dict:
    _validate_ma_cross(short_window, long_window, order_size)
    _require_positive_decimal(initial_cash, "initial_cash")
    backtest = BacktestEngine(
        engine=engine,
        initial_cash=initial_cash,
        commission_rate=DEFAULT_COMMISSION_RATE,
        slippage_rate=DEFAULT_SLIPPAGE_RATE,
    )
    result = backtest.run(
        symbol=symbol,
        strategy=MACrossStrategy(
            short_window=short_window,
            long_window=long_window,
            order_size=order_size,
        ),
        strategy_name="ma_cross",
    )
    return {
        "run_id": result.run_id,
        "symbol": symbol,
        "strategy_name": "ma_cross",
        "final_equity": _decimal_text(result.final_equity),
        "equity_points": result.equity_points,
    }


def create_paper_account(
    engine: Engine,
    name: str,
    initial_cash: Decimal,
    base_currency: str = "CNY",
) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("name is required")
    _require_positive_decimal(initial_cash, "initial_cash")
    currency = (base_currency or "CNY").strip().upper() or "CNY"
    paper = _make_paper_engine(engine, max_order_value=DEFAULT_MAX_ORDER_VALUE)
    account_id = paper.create_account(
        name=clean_name,
        initial_cash=initial_cash,
        base_currency=currency,
    )
    return {
        "account_id": account_id,
        "name": clean_name,
        "initial_cash": _decimal_text(initial_cash),
        "base_currency": currency,
    }


def start_ma_cross_paper_run(
    engine: Engine,
    account_id: int,
    symbol: str,
    short_window: int,
    long_window: int,
    order_size: int,
    max_order_value: Decimal = DEFAULT_MAX_ORDER_VALUE,
) -> dict:
    _validate_ma_cross(short_window, long_window, order_size)
    _require_positive_decimal(max_order_value, "max_order_value")
    strategy = MACrossStrategy(
        short_window=short_window,
        long_window=long_window,
        order_size=order_size,
    )
    paper = _make_paper_engine(engine, max_order_value=max_order_value)
    run_id = paper.start_run(
        account_id=account_id,
        symbol=symbol,
        strategy=strategy,
        strategy_name="ma_cross",
        strategy_status=StrategyStatus.APPROVED,
        risk_config={"max_order_value": _decimal_text(max_order_value)},
    )
    return {
        "run_id": run_id,
        "account_id": account_id,
        "symbol": symbol,
        "strategy_name": "ma_cross",
        "status": "running",
    }


def run_paper_tick(engine: Engine, run_id: int) -> dict:
    strategy, max_order_value = _load_ma_cross_run_config(engine, run_id)
    paper = _make_paper_engine(engine, max_order_value=max_order_value)
    result = paper.run_one_tick(
        run_id=run_id,
        strategy=strategy,
        strategy_status=StrategyStatus.APPROVED,
    )
    return _paper_tick_payload(result)


def _load_ma_cross_run_config(engine: Engine, run_id: int) -> tuple[MACrossStrategy, Decimal]:
    with session_scope(engine) as session:
        run = session.get(PaperRunORM, run_id)
        if run is None:
            raise ValueError(f"paper run not found: {run_id}")
        if run.strategy_name != "ma_cross":
            raise ValueError(f"unsupported paper strategy for job: {run.strategy_name}")
        strategy_config = json.loads(run.strategy_config or "{}")
        risk_config = json.loads(run.risk_config or "{}")

    strategy = MACrossStrategy(
        short_window=int(strategy_config.get("short_window", 5)),
        long_window=int(strategy_config.get("long_window", 20)),
        order_size=int(strategy_config.get("order_size", 100)),
    )
    max_order_value = Decimal(str(risk_config.get("max_order_value", DEFAULT_MAX_ORDER_VALUE)))
    return strategy, max_order_value


def _make_paper_engine(engine: Engine, max_order_value: Decimal) -> PaperTradingEngine:
    return PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine(
            [
                StrategyStatusRule(),
                NoTradeWithoutDataRule(),
                PriceSanityRule(),
                MaxOrderValueRule(max_order_value=max_order_value),
            ]
        ),
        commission_rate=DEFAULT_COMMISSION_RATE,
        slippage_rate=DEFAULT_SLIPPAGE_RATE,
    )


def _paper_tick_payload(result: PaperTickSummary) -> dict:
    return {
        "run_id": result.run_id,
        "account_id": result.account_id,
        "processed_at": result.processed_at.isoformat(),
        "orders_created": result.orders_created,
        "orders_filled": result.orders_filled,
        "orders_rejected": result.orders_rejected,
        "fills_created": result.fills_created,
        "snapshot_created": result.snapshot_created,
        "risk_decision_count": result.risk_decision_count,
        "idempotent_noop": result.idempotent_noop,
    }


def _validate_ma_cross(short_window: int, long_window: int, order_size: int) -> None:
    if short_window <= 0:
        raise ValueError("short_window must be positive")
    if long_window <= short_window:
        raise ValueError("long_window must be greater than short_window")
    if order_size <= 0:
        raise ValueError("order_size must be positive")


def _require_positive_decimal(value: Decimal, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
```

- [ ] **Step 4: Refactor job tasks to use the workflow service**

Modify `src/quant_trading/jobs/tasks.py` so the public task functions keep their existing signatures but delegate to the service layer:

```python
from decimal import Decimal

from quant_trading.storage.db import create_all, make_engine
from quant_trading.workflows.operations import (
    import_legacy_data,
    run_ma_cross_backtest,
    run_paper_tick,
)


def import_legacy_data_task(legacy_db_path: str, database_url: str) -> dict:
    engine = make_engine(database_url)
    create_all(engine)
    return import_legacy_data(engine, legacy_db_path)


def run_ma_cross_backtest_task(database_url: str, symbol: str = "000001") -> dict:
    engine = make_engine(database_url)
    create_all(engine)
    return run_ma_cross_backtest(
        engine=engine,
        symbol=symbol,
        short_window=5,
        long_window=20,
        order_size=100,
        initial_cash=Decimal("100000"),
    )


def run_paper_tick_task(database_url: str, run_id: int) -> dict:
    engine = make_engine(database_url)
    create_all(engine)
    return run_paper_tick(engine=engine, run_id=run_id)
```

Delete the old `_load_paper_strategy_for_job()` helper from `tasks.py` after the refactor; that behavior now lives in `workflows.operations._load_ma_cross_run_config()`.

- [ ] **Step 5: Run focused verification**

Run:

```bash
python -m pytest tests/integration/test_workflows_service.py tests/integration/test_paper_jobs.py -q
```

Expected: all tests pass, including the existing persisted MA Cross config and unsupported strategy job tests.

- [ ] **Step 6: Run required reviews**

Spec review:

```text
Task 1 covers reusable command execution, legacy import, MA Cross backtest, paper account/run creation, paper tick execution, idempotency, and persisted strategy/risk config. It does not expose HTTP or dashboard UI yet; those are later tasks.
```

Quality review:

```text
Confirm command functions are thin, deterministic, validate numeric boundaries, return JSON-ready dictionaries, share paper tick reconstruction with jobs, and do not introduce a second strategy-default code path.
```

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add src/quant_trading/workflows/__init__.py src/quant_trading/workflows/operations.py src/quant_trading/jobs/tasks.py tests/integration/test_workflows_service.py tests/integration/test_paper_jobs.py
git commit -m "feat: add quant workflow command service"
```

---

### Task 2: JSON Command API Routes

**Files:**
- Create: `src/quant_trading/api/routes/workflows.py`
- Modify: `src/quant_trading/api/main.py`
- Test: `tests/integration/test_workflows_api.py`

- [ ] **Step 1: Write failing command API tests**

Create `tests/integration/test_workflows_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from quant_trading.api.main import create_app
from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.models import CashLedgerORM, PaperRunORM


def make_client():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return TestClient(create_app(engine)), engine


def test_workflow_command_api_runs_import_backtest_paper_tick(legacy_sqlite_db: Path):
    client, engine = make_client()

    import_response = client.post(
        "/workflows/import-legacy",
        json={"legacy_db_path": str(legacy_sqlite_db)},
    )
    backtest_response = client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "000001",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "initial_cash": "100000",
        },
    )
    account_response = client.post(
        "/workflows/paper/accounts",
        json={
            "name": "Local Paper",
            "initial_cash": "100000",
            "base_currency": "CNY",
        },
    )
    run_response = client.post(
        "/workflows/paper/runs/ma-cross",
        json={
            "account_id": account_response.json()["account_id"],
            "symbol": "000001",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "max_order_value": "100000",
        },
    )
    tick_response = client.post(
        f"/workflows/paper/runs/{run_response.json()['run_id']}/tick"
    )

    assert import_response.status_code == 200
    assert import_response.json() == {"imported_symbols": 1, "imported_bars": 121}
    assert backtest_response.status_code == 200
    assert backtest_response.json()["strategy_name"] == "ma_cross"
    assert backtest_response.json()["equity_points"] == 121
    assert account_response.status_code == 200
    assert account_response.json()["name"] == "Local Paper"
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "running"
    assert tick_response.status_code == 200
    assert tick_response.json()["snapshot_created"] is True

    with session_scope(engine) as session:
        run = session.get(PaperRunORM, run_response.json()["run_id"])
        ledger_rows = session.query(CashLedgerORM).all()
    assert run is not None
    assert run.strategy_config
    assert len(ledger_rows) >= 1


def test_workflow_command_api_validates_invalid_payloads(legacy_sqlite_db: Path):
    client, _ = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})

    invalid_backtest = client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "000001",
            "short_window": 20,
            "long_window": 5,
            "order_size": 50,
            "initial_cash": "100000",
        },
    )
    invalid_account = client.post(
        "/workflows/paper/accounts",
        json={"name": "   ", "initial_cash": "100000", "base_currency": "CNY"},
    )
    missing_run_tick = client.post("/workflows/paper/runs/999/tick")

    assert invalid_backtest.status_code in {400, 422}
    assert invalid_account.status_code in {400, 422}
    assert missing_run_tick.status_code == 404
```

- [ ] **Step 2: Run the API tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_workflows_api.py -q
```

Expected: fail with `404 Not Found` for `/workflows/...` routes.

- [ ] **Step 3: Implement command route models and handlers**

Create `src/quant_trading/api/routes/workflows.py`:

```python
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from quant_trading.workflows.operations import (
    create_paper_account,
    import_legacy_data,
    run_ma_cross_backtest,
    run_paper_tick,
    start_ma_cross_paper_run,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


class ImportLegacyRequest(BaseModel):
    legacy_db_path: str = Field(min_length=1)


class MACrossBacktestRequest(BaseModel):
    symbol: str = Field(min_length=1)
    short_window: int = Field(gt=0)
    long_window: int = Field(gt=0)
    order_size: int = Field(gt=0)
    initial_cash: Decimal = Field(gt=Decimal("0"))

    @model_validator(mode="after")
    def validate_windows(self):
        if self.long_window <= self.short_window:
            raise ValueError("long_window must be greater than short_window")
        return self


class CreatePaperAccountRequest(BaseModel):
    name: str = Field(min_length=1)
    initial_cash: Decimal = Field(gt=Decimal("0"))
    base_currency: str = "CNY"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("name is required")
        return clean

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return (value or "CNY").strip().upper() or "CNY"


class CreateMACrossPaperRunRequest(BaseModel):
    account_id: int = Field(gt=0)
    symbol: str = Field(min_length=1)
    short_window: int = Field(gt=0)
    long_window: int = Field(gt=0)
    order_size: int = Field(gt=0)
    max_order_value: Decimal = Field(default=Decimal("100000"), gt=Decimal("0"))

    @model_validator(mode="after")
    def validate_windows(self):
        if self.long_window <= self.short_window:
            raise ValueError("long_window must be greater than short_window")
        return self


@router.post("/import-legacy")
def import_legacy(payload: ImportLegacyRequest, request: Request) -> dict:
    return _run_command(lambda: import_legacy_data(request.app.state.engine, payload.legacy_db_path))


@router.post("/backtests/ma-cross")
def create_ma_cross_backtest(payload: MACrossBacktestRequest, request: Request) -> dict:
    return _run_command(
        lambda: run_ma_cross_backtest(
            engine=request.app.state.engine,
            symbol=payload.symbol,
            short_window=payload.short_window,
            long_window=payload.long_window,
            order_size=payload.order_size,
            initial_cash=payload.initial_cash,
        )
    )


@router.post("/paper/accounts")
def create_account(payload: CreatePaperAccountRequest, request: Request) -> dict:
    return _run_command(
        lambda: create_paper_account(
            engine=request.app.state.engine,
            name=payload.name,
            initial_cash=payload.initial_cash,
            base_currency=payload.base_currency,
        )
    )


@router.post("/paper/runs/ma-cross")
def create_ma_cross_paper_run(
    payload: CreateMACrossPaperRunRequest,
    request: Request,
) -> dict:
    return _run_command(
        lambda: start_ma_cross_paper_run(
            engine=request.app.state.engine,
            account_id=payload.account_id,
            symbol=payload.symbol,
            short_window=payload.short_window,
            long_window=payload.long_window,
            order_size=payload.order_size,
            max_order_value=payload.max_order_value,
        )
    )


@router.post("/paper/runs/{run_id}/tick")
def run_one_paper_tick(run_id: int, request: Request) -> dict:
    return _run_command(lambda: run_paper_tick(request.app.state.engine, run_id))


def _run_command(callback):
    try:
        return callback()
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
```

- [ ] **Step 4: Wire the router into the app**

Modify `src/quant_trading/api/main.py`:

```python
from quant_trading.api.routes import backtests, dashboard, health, instruments, paper, workflows
```

Then include routers in `create_app()`:

```python
app.include_router(health.router)
app.include_router(instruments.router)
app.include_router(backtests.router)
app.include_router(paper.router)
app.include_router(workflows.router)
app.include_router(dashboard.router)
```

If `dashboard.py` does not exist yet, temporarily omit `dashboard` from the import and router list in this task; Task 3 will add it. Do not leave a broken import.

- [ ] **Step 5: Run focused verification**

Run:

```bash
python -m pytest tests/integration/test_workflows_api.py tests/integration/test_workflows_service.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run required reviews**

Spec review:

```text
Task 2 covers all five JSON command endpoints, synchronous responses, validation, expected 400/404 handling, and persisted ids in responses. Dashboard and README are still pending by design.
```

Quality review:

```text
Confirm route handlers stay thin, Pydantic validates numeric boundaries, domain ValueError messages become clear HTTP errors, and command routes reuse workflows.operations rather than instantiating engines directly.
```

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/quant_trading/api/main.py src/quant_trading/api/routes/workflows.py tests/integration/test_workflows_api.py
git commit -m "feat: expose quant workflow command APIs"
```

---

### Task 3: Server-Rendered Operations Dashboard

**Files:**
- Create: `src/quant_trading/api/routes/dashboard.py`
- Modify: `src/quant_trading/api/main.py`
- Modify: `pyproject.toml`
- Test: `tests/integration/test_dashboard.py`

- [ ] **Step 1: Write failing dashboard tests**

Create `tests/integration/test_dashboard.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from quant_trading.api.main import create_app
from quant_trading.storage.db import create_all, make_engine


def make_client():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return TestClient(create_app(engine)), engine


def test_dashboard_renders_workflow_forms_and_empty_state():
    client, _ = make_client()

    response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "Operations Workbench" in html
    assert 'action="/dashboard/actions/import-legacy"' in html
    assert 'action="/dashboard/actions/backtests/ma-cross"' in html
    assert 'action="/dashboard/actions/paper/accounts"' in html
    assert 'action="/dashboard/actions/paper/runs/ma-cross"' in html
    assert 'action="/dashboard/actions/paper/tick"' in html
    assert "Backtest Runs" in html
    assert "Paper Accounts" in html


def test_dashboard_displays_seeded_workflow_state(legacy_sqlite_db: Path):
    client, _ = make_client()
    client.post("/workflows/import-legacy", json={"legacy_db_path": str(legacy_sqlite_db)})
    backtest = client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "000001",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "initial_cash": "100000",
        },
    ).json()
    account = client.post(
        "/workflows/paper/accounts",
        json={"name": "Dashboard Paper", "initial_cash": "100000", "base_currency": "CNY"},
    ).json()
    run = client.post(
        "/workflows/paper/runs/ma-cross",
        json={
            "account_id": account["account_id"],
            "symbol": "000001",
            "short_window": 3,
            "long_window": 8,
            "order_size": 50,
            "max_order_value": "100000",
        },
    ).json()
    client.post(f"/workflows/paper/runs/{run['run_id']}/tick")

    response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "000001" in html
    assert "Dashboard Paper" in html
    assert f"#{backtest['run_id']}" in html
    assert f"#{run['run_id']}" in html
    assert "running" in html


def test_dashboard_form_actions_complete_core_workflow(legacy_sqlite_db: Path):
    client, _ = make_client()

    import_response = client.post(
        "/dashboard/actions/import-legacy",
        data={"legacy_db_path": str(legacy_sqlite_db)},
        follow_redirects=False,
    )
    backtest_response = client.post(
        "/dashboard/actions/backtests/ma-cross",
        data={
            "symbol": "000001",
            "short_window": "3",
            "long_window": "8",
            "order_size": "50",
            "initial_cash": "100000",
        },
        follow_redirects=False,
    )
    account_response = client.post(
        "/dashboard/actions/paper/accounts",
        data={"name": "Form Paper", "initial_cash": "100000", "base_currency": "CNY"},
        follow_redirects=False,
    )
    assert import_response.status_code == 303
    assert backtest_response.status_code == 303
    assert account_response.status_code == 303

    dashboard = client.get("/dashboard")
    assert "Form Paper" in dashboard.text
```

- [ ] **Step 2: Run dashboard tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_dashboard.py -q
```

Expected: fail with `404 Not Found` for `/dashboard`.

- [ ] **Step 3: Add form parsing dependency**

Modify `pyproject.toml` and add `python-multipart` to `[project].dependencies`:

```toml
  "python-multipart>=0.0.9",
```

This keeps dashboard form actions on Starlette/FastAPI's supported form parser instead of adding hand-written request-body parsing.

- [ ] **Step 4: Implement dashboard state collection and rendering**

Create `src/quant_trading/api/routes/dashboard.py` with compact server-rendered HTML. Use `Request.form()` for form action handlers:

```python
from decimal import Decimal
from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from quant_trading.storage.db import session_scope
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
)
from quant_trading.workflows.operations import (
    create_paper_account,
    import_legacy_data,
    run_ma_cross_backtest,
    run_paper_tick,
    start_ma_cross_paper_run,
)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, notice: str | None = None, error: str | None = None) -> HTMLResponse:
    state = _collect_state(request)
    return HTMLResponse(_render_dashboard(state, notice=notice, error=error))


@router.post("/dashboard/actions/import-legacy")
async def dashboard_import_legacy(request: Request):
    form = await request.form()
    return _dashboard_action(
        request,
        lambda: import_legacy_data(request.app.state.engine, str(form.get("legacy_db_path", ""))),
        "Imported legacy data",
    )


@router.post("/dashboard/actions/backtests/ma-cross")
async def dashboard_backtest(request: Request):
    form = await request.form()
    return _dashboard_action(
        request,
        lambda: run_ma_cross_backtest(
            engine=request.app.state.engine,
            symbol=str(form.get("symbol", "000001")),
            short_window=int(form.get("short_window", "5")),
            long_window=int(form.get("long_window", "20")),
            order_size=int(form.get("order_size", "100")),
            initial_cash=Decimal(str(form.get("initial_cash", "100000"))),
        ),
        "Created MA Cross backtest",
    )


@router.post("/dashboard/actions/paper/accounts")
async def dashboard_create_account(request: Request):
    form = await request.form()
    return _dashboard_action(
        request,
        lambda: create_paper_account(
            engine=request.app.state.engine,
            name=str(form.get("name", "")),
            initial_cash=Decimal(str(form.get("initial_cash", "100000"))),
            base_currency=str(form.get("base_currency", "CNY")),
        ),
        "Created paper account",
    )


@router.post("/dashboard/actions/paper/runs/ma-cross")
async def dashboard_create_run(request: Request):
    form = await request.form()
    return _dashboard_action(
        request,
        lambda: start_ma_cross_paper_run(
            engine=request.app.state.engine,
            account_id=int(form.get("account_id", "0")),
            symbol=str(form.get("symbol", "000001")),
            short_window=int(form.get("short_window", "5")),
            long_window=int(form.get("long_window", "20")),
            order_size=int(form.get("order_size", "100")),
            max_order_value=Decimal(str(form.get("max_order_value", "100000"))),
        ),
        "Created MA Cross paper run",
    )


@router.post("/dashboard/actions/paper/tick")
async def dashboard_tick(request: Request):
    form = await request.form()
    return _dashboard_action(
        request,
        lambda: run_paper_tick(request.app.state.engine, int(form.get("run_id", "0"))),
        "Processed paper tick",
    )


def _dashboard_action(request: Request, callback, success_message: str):
    try:
        callback()
    except Exception as exc:
        state = _collect_state(request)
        return HTMLResponse(_render_dashboard(state, error=str(exc)), status_code=400)
    return RedirectResponse(
        "/dashboard?" + urlencode({"notice": success_message}),
        status_code=303,
    )


def _collect_state(request: Request) -> dict:
    engine = request.app.state.engine
    db_label = str(engine.url.render_as_string(hide_password=True))
    with session_scope(engine) as session:
        return {
            "db_label": db_label,
            "instrument_count": session.scalar(select(func.count()).select_from(InstrumentORM)) or 0,
            "latest_bar": session.scalar(select(func.max(MarketBarORM.timestamp))),
            "backtests": session.scalars(
                select(BacktestRunORM).order_by(BacktestRunORM.id.desc()).limit(10)
            ).all(),
            "accounts": session.scalars(
                select(PaperAccountORM).order_by(PaperAccountORM.id.desc()).limit(10)
            ).all(),
            "runs": session.scalars(select(PaperRunORM).order_by(PaperRunORM.id.desc()).limit(10)).all(),
            "positions": session.scalars(
                select(PaperPositionORM).order_by(PaperPositionORM.updated_at.desc()).limit(10)
            ).all(),
            "orders": session.scalars(select(PaperOrderORM).order_by(PaperOrderORM.id.desc()).limit(10)).all(),
            "fills": session.scalars(select(PaperFillORM).order_by(PaperFillORM.id.desc()).limit(10)).all(),
            "risk": session.scalars(select(RiskDecisionORM).order_by(RiskDecisionORM.id.desc()).limit(10)).all(),
            "ledger": session.scalars(select(CashLedgerORM).order_by(CashLedgerORM.id.desc()).limit(10)).all(),
            "snapshots": session.scalars(
                select(PortfolioSnapshotORM).order_by(PortfolioSnapshotORM.timestamp.desc()).limit(10)
            ).all(),
        }
```

In the same file, add `_render_dashboard()` and small table helpers. Keep the UI dense and operational:

```python
def _render_dashboard(state: dict, notice: str | None, error: str | None) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Operations Workbench</title>
  <style>
    body {{ margin:0; font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#17202a; background:#f5f7fa; }}
    header {{ padding:18px 24px; background:#ffffff; border-bottom:1px solid #d8dee6; }}
    main {{ padding:18px 24px 32px; display:grid; gap:18px; }}
    h1 {{ margin:0 0 4px; font-size:22px; }}
    h2 {{ margin:0 0 10px; font-size:16px; }}
    .meta {{ color:#5d6d7e; font-size:12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; align-items:start; }}
    section {{ background:#fff; border:1px solid #d8dee6; border-radius:6px; padding:14px; }}
    form {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
    label {{ display:grid; gap:3px; color:#34495e; font-size:12px; }}
    input {{ padding:7px 8px; border:1px solid #b9c2cc; border-radius:4px; font:inherit; }}
    button {{ padding:8px 10px; border:1px solid #1f618d; background:#2471a3; color:#fff; border-radius:4px; font:inherit; cursor:pointer; }}
    button:hover {{ background:#1f618d; }}
    .full {{ grid-column:1 / -1; }}
    .notice {{ padding:9px 12px; border-radius:4px; background:#eafaf1; color:#196f3d; border:1px solid #abebc6; }}
    .error {{ padding:9px 12px; border-radius:4px; background:#fdedec; color:#922b21; border:1px solid #f5b7b1; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    th,td {{ padding:6px 7px; border-bottom:1px solid #edf1f5; text-align:left; white-space:nowrap; }}
    th {{ color:#566573; background:#f8fafc; }}
    .tables {{ display:grid; gap:14px; }}
    @media (max-width: 720px) {{ form {{ grid-template-columns:1fr; }} main {{ padding:14px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Operations Workbench</h1>
    <div class="meta">database: {_e(state["db_label"])} | instruments: {state["instrument_count"]} | latest bar: {_e(state["latest_bar"])}</div>
  </header>
  <main>
    {_message("notice", notice)}
    {_message("error", error)}
    <div class="grid">
      {_forms_html()}
    </div>
    <div class="tables">
      {_backtests_table(state["backtests"])}
      {_accounts_table(state["accounts"])}
      {_runs_table(state["runs"])}
      {_simple_table("Latest Positions", state["positions"], ["id", "account_id", "symbol", "quantity", "market_price", "updated_at"])}
      {_simple_table("Latest Orders", state["orders"], ["id", "run_id", "symbol", "side", "quantity", "status"])}
      {_simple_table("Latest Fills", state["fills"], ["id", "run_id", "symbol", "side", "quantity", "price"])}
      {_simple_table("Latest Risk Decisions", state["risk"], ["id", "run_id", "order_id", "decision", "rule_name", "message"])}
      {_simple_table("Latest Cash Ledger", state["ledger"], ["id", "account_id", "event_type", "amount", "cash_after", "currency"])}
      {_simple_table("Latest Snapshots", state["snapshots"], ["id", "account_id", "run_id", "timestamp", "equity", "cash", "market_value"])}
    </div>
  </main>
</body>
</html>"""


def _forms_html() -> str:
    return """
<section><h2>Import Legacy Data</h2><form method="post" action="/dashboard/actions/import-legacy">
  <label class="full">Legacy DB Path<input name="legacy_db_path" value="legacy/django_app/db.sqlite3"></label>
  <button class="full" type="submit">Import</button>
</form></section>
<section><h2>Run MA Cross Backtest</h2><form method="post" action="/dashboard/actions/backtests/ma-cross">
  <label>Symbol<input name="symbol" value="000001"></label><label>Initial Cash<input name="initial_cash" value="100000"></label>
  <label>Short Window<input name="short_window" value="5"></label><label>Long Window<input name="long_window" value="20"></label>
  <label>Order Size<input name="order_size" value="100"></label><button type="submit">Run</button>
</form></section>
<section><h2>Create Paper Account</h2><form method="post" action="/dashboard/actions/paper/accounts">
  <label>Name<input name="name" value="Local Paper"></label><label>Initial Cash<input name="initial_cash" value="100000"></label>
  <label>Base Currency<input name="base_currency" value="CNY"></label><button type="submit">Create</button>
</form></section>
<section><h2>Create MA Cross Paper Run</h2><form method="post" action="/dashboard/actions/paper/runs/ma-cross">
  <label>Account ID<input name="account_id" value="1"></label><label>Symbol<input name="symbol" value="000001"></label>
  <label>Short Window<input name="short_window" value="5"></label><label>Long Window<input name="long_window" value="20"></label>
  <label>Order Size<input name="order_size" value="100"></label><label>Max Order Value<input name="max_order_value" value="100000"></label>
  <button class="full" type="submit">Start Run</button>
</form></section>
<section><h2>Run One Paper Tick</h2><form method="post" action="/dashboard/actions/paper/tick">
  <label>Run ID<input name="run_id" value="1"></label><button type="submit">Process Tick</button>
</form></section>
"""
```

Add helper functions in the same file:

```python
def _message(kind: str, text: str | None) -> str:
    return "" if not text else f'<div class="{kind}">{_e(text)}</div>'


def _backtests_table(rows) -> str:
    return _simple_table("Backtest Runs", rows, ["id", "symbol", "strategy_name", "final_equity", "status"])


def _accounts_table(rows) -> str:
    return _simple_table("Paper Accounts", rows, ["id", "name", "base_currency", "initial_cash", "status"])


def _runs_table(rows) -> str:
    return _simple_table("Paper Runs", rows, ["id", "account_id", "symbol", "strategy_name", "status", "last_processed_at"])


def _simple_table(title: str, rows, fields: list[str]) -> str:
    body = "".join(_row_html(row, fields) for row in rows)
    if not body:
        body = f'<tr><td colspan="{len(fields)}">No rows</td></tr>'
    headers = "".join(f"<th>{_e(field)}</th>" for field in fields)
    return f"<section><h2>{_e(title)}</h2><table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></section>"


def _row_html(row, fields: list[str]) -> str:
    cells = []
    for field in fields:
        value = getattr(row, field)
        if field == "id":
            value = f"#{value}"
        cells.append(f"<td>{_e(value)}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def _e(value) -> str:
    if value is None:
        return ""
    return escape(str(value))
```

- [ ] **Step 5: Wire dashboard router into the app**

Modify `src/quant_trading/api/main.py`:

```python
from quant_trading.api.routes import backtests, dashboard, health, instruments, paper, workflows
```

Include both routers:

```python
app.include_router(workflows.router)
app.include_router(dashboard.router)
```

- [ ] **Step 6: Run focused verification**

Run:

```bash
python -m pytest tests/integration/test_dashboard.py tests/integration/test_workflows_api.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Run required reviews**

Spec review:

```text
Task 3 covers GET /dashboard, service status/database label, instrument count/latest bar date, workflow forms, compact status tables, and browser form actions. It keeps the UI server-rendered and avoids a frontend build chain.
```

Quality review:

```text
Confirm all displayed values are escaped, HTML forms have stable defaults, the layout is operational rather than marketing-like, dashboard actions reuse workflows.operations, and the new `python-multipart` dependency is limited to supported form parsing.
```

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add pyproject.toml src/quant_trading/api/main.py src/quant_trading/api/routes/dashboard.py tests/integration/test_dashboard.py
git commit -m "feat: add quant operations dashboard"
```

---

### Task 4: End-To-End HTTP Workflow Test

**Files:**
- Create: `tests/integration/test_operations_workflow_e2e.py`
- Modify only if needed: `src/quant_trading/api/routes/workflows.py`
- Modify only if needed: `src/quant_trading/api/routes/dashboard.py`

- [ ] **Step 1: Write the end-to-end HTTP workflow test**

Create `tests/integration/test_operations_workflow_e2e.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from quant_trading.api.main import create_app
from quant_trading.storage.db import create_all, make_engine


def make_client():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return TestClient(create_app(engine))


def test_operator_can_complete_core_workflow_over_http(legacy_sqlite_db: Path):
    client = make_client()

    imported = client.post(
        "/workflows/import-legacy",
        json={"legacy_db_path": str(legacy_sqlite_db)},
    )
    backtest = client.post(
        "/workflows/backtests/ma-cross",
        json={
            "symbol": "000001",
            "short_window": 5,
            "long_window": 20,
            "order_size": 100,
            "initial_cash": "100000",
        },
    )
    account = client.post(
        "/workflows/paper/accounts",
        json={
            "name": "E2E Paper",
            "initial_cash": "100000",
            "base_currency": "CNY",
        },
    )
    paper_run = client.post(
        "/workflows/paper/runs/ma-cross",
        json={
            "account_id": account.json()["account_id"],
            "symbol": "000001",
            "short_window": 5,
            "long_window": 20,
            "order_size": 100,
            "max_order_value": "100000",
        },
    )
    tick = client.post(f"/workflows/paper/runs/{paper_run.json()['run_id']}/tick")
    noop_tick = client.post(f"/workflows/paper/runs/{paper_run.json()['run_id']}/tick")

    assert imported.status_code == 200
    assert backtest.status_code == 200
    assert account.status_code == 200
    assert paper_run.status_code == 200
    assert tick.status_code == 200
    assert noop_tick.status_code == 200
    assert tick.json()["snapshot_created"] is True
    assert noop_tick.json()["idempotent_noop"] is True

    account_id = account.json()["account_id"]
    run_id = paper_run.json()["run_id"]
    read_responses = [
        client.get("/instruments"),
        client.get("/backtests"),
        client.get("/paper/accounts"),
        client.get(f"/paper/accounts/{account_id}"),
        client.get(f"/paper/accounts/{account_id}/positions"),
        client.get(f"/paper/accounts/{account_id}/cash-ledger"),
        client.get("/paper/runs"),
        client.get(f"/paper/runs/{run_id}"),
        client.get(f"/paper/runs/{run_id}/orders"),
        client.get(f"/paper/runs/{run_id}/fills"),
        client.get(f"/paper/runs/{run_id}/risk-decisions"),
        client.get(f"/paper/runs/{run_id}/snapshots"),
        client.get("/dashboard"),
    ]

    assert [response.status_code for response in read_responses] == [200] * len(read_responses)
    assert read_responses[0].json()[0]["symbol"] == "000001"
    assert read_responses[1].json()[0]["strategy_name"] == "ma_cross"
    assert read_responses[3].json()["name"] == "E2E Paper"
    assert read_responses[-1].text.count("Operations Workbench") == 1
```

- [ ] **Step 2: Run the e2e test and verify failure or pass**

Run:

```bash
python -m pytest tests/integration/test_operations_workflow_e2e.py -q
```

Expected after Tasks 1-3: pass. If it fails, fix only the route/service mismatch causing the e2e failure.

- [ ] **Step 3: Fix only concrete e2e gaps**

Allowed fixes:

```text
- Missing router include in api/main.py.
- Dashboard HTML escaping or table field name mismatch.
- Command API status code mapping for expected ValueError cases.
- Paper tick response field mismatch against the Stage 3 spec.
```

Not allowed in this task:

```text
- Adding new strategy types.
- Adding async queues.
- Adding broker or exchange integrations.
- Rewriting existing read APIs unless the e2e test exposes a direct regression.
```

- [ ] **Step 4: Run broader integration verification**

Run:

```bash
python -m pytest tests/integration/test_workflows_service.py tests/integration/test_workflows_api.py tests/integration/test_dashboard.py tests/integration/test_operations_workflow_e2e.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run required reviews**

Spec review:

```text
Task 4 proves the exact operator loop from the Stage 3 spec over HTTP: import legacy data, run backtest, create paper account, create MA Cross paper run, process tick, inspect read APIs, inspect dashboard.
```

Quality review:

```text
Confirm the e2e test does not call internal Python workflow functions, asserts idempotency, and keeps failures actionable by checking each HTTP response status before inspecting payloads.
```

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add tests/integration/test_operations_workflow_e2e.py src/quant_trading/api/main.py src/quant_trading/api/routes/workflows.py src/quant_trading/api/routes/dashboard.py
git commit -m "test: cover quant operations workflow e2e"
```

If no source files changed, omit them from `git add`.

---

### Task 5: README And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README current milestone and endpoint list**

Modify the "Current Milestone" list in `README.md` so it includes:

```markdown
- Running the operations workbench through command APIs and a server-rendered dashboard.
- Completing the local loop: import legacy data -> run MA Cross backtest -> create paper account/run -> trigger paper tick -> inspect results.
```

Add these endpoints to the "Local Services" endpoint list:

```text
http://localhost:8000/dashboard
http://localhost:8000/workflows/import-legacy
http://localhost:8000/workflows/backtests/ma-cross
http://localhost:8000/workflows/paper/accounts
http://localhost:8000/workflows/paper/runs/ma-cross
http://localhost:8000/workflows/paper/runs/{run_id}/tick
```

- [ ] **Step 2: Add Run The Workbench documentation**

Add this section after "Local Services":

````markdown
## Run The Workbench

Start the API locally:

```bash
python -m uvicorn quant_trading.api.main:app --host 127.0.0.1 --port 8000
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

The dashboard is a local operations console for the paper-trading workflow:

```text
import legacy data -> run MA Cross backtest -> create paper account -> create MA Cross paper run -> run one paper tick -> inspect results
```

Command API example:

```bash
curl -X POST http://127.0.0.1:8000/workflows/import-legacy \
  -H "content-type: application/json" \
  -d '{"legacy_db_path":"legacy/django_app/db.sqlite3"}'

curl -X POST http://127.0.0.1:8000/workflows/backtests/ma-cross \
  -H "content-type: application/json" \
  -d '{"symbol":"000001","short_window":5,"long_window":20,"order_size":100,"initial_cash":"100000"}'

curl -X POST http://127.0.0.1:8000/workflows/paper/accounts \
  -H "content-type: application/json" \
  -d '{"name":"Local Paper","initial_cash":"100000","base_currency":"CNY"}'

curl -X POST http://127.0.0.1:8000/workflows/paper/runs/ma-cross \
  -H "content-type: application/json" \
  -d '{"account_id":1,"symbol":"000001","short_window":5,"long_window":20,"order_size":100,"max_order_value":"100000"}'

curl -X POST http://127.0.0.1:8000/workflows/paper/runs/1/tick
```

These commands are synchronous and intended for local research and paper trading only.
````

- [ ] **Step 3: Update roadmap and safety text**

Replace the old "Roadmap" paragraph that says the next productization stage is persistent paper trading with:

```markdown
## Roadmap

Next productization stages:

- Add queued execution and progress tracking for long imports/backtests.
- Add authentication before exposing command endpoints beyond local development.
- Add broker adapter interfaces only after paper-trading command contracts are stable.
- Add Alembic migrations for existing databases instead of relying on `create_all()`.
```

Keep the Safety section explicit:

```markdown
This project does not place real broker or exchange orders. Command APIs and dashboard actions operate on local research and paper-trading state only.
```

- [ ] **Step 4: Run full verification**

Run:

```bash
python -m pytest -q
docker compose config
```

Expected:

```text
39+ tests passed
docker compose config exits 0
```

The exact test count may increase after adding Stage 3 tests; failures must be fixed before completion.

- [ ] **Step 5: Run required reviews**

Spec review:

```text
Task 5 documents the dashboard URL, command API workflow, synchronous/local scope, and non-real-money safety boundary required by the Stage 3 spec.
```

Quality review:

```text
Confirm README examples match actual endpoint paths and JSON field names, do not imply real-money readiness, and keep the create_all migration caveat in the Legacy Data section.
```

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add README.md
git commit -m "docs: document quant operations workbench"
```

---

## Final Acceptance Checklist

- [ ] `/workflows/import-legacy` imports the legacy SQLite fixture and returns imported symbol/bar counts.
- [ ] `/workflows/backtests/ma-cross` persists a MA Cross backtest run and returns run id, final equity, and equity point count.
- [ ] `/workflows/paper/accounts` creates an account and initial deposit ledger row.
- [ ] `/workflows/paper/runs/ma-cross` starts a persisted MA Cross paper run with strategy config and risk config.
- [ ] `/workflows/paper/runs/{run_id}/tick` runs the existing reconstructed MA Cross paper tick path and preserves idempotency.
- [ ] `/dashboard` renders workflow forms, service status, database label, instruments/latest bar summary, backtests, paper accounts, paper runs, positions, orders, fills, risk decisions, cash ledger, and snapshots.
- [ ] Dashboard form actions complete the local workflow or show plain operational errors.
- [ ] Existing read APIs still work after command actions.
- [ ] `python -m pytest -q` passes.
- [ ] `docker compose config` passes.
- [ ] README documents local workbench usage and does not imply real broker/exchange readiness.

## Execution Handoff

Plan complete. Use one of these execution modes:

1. **Subagent-Driven (recommended)**: use `superpowers:subagent-driven-development`, dispatch a fresh subagent per task, and perform the two required reviews after each task.
2. **Inline Execution**: use `superpowers:executing-plans` and execute tasks in this session with checkpoints and reviews.

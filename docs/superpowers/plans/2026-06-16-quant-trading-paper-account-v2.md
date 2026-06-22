# Quant Trading Paper Account V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `quant-trading` paper trading from stateless one-tick snapshots to persistent paper accounts with runs, orders, fills, positions, cash ledger, idempotent ticks, and read APIs.

**Architecture:** Add paper-specific persistence tables and repositories, then refactor `PaperTradingEngine` into an explicit account/run lifecycle. The schema keeps future multi-strategy and multi-symbol fields, while the stage 2 engine validates one strategy on one symbol. API routes read the persisted account state; command APIs are outside the required acceptance bar.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x, FastAPI, pytest, SQLite for tests, PostgreSQL-compatible SQLAlchemy models.

---

## Scope Lock

This plan implements `docs/superpowers/specs/2026-06-16-quant-trading-paper-account-v2-design.md`.

In scope:

- Persistent `paper_runs`, `paper_orders`, `paper_fills`, `paper_positions`, and `cash_ledger`.
- `PaperTradingEngine.create_account()`, `start_run()`, and `run_one_tick(run_id, ...)`.
- Single-strategy, single-symbol execution for this milestone.
- Idempotent latest-bar processing.
- Risk decisions tied to paper run ids and paper order ids.
- Read APIs for accounts, runs, positions, ledger, orders, fills, snapshots, and risk decisions.
- Job wrapper that runs one paper tick for an existing run.

Out of scope:

- Real broker or exchange adapters.
- Live scheduler daemon.
- Multi-strategy order netting.
- Multi-symbol valuation.
- Partial fills, cancels, replace orders, or broker callbacks.
- Strategy upload or arbitrary Python execution.
- Full frontend.
- Required command APIs.

## Repository And Branch Rules

Implementation work happens in the nested repository:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
```

Current expected base branch:

```text
django-app
```

Current expected dirty user change:

```text
M legacy/django_app/quant_web/settings.py
```

That dirty file is user work migrated from the previous Django path. Do not revert, stage, or commit it unless the user explicitly asks. When creating an implementation worktree, start from committed `django-app` and leave this dirty change in the main checkout.

Suggested implementation branch:

```text
codex/quant-paper-account-v2
```

## File Structure

Create or modify these files in `quant-trading/`:

```text
src/quant_trading/core/enums.py
src/quant_trading/paper/engine.py
src/quant_trading/paper/repositories.py
src/quant_trading/storage/models.py
src/quant_trading/api/routes/paper.py
src/quant_trading/jobs/tasks.py
README.md

tests/integration/test_paper_storage_models.py
tests/integration/test_paper_lifecycle.py
tests/integration/test_paper_engine.py
tests/integration/test_api.py
tests/integration/test_paper_jobs.py
```

Responsibilities:

- `storage/models.py`: SQLAlchemy persistence schema only.
- `paper/repositories.py`: paper account/run/order/fill/position/ledger persistence helpers.
- `paper/engine.py`: lifecycle and tick orchestration.
- `api/routes/paper.py`: read-only persisted paper state APIs.
- `jobs/tasks.py`: background task wrapper for existing paper runs.

---

### Task 1: Persistent Paper Storage Schema

**Files:**
- Modify: `src/quant_trading/core/enums.py`
- Modify: `src/quant_trading/storage/models.py`
- Create: `tests/integration/test_paper_storage_models.py`

- [ ] **Step 1: Write failing storage model test**

Create `tests/integration/test_paper_storage_models.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.models import (
    CashLedgerORM,
    PaperAccountORM,
    PaperFillORM,
    PaperOrderORM,
    PaperPositionORM,
    PaperRunORM,
)


def test_paper_persistence_tables_round_trip():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)

    with session_scope(engine) as session:
        account = PaperAccountORM(
            name="Stage 2 Account",
            base_currency="CNY",
            initial_cash=Decimal("100000"),
            status="active",
        )
        session.add(account)
        session.flush()
        run = PaperRunORM(
            account_id=account.id,
            strategy_name="one_shot_buy",
            symbol="000001",
            universe_config='{"symbols":["000001"]}',
            strategy_config='{"order_size":100}',
            risk_config='{"max_order_value":"100000"}',
            status="running",
        )
        session.add(run)
        session.flush()
        order = PaperOrderORM(
            run_id=run.id,
            account_id=account.id,
            instrument_id=1,
            symbol="000001",
            side="buy",
            order_type="market",
            quantity=100,
            reason="paper_tick_entry",
            status="filled",
            risk_decision="approved",
            submitted_at=date(2026, 1, 2),
        )
        session.add(order)
        session.flush()
        fill = PaperFillORM(
            run_id=run.id,
            account_id=account.id,
            order_id=order.id,
            instrument_id=1,
            symbol="000001",
            side="buy",
            quantity=100,
            price=Decimal("10.20"),
            commission=Decimal("0.31"),
            slippage=Decimal("1.02"),
            filled_at=date(2026, 1, 2),
        )
        session.add(fill)
        session.flush()
        session.add(
            PaperPositionORM(
                account_id=account.id,
                instrument_id=1,
                symbol="000001",
                quantity=100,
                avg_cost=Decimal("10.2031"),
                market_price=Decimal("10.20"),
                realized_pnl=Decimal("0"),
                updated_at=date(2026, 1, 2),
            )
        )
        session.add(
            CashLedgerORM(
                account_id=account.id,
                run_id=run.id,
                order_id=order.id,
                fill_id=fill.id,
                event_type="buy_notional",
                amount=Decimal("-1020"),
                cash_after=Decimal("98980"),
                currency="CNY",
                occurred_at=date(2026, 1, 2),
            )
        )

    with session_scope(engine) as session:
        loaded_run = session.scalar(select(PaperRunORM).where(PaperRunORM.symbol == "000001"))
        loaded_order = session.scalar(select(PaperOrderORM).where(PaperOrderORM.run_id == loaded_run.id))
        loaded_fill = session.scalar(select(PaperFillORM).where(PaperFillORM.order_id == loaded_order.id))
        loaded_position = session.scalar(select(PaperPositionORM).where(PaperPositionORM.account_id == loaded_run.account_id))
        loaded_ledger = session.scalar(select(CashLedgerORM).where(CashLedgerORM.fill_id == loaded_fill.id))

    assert loaded_run.status == "running"
    assert loaded_order.status == "filled"
    assert loaded_fill.price == Decimal("10.200000")
    assert loaded_position.quantity == 100
    assert loaded_ledger.cash_after == Decimal("98980.000000")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python -m pytest tests/integration/test_paper_storage_models.py -q
```

Expected:

```text
ImportError: cannot import name 'CashLedgerORM'
```

- [ ] **Step 3: Add paper status enums**

Modify `src/quant_trading/core/enums.py` by appending:

```python
class PaperRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class PaperOrderStatus(StrEnum):
    CREATED = "created"
    RISK_REJECTED = "risk_rejected"
    FILLED = "filled"
    SKIPPED = "skipped"


class CashLedgerEventType(StrEnum):
    INITIAL_DEPOSIT = "initial_deposit"
    BUY_NOTIONAL = "buy_notional"
    SELL_NOTIONAL = "sell_notional"
    COMMISSION = "commission"
    MANUAL_ADJUSTMENT = "manual_adjustment"
```

- [ ] **Step 4: Add SQLAlchemy ORM classes**

Modify the top import in `src/quant_trading/storage/models.py`:

```python
from datetime import date, datetime
```

Then append these ORM classes after `PaperAccountORM` and before `PortfolioSnapshotORM`:

```python
class PaperRunORM(Base):
    __tablename__ = "paper_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    universe_config: Mapped[str] = mapped_column(String(2048), default="{}")
    strategy_config: Mapped[str] = mapped_column(String(2048), default="{}")
    risk_config: Mapped[str] = mapped_column(String(2048), default="{}")
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    last_processed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaperOrderORM(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("paper_runs.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(16))
    order_type: Mapped[str] = mapped_column(String(16), default="market")
    quantity: Mapped[int] = mapped_column(Integer)
    limit_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    reason: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    risk_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    submitted_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaperFillORM(Base):
    __tablename__ = "paper_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("paper_runs.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(18, 6))
    commission: Mapped[float] = mapped_column(Numeric(18, 6))
    slippage: Mapped[float] = mapped_column(Numeric(18, 6))
    filled_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaperPositionORM(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "instrument_id", name="uq_paper_position_account_instrument"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_cost: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    market_price: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    realized_pnl: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    updated_at: Mapped[date] = mapped_column(Date)


class CashLedgerORM(Base):
    __tablename__ = "cash_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("paper_runs.id"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("paper_orders.id"), nullable=True, index=True)
    fill_id: Mapped[int | None] = mapped_column(ForeignKey("paper_fills.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 6))
    cash_after: Mapped[float] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    occurred_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 5: Run storage model test**

Run:

```bash
python -m pytest tests/integration/test_paper_storage_models.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run current product tests**

Run:

```bash
python -m pytest tests -q
```

Expected:

```text
23 passed
```

- [ ] **Step 7: Commit storage schema**

Run:

```bash
git add src/quant_trading/core/enums.py src/quant_trading/storage/models.py tests/integration/test_paper_storage_models.py
git commit -m "feat: add persistent paper trading schema"
```

Expected commit summary includes:

```text
feat: add persistent paper trading schema
```

---

### Task 2: Paper Account And Run Lifecycle

**Files:**
- Create: `src/quant_trading/paper/repositories.py`
- Modify: `src/quant_trading/paper/engine.py`
- Create: `tests/integration/test_paper_lifecycle.py`

- [ ] **Step 1: Write failing lifecycle tests**

Create `tests/integration/test_paper_lifecycle.py`:

```python
from decimal import Decimal

from sqlalchemy import select

from quant_trading.core.enums import PaperRunStatus, StrategyStatus
from quant_trading.paper.engine import PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.models import CashLedgerORM, PaperAccountORM, PaperRunORM


class NoopStrategy:
    name = "noop"

    def on_bar(self, bars, portfolio):
        return []


def make_paper_engine():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine([]),
    ), engine


def test_create_account_persists_initial_cash_ledger_once():
    paper, engine = make_paper_engine()

    account_id = paper.create_account(
        name="Stage 2 Paper",
        initial_cash=Decimal("100000"),
        base_currency="CNY",
    )

    duplicate_account_id = paper.create_account(
        name="Stage 2 Paper",
        initial_cash=Decimal("100000"),
        base_currency="CNY",
    )

    with session_scope(engine) as session:
        account = session.get(PaperAccountORM, account_id)
        ledger_rows = session.scalars(
            select(CashLedgerORM).where(CashLedgerORM.account_id == account_id)
        ).all()

    assert duplicate_account_id != account_id
    assert account.name == "Stage 2 Paper"
    assert account.initial_cash == Decimal("100000.000000")
    assert len(ledger_rows) == 1
    assert ledger_rows[0].event_type == "initial_deposit"
    assert ledger_rows[0].amount == Decimal("100000.000000")
    assert ledger_rows[0].cash_after == Decimal("100000.000000")


def test_start_run_links_account_strategy_symbol_and_status():
    paper, engine = make_paper_engine()
    account_id = paper.create_account(
        name="Stage 2 Paper",
        initial_cash=Decimal("100000"),
        base_currency="CNY",
    )

    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=NoopStrategy(),
        strategy_name="noop",
        strategy_status=StrategyStatus.APPROVED,
        risk_config={"max_order_value": "100000"},
    )

    with session_scope(engine) as session:
        run = session.get(PaperRunORM, run_id)

    assert run.account_id == account_id
    assert run.strategy_name == "noop"
    assert run.symbol == "000001"
    assert run.status == PaperRunStatus.RUNNING.value
    assert run.universe_config == '{"symbols":["000001"]}'
    assert run.strategy_config == '{"strategy_name":"noop"}'
    assert run.risk_config == '{"max_order_value":"100000"}'
```

- [ ] **Step 2: Run lifecycle tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_paper_lifecycle.py -q
```

Expected:

```text
AttributeError: 'PaperTradingEngine' object has no attribute 'create_account'
```

- [ ] **Step 3: Implement paper repositories**

Create `src/quant_trading/paper/repositories.py`:

```python
from datetime import date, datetime
from decimal import Decimal
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_trading.core.enums import CashLedgerEventType, PaperRunStatus
from quant_trading.core.models import Portfolio, Position
from quant_trading.storage.models import (
    CashLedgerORM,
    PaperAccountORM,
    PaperPositionORM,
    PaperRunORM,
)


def _json_dumps(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class PaperStateRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_account(self, name: str, initial_cash: Decimal, base_currency: str) -> PaperAccountORM:
        account = PaperAccountORM(
            name=name,
            base_currency=base_currency,
            initial_cash=initial_cash,
            status="active",
        )
        self.session.add(account)
        self.session.flush()
        self.session.add(
            CashLedgerORM(
                account_id=account.id,
                run_id=None,
                order_id=None,
                fill_id=None,
                event_type=CashLedgerEventType.INITIAL_DEPOSIT.value,
                amount=initial_cash,
                cash_after=initial_cash,
                currency=base_currency,
                occurred_at=date.today(),
            )
        )
        self.session.flush()
        return account

    def start_run(
        self,
        account_id: int,
        symbol: str,
        strategy_name: str,
        risk_config: dict | None,
    ) -> PaperRunORM:
        run = PaperRunORM(
            account_id=account_id,
            strategy_name=strategy_name,
            symbol=symbol,
            universe_config=_json_dumps({"symbols": [symbol]}),
            strategy_config=_json_dumps({"strategy_name": strategy_name}),
            risk_config=_json_dumps(risk_config or {}),
            status=PaperRunStatus.RUNNING.value,
            started_at=datetime.utcnow(),
        )
        self.session.add(run)
        self.session.flush()
        return run

    def load_run(self, run_id: int) -> PaperRunORM:
        run = self.session.get(PaperRunORM, run_id)
        if run is None:
            raise ValueError(f"paper run not found: {run_id}")
        return run

    def latest_cash(self, account_id: int) -> Decimal:
        row = self.session.scalar(
            select(CashLedgerORM)
            .where(CashLedgerORM.account_id == account_id)
            .order_by(CashLedgerORM.id.desc())
        )
        if row is None:
            raise ValueError(f"cash ledger is missing for account: {account_id}")
        return row.cash_after

    def load_portfolio(self, account_id: int) -> Portfolio:
        positions = self.session.scalars(
            select(PaperPositionORM).where(PaperPositionORM.account_id == account_id)
        ).all()
        return Portfolio(
            account_id=account_id,
            cash=self.latest_cash(account_id),
            positions={
                row.instrument_id: Position(
                    instrument_id=row.instrument_id,
                    symbol=row.symbol,
                    quantity=row.quantity,
                    avg_cost=row.avg_cost,
                    market_price=row.market_price,
                )
                for row in positions
                if row.quantity != 0
            },
        )
```

- [ ] **Step 4: Add lifecycle methods to paper engine**

Modify `src/quant_trading/paper/engine.py`:

```python
from quant_trading.paper.repositories import PaperStateRepository
```

Add methods inside `PaperTradingEngine`:

```python
    def create_account(
        self,
        name: str,
        initial_cash: Decimal | None = None,
        base_currency: str = "CNY",
    ) -> int:
        cash = initial_cash if initial_cash is not None else self.initial_cash
        with session_scope(self.engine) as session:
            account = PaperStateRepository(session).create_account(
                name=name,
                initial_cash=cash,
                base_currency=base_currency,
            )
            return account.id

    def start_run(
        self,
        account_id: int,
        symbol: str,
        strategy: Strategy,
        strategy_name: str,
        strategy_status: StrategyStatus,
        risk_config: dict | None = None,
    ) -> int:
        if strategy_status is not StrategyStatus.APPROVED:
            raise ValueError("paper run requires an approved strategy")
        if not strategy_name:
            raise ValueError("strategy_name is required")
        with session_scope(self.engine) as session:
            if session.get(PaperAccountORM, account_id) is None:
                raise ValueError(f"paper account not found: {account_id}")
            run = PaperStateRepository(session).start_run(
                account_id=account_id,
                symbol=symbol,
                strategy_name=strategy_name,
                risk_config=risk_config,
            )
            return run.id
```

Keep the existing `run_one_tick(symbol, ...)` method for now. Task 3 replaces it after tests are in place.

- [ ] **Step 5: Run lifecycle tests**

Run:

```bash
python -m pytest tests/integration/test_paper_lifecycle.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run paper tests**

Run:

```bash
python -m pytest tests/integration/test_paper_lifecycle.py tests/integration/test_paper_engine.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit lifecycle**

Run:

```bash
git add src/quant_trading/paper/repositories.py src/quant_trading/paper/engine.py tests/integration/test_paper_lifecycle.py
git commit -m "feat: add paper account lifecycle"
```

Expected commit summary includes:

```text
feat: add paper account lifecycle
```

---

### Task 3: Persistent Tick Execution And Idempotency

**Files:**
- Modify: `src/quant_trading/paper/engine.py`
- Modify: `src/quant_trading/paper/repositories.py`
- Modify: `tests/integration/test_paper_engine.py`

- [ ] **Step 1: Replace paper engine tests with persistent-run behavior**

Replace `tests/integration/test_paper_engine.py` with:

```python
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from quant_trading.core.enums import Market, OrderSide, StrategyStatus
from quant_trading.core.models import OrderIntent
from quant_trading.paper.engine import PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import (
    MaxOrderValueRule,
    NoTradeWithoutDataRule,
    PriceSanityRule,
    StrategyStatusRule,
)
from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.storage.models import (
    CashLedgerORM,
    PaperFillORM,
    PaperOrderORM,
    PaperPositionORM,
    PortfolioSnapshotORM,
    RiskDecisionORM,
)
from quant_trading.storage.repositories import InstrumentRepository, MarketDataRepository


class BuyIfFlatStrategy:
    name = "buy_if_flat"

    def __init__(self):
        self.seen_cash = []
        self.seen_quantities = []

    def on_bar(self, bars, portfolio):
        latest = bars[-1]
        position = portfolio.positions.get(latest.instrument_id)
        self.seen_cash.append(portfolio.cash)
        self.seen_quantities.append(0 if position is None else position.quantity)
        if position is not None and position.quantity > 0:
            return []
        return [
            OrderIntent(
                instrument_id=latest.instrument_id,
                symbol=latest.symbol,
                side=OrderSide.BUY,
                quantity=100,
                reason="paper_tick_entry",
            )
        ]


def make_paper(engine):
    return PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine(
            [
                StrategyStatusRule(),
                NoTradeWithoutDataRule(),
                PriceSanityRule(),
                MaxOrderValueRule(max_order_value=Decimal("100000")),
            ]
        ),
    )


def test_paper_tick_persists_order_fill_position_ledger_snapshot_and_risk_decision(
    legacy_sqlite_db: Path,
):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = make_paper(engine)
    strategy = BuyIfFlatStrategy()
    account_id = paper.create_account("Persistent Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name=strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )

    result = paper.run_one_tick(
        run_id=run_id,
        strategy=strategy,
        strategy_status=StrategyStatus.APPROVED,
    )

    with session_scope(engine) as session:
        orders = session.scalars(select(PaperOrderORM).where(PaperOrderORM.run_id == run_id)).all()
        fills = session.scalars(select(PaperFillORM).where(PaperFillORM.run_id == run_id)).all()
        positions = session.scalars(
            select(PaperPositionORM).where(PaperPositionORM.account_id == account_id)
        ).all()
        ledger = session.scalars(
            select(CashLedgerORM).where(CashLedgerORM.account_id == account_id).order_by(CashLedgerORM.id)
        ).all()
        snapshots = session.scalars(
            select(PortfolioSnapshotORM).where(PortfolioSnapshotORM.account_id == account_id)
        ).all()
        decisions = session.scalars(select(RiskDecisionORM).where(RiskDecisionORM.run_id == run_id)).all()

    assert result.run_id == run_id
    assert result.account_id == account_id
    assert result.orders_created == 1
    assert result.orders_filled == 1
    assert result.orders_rejected == 0
    assert result.fills_created == 1
    assert result.snapshot_created is True
    assert result.idempotent_noop is False
    assert len(orders) == 1
    assert orders[0].status == "filled"
    assert orders[0].risk_decision == "approved"
    assert len(fills) == 1
    assert fills[0].order_id == orders[0].id
    assert len(positions) == 1
    assert positions[0].quantity == 100
    assert [row.event_type for row in ledger] == ["initial_deposit", "buy_notional", "commission"]
    assert ledger[-1].cash_after == snapshots[0].cash
    assert snapshots[0].market_value > Decimal("0")
    assert snapshots[0].equity == snapshots[0].cash + snapshots[0].market_value
    assert len(decisions) == 1
    assert decisions[0].order_id == orders[0].id


def test_paper_tick_is_idempotent_for_same_latest_bar(legacy_sqlite_db: Path):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = make_paper(engine)
    strategy = BuyIfFlatStrategy()
    account_id = paper.create_account("Persistent Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name=strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )

    first = paper.run_one_tick(run_id, strategy, StrategyStatus.APPROVED)
    second = paper.run_one_tick(run_id, strategy, StrategyStatus.APPROVED)

    with session_scope(engine) as session:
        order_count = len(session.scalars(select(PaperOrderORM).where(PaperOrderORM.run_id == run_id)).all())
        fill_count = len(session.scalars(select(PaperFillORM).where(PaperFillORM.run_id == run_id)).all())
        snapshot_count = len(
            session.scalars(select(PortfolioSnapshotORM).where(PortfolioSnapshotORM.account_id == account_id)).all()
        )

    assert first.idempotent_noop is False
    assert second.idempotent_noop is True
    assert second.orders_created == 0
    assert second.fills_created == 0
    assert second.snapshot_created is False
    assert order_count == 1
    assert fill_count == 1
    assert snapshot_count == 1


def test_later_tick_restores_existing_cash_and_position(legacy_sqlite_db: Path):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = make_paper(engine)
    strategy = BuyIfFlatStrategy()
    account_id = paper.create_account("Persistent Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name=strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )
    paper.run_one_tick(run_id, strategy, StrategyStatus.APPROVED)

    with session_scope(engine) as session:
        instrument = InstrumentRepository(session).get_by_symbol("000001")
        MarketDataRepository(session).upsert_daily_bar(
            instrument_id=instrument.id,
            timestamp=date(2026, 5, 9),
            open=Decimal("11.00"),
            high=Decimal("11.30"),
            low=Decimal("10.90"),
            close=Decimal("11.10"),
            volume=Decimal("200000"),
            source="legacy_sqlite",
            adjusted="qfq",
        )

    result = paper.run_one_tick(run_id, strategy, StrategyStatus.APPROVED)

    with session_scope(engine) as session:
        snapshots = session.scalars(
            select(PortfolioSnapshotORM)
            .where(PortfolioSnapshotORM.account_id == account_id)
            .order_by(PortfolioSnapshotORM.timestamp)
        ).all()
        orders = session.scalars(select(PaperOrderORM).where(PaperOrderORM.run_id == run_id)).all()

    assert result.idempotent_noop is False
    assert result.orders_created == 0
    assert strategy.seen_quantities[-1] == 100
    assert strategy.seen_cash[-1] < Decimal("100000")
    assert len(orders) == 1
    assert len(snapshots) == 2
    assert snapshots[-1].market_value == Decimal("1110.000000")
```

- [ ] **Step 2: Run persistent paper tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_paper_engine.py -q
```

Expected:

```text
TypeError: PaperTradingEngine.run_one_tick() got an unexpected keyword argument 'run_id'
```

- [ ] **Step 3: Extend paper repositories for tick writes**

Modify `src/quant_trading/paper/repositories.py` by updating imports:

```python
from quant_trading.core.enums import CashLedgerEventType, PaperOrderStatus
from quant_trading.core.models import Fill, OrderIntent
from quant_trading.storage.models import PaperFillORM, PaperOrderORM, PortfolioSnapshotORM, RiskDecisionORM
```

Add these methods inside `PaperStateRepository`:

```python
    def create_order(self, run: PaperRunORM, intent: OrderIntent, submitted_at: date) -> PaperOrderORM:
        order = PaperOrderORM(
            run_id=run.id,
            account_id=run.account_id,
            instrument_id=intent.instrument_id,
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            reason=intent.reason,
            status=PaperOrderStatus.CREATED.value,
            submitted_at=submitted_at,
        )
        self.session.add(order)
        self.session.flush()
        return order

    def record_risk_decision(self, run_id: int, order_id: int, decision) -> RiskDecisionORM:
        row = RiskDecisionORM(
            run_id=run_id,
            order_id=order_id,
            decision=decision.decision.value,
            rule_name=decision.rule_name,
            message=decision.message,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def mark_order_rejected(self, order: PaperOrderORM, decision_value: str) -> None:
        order.status = PaperOrderStatus.RISK_REJECTED.value
        order.risk_decision = decision_value
        self.session.flush()

    def mark_order_skipped(self, order: PaperOrderORM, decision_value: str) -> None:
        order.status = PaperOrderStatus.SKIPPED.value
        order.risk_decision = decision_value
        self.session.flush()

    def record_fill(self, run: PaperRunORM, order: PaperOrderORM, fill: Fill) -> PaperFillORM:
        row = PaperFillORM(
            run_id=run.id,
            account_id=run.account_id,
            order_id=order.id,
            instrument_id=fill.instrument_id,
            symbol=fill.symbol,
            side=fill.side.value,
            quantity=fill.quantity,
            price=fill.price,
            commission=fill.commission,
            slippage=fill.slippage,
            filled_at=fill.filled_at,
        )
        self.session.add(row)
        self.session.flush()
        order.status = PaperOrderStatus.FILLED.value
        order.risk_decision = "approved"
        self.session.flush()
        return row

    def append_cash_ledger(
        self,
        account_id: int,
        run_id: int | None,
        order_id: int | None,
        fill_id: int | None,
        event_type: CashLedgerEventType,
        amount: Decimal,
        cash_after: Decimal,
        currency: str,
        occurred_at: date,
    ) -> CashLedgerORM:
        row = CashLedgerORM(
            account_id=account_id,
            run_id=run_id,
            order_id=order_id,
            fill_id=fill_id,
            event_type=event_type.value,
            amount=amount,
            cash_after=cash_after,
            currency=currency,
            occurred_at=occurred_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def upsert_positions(self, portfolio: Portfolio, processed_at: date) -> None:
        for position in portfolio.positions.values():
            row = self.session.scalar(
                select(PaperPositionORM).where(
                    PaperPositionORM.account_id == portfolio.account_id,
                    PaperPositionORM.instrument_id == position.instrument_id,
                )
            )
            if row is None:
                row = PaperPositionORM(
                    account_id=portfolio.account_id,
                    instrument_id=position.instrument_id,
                    symbol=position.symbol,
                    quantity=position.quantity,
                    avg_cost=position.avg_cost,
                    market_price=position.market_price,
                    realized_pnl=portfolio.realized_pnl,
                    updated_at=processed_at,
                )
                self.session.add(row)
            else:
                row.quantity = position.quantity
                row.avg_cost = position.avg_cost
                row.market_price = position.market_price
                row.realized_pnl = portfolio.realized_pnl
                row.updated_at = processed_at
        self.session.flush()

    def record_snapshot(self, portfolio: Portfolio, processed_at: date) -> PortfolioSnapshotORM:
        row = PortfolioSnapshotORM(
            account_id=portfolio.account_id,
            timestamp=processed_at,
            equity=portfolio.equity,
            cash=portfolio.cash,
            market_value=portfolio.market_value,
            realized_pnl=portfolio.realized_pnl,
            unrealized_pnl=sum(
                (position.unrealized_pnl for position in portfolio.positions.values()),
                Decimal("0"),
            ),
            drawdown=portfolio.drawdown,
        )
        self.session.add(row)
        self.session.flush()
        return row
```

- [ ] **Step 4: Replace paper engine tick API**

Modify `src/quant_trading/paper/engine.py`.

Replace `PaperTickSummary` with:

```python
@dataclass(frozen=True)
class PaperTickSummary:
    run_id: int
    account_id: int
    processed_at: date | None
    orders_created: int
    orders_filled: int
    orders_rejected: int
    fills_created: int
    snapshot_created: bool
    risk_decision_count: int
    idempotent_noop: bool
```

Replace the old `run_one_tick` method with:

```python
    def run_one_tick(
        self,
        run_id: int,
        strategy: Strategy,
        strategy_status: StrategyStatus,
    ) -> PaperTickSummary:
        with session_scope(self.engine) as session:
            repo = PaperStateRepository(session)
            run = repo.load_run(run_id)
            bars = MarketDataRepository(session).list_bars(run.symbol)
            if not bars:
                raise ValueError(f"no market bars found for symbol: {run.symbol}")

            latest = bars[-1]
            if run.last_processed_at is not None and latest.timestamp <= run.last_processed_at:
                return PaperTickSummary(
                    run_id=run.id,
                    account_id=run.account_id,
                    processed_at=latest.timestamp,
                    orders_created=0,
                    orders_filled=0,
                    orders_rejected=0,
                    fills_created=0,
                    snapshot_created=False,
                    risk_decision_count=0,
                    idempotent_noop=True,
                )

            portfolio = repo.load_portfolio(run.account_id)
            orders_created = 0
            orders_filled = 0
            orders_rejected = 0
            fills_created = 0
            risk_decision_count = 0

            for intent in strategy.on_bar(bars, portfolio):
                order = repo.create_order(run, intent, latest.timestamp)
                orders_created += 1
                decision = self.risk_engine.check_order(intent, latest, portfolio, strategy_status)
                repo.record_risk_decision(run.id, order.id, decision)
                risk_decision_count += 1
                if decision.decision is not RiskDecisionType.APPROVED:
                    repo.mark_order_rejected(order, decision.decision.value)
                    orders_rejected += 1
                    continue

                fill = self.broker.execute_market_order(intent, latest)
                try:
                    updated_portfolio = apply_fill(portfolio, fill)
                except ValueError as exc:
                    if str(exc) == "insufficient cash for buy fill":
                        repo.mark_order_skipped(order, decision.decision.value)
                        continue
                    raise

                fill_row = repo.record_fill(run, order, fill)
                notional = fill.price * Decimal(fill.quantity)
                if fill.side.value == "buy":
                    repo.append_cash_ledger(
                        account_id=run.account_id,
                        run_id=run.id,
                        order_id=order.id,
                        fill_id=fill_row.id,
                        event_type=CashLedgerEventType.BUY_NOTIONAL,
                        amount=-notional,
                        cash_after=updated_portfolio.cash + fill.commission,
                        currency="CNY",
                        occurred_at=latest.timestamp,
                    )
                    repo.append_cash_ledger(
                        account_id=run.account_id,
                        run_id=run.id,
                        order_id=order.id,
                        fill_id=fill_row.id,
                        event_type=CashLedgerEventType.COMMISSION,
                        amount=-fill.commission,
                        cash_after=updated_portfolio.cash,
                        currency="CNY",
                        occurred_at=latest.timestamp,
                    )
                else:
                    repo.append_cash_ledger(
                        account_id=run.account_id,
                        run_id=run.id,
                        order_id=order.id,
                        fill_id=fill_row.id,
                        event_type=CashLedgerEventType.SELL_NOTIONAL,
                        amount=notional,
                        cash_after=updated_portfolio.cash + fill.commission,
                        currency="CNY",
                        occurred_at=latest.timestamp,
                    )
                    repo.append_cash_ledger(
                        account_id=run.account_id,
                        run_id=run.id,
                        order_id=order.id,
                        fill_id=fill_row.id,
                        event_type=CashLedgerEventType.COMMISSION,
                        amount=-fill.commission,
                        cash_after=updated_portfolio.cash,
                        currency="CNY",
                        occurred_at=latest.timestamp,
                    )
                portfolio = updated_portfolio
                orders_filled += 1
                fills_created += 1

            for position in portfolio.positions.values():
                if position.instrument_id == latest.instrument_id:
                    position.market_price = latest.close
            repo.upsert_positions(portfolio, latest.timestamp)
            repo.record_snapshot(portfolio, latest.timestamp)
            run.last_processed_at = latest.timestamp
            return PaperTickSummary(
                run_id=run.id,
                account_id=run.account_id,
                processed_at=latest.timestamp,
                orders_created=orders_created,
                orders_filled=orders_filled,
                orders_rejected=orders_rejected,
                fills_created=fills_created,
                snapshot_created=True,
                risk_decision_count=risk_decision_count,
                idempotent_noop=False,
            )
```

Also add imports at the top:

```python
from quant_trading.core.enums import CashLedgerEventType, PaperRunStatus
from quant_trading.paper.repositories import PaperStateRepository
```

After `run = repo.load_run(run_id)`, add the run-state guard:

```python
            if run.status != PaperRunStatus.RUNNING.value:
                raise ValueError(f"paper run is not running: {run.id}")
```

- [ ] **Step 5: Run persistent paper engine tests**

Run:

```bash
python -m pytest tests/integration/test_paper_engine.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Run lifecycle and paper tests**

Run:

```bash
python -m pytest tests/integration/test_paper_lifecycle.py tests/integration/test_paper_engine.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 7: Commit persistent tick execution**

Run:

```bash
git add src/quant_trading/paper/engine.py src/quant_trading/paper/repositories.py tests/integration/test_paper_engine.py
git commit -m "feat: persist paper tick execution"
```

Expected commit summary includes:

```text
feat: persist paper tick execution
```

---

### Task 4: Rejected, Skipped, And Zero-Quantity Paper Orders

**Files:**
- Modify: `tests/integration/test_paper_engine.py`
- Modify: `src/quant_trading/paper/engine.py`
- Modify: `src/quant_trading/paper/repositories.py`

- [ ] **Step 1: Add rejected, skipped, and sell-to-zero tests**

Append to `tests/integration/test_paper_engine.py`:

```python
class OversizedBuyStrategy:
    name = "oversized_buy"

    def on_bar(self, bars, portfolio):
        latest = bars[-1]
        return [
            OrderIntent(
                instrument_id=latest.instrument_id,
                symbol=latest.symbol,
                side=OrderSide.BUY,
                quantity=1000000,
                reason="oversized_order",
            )
        ]


class SellAllStrategy:
    name = "sell_all"

    def on_bar(self, bars, portfolio):
        latest = bars[-1]
        position = portfolio.positions.get(latest.instrument_id)
        if position is None or position.quantity <= 0:
            return []
        return [
            OrderIntent(
                instrument_id=latest.instrument_id,
                symbol=latest.symbol,
                side=OrderSide.SELL,
                quantity=position.quantity,
                reason="sell_to_zero_for_audit",
            )
        ]


def test_rejected_strategy_status_creates_order_and_risk_decision_without_fill(
    legacy_sqlite_db: Path,
):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = make_paper(engine)
    strategy = BuyIfFlatStrategy()
    account_id = paper.create_account("Persistent Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name=strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )

    result = paper.run_one_tick(run_id, strategy, StrategyStatus.DRAFT)

    with session_scope(engine) as session:
        orders = session.scalars(select(PaperOrderORM).where(PaperOrderORM.run_id == run_id)).all()
        fills = session.scalars(select(PaperFillORM).where(PaperFillORM.run_id == run_id)).all()
        positions = session.scalars(
            select(PaperPositionORM).where(PaperPositionORM.account_id == account_id)
        ).all()
        ledger = session.scalars(
            select(CashLedgerORM).where(CashLedgerORM.account_id == account_id).order_by(CashLedgerORM.id)
        ).all()
        decisions = session.scalars(select(RiskDecisionORM).where(RiskDecisionORM.run_id == run_id)).all()

    assert result.orders_created == 1
    assert result.orders_rejected == 1
    assert result.fills_created == 0
    assert orders[0].status == "risk_rejected"
    assert orders[0].risk_decision == "rejected"
    assert len(decisions) == 1
    assert decisions[0].order_id == orders[0].id
    assert fills == []
    assert positions == []
    assert [row.event_type for row in ledger] == ["initial_deposit"]


def test_insufficient_cash_marks_order_skipped_without_cash_or_position_change(
    legacy_sqlite_db: Path,
):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = make_paper(engine)
    strategy = OversizedBuyStrategy()
    account_id = paper.create_account("Persistent Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name=strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )

    result = paper.run_one_tick(run_id, strategy, StrategyStatus.APPROVED)

    with session_scope(engine) as session:
        orders = session.scalars(select(PaperOrderORM).where(PaperOrderORM.run_id == run_id)).all()
        fills = session.scalars(select(PaperFillORM).where(PaperFillORM.run_id == run_id)).all()
        positions = session.scalars(
            select(PaperPositionORM).where(PaperPositionORM.account_id == account_id)
        ).all()
        ledger = session.scalars(
            select(CashLedgerORM).where(CashLedgerORM.account_id == account_id).order_by(CashLedgerORM.id)
        ).all()

    assert result.orders_created == 1
    assert result.orders_filled == 0
    assert result.fills_created == 0
    assert orders[0].status == "skipped"
    assert orders[0].risk_decision == "approved"
    assert fills == []
    assert positions == []
    assert [row.event_type for row in ledger] == ["initial_deposit"]
    assert ledger[0].cash_after == Decimal("100000.000000")


def test_sell_to_zero_retains_position_row_for_audit(legacy_sqlite_db: Path):
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = make_paper(engine)
    buy_strategy = BuyIfFlatStrategy()
    sell_strategy = SellAllStrategy()
    account_id = paper.create_account("Persistent Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=buy_strategy,
        strategy_name=buy_strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )
    paper.run_one_tick(run_id, buy_strategy, StrategyStatus.APPROVED)

    with session_scope(engine) as session:
        instrument = InstrumentRepository(session).get_by_symbol("000001")
        MarketDataRepository(session).upsert_daily_bar(
            instrument_id=instrument.id,
            timestamp=date(2026, 5, 9),
            open=Decimal("11.00"),
            high=Decimal("11.30"),
            low=Decimal("10.90"),
            close=Decimal("11.10"),
            volume=Decimal("200000"),
            source="legacy_sqlite",
            adjusted="qfq",
        )

    result = paper.run_one_tick(run_id, sell_strategy, StrategyStatus.APPROVED)

    with session_scope(engine) as session:
        orders = session.scalars(select(PaperOrderORM).where(PaperOrderORM.run_id == run_id)).all()
        fills = session.scalars(select(PaperFillORM).where(PaperFillORM.run_id == run_id)).all()
        positions = session.scalars(
            select(PaperPositionORM).where(PaperPositionORM.account_id == account_id)
        ).all()
        ledger = session.scalars(
            select(CashLedgerORM).where(CashLedgerORM.account_id == account_id).order_by(CashLedgerORM.id)
        ).all()

    assert result.orders_created == 1
    assert result.orders_filled == 1
    assert result.fills_created == 1
    assert len(orders) == 2
    assert orders[-1].status == "filled"
    assert len(fills) == 2
    assert len(positions) == 1
    assert positions[0].quantity == 0
    assert positions[0].realized_pnl != Decimal("0")
    assert [row.event_type for row in ledger] == [
        "initial_deposit",
        "buy_notional",
        "commission",
        "sell_notional",
        "commission",
    ]
```

- [ ] **Step 2: Run new tests and verify failure**

Run:

```bash
python -m pytest tests/integration/test_paper_engine.py::test_rejected_strategy_status_creates_order_and_risk_decision_without_fill tests/integration/test_paper_engine.py::test_insufficient_cash_marks_order_skipped_without_cash_or_position_change tests/integration/test_paper_engine.py::test_sell_to_zero_retains_position_row_for_audit -q
```

Expected:

```text
FAILED
```

The rejected/skipped tests may pass if Task 3 already handled those branches. The sell-to-zero test must fail before Step 5 because `apply_fill()` removes zero-quantity positions from the in-memory portfolio and Task 3's repository only upserts active positions.

- [ ] **Step 3: Fix rejected order counters**

In `src/quant_trading/paper/engine.py`, ensure the rejected branch increments `orders_rejected` and does not write fills, positions, or non-initial ledger rows:

```python
                if decision.decision is not RiskDecisionType.APPROVED:
                    repo.mark_order_rejected(order, decision.decision.value)
                    orders_rejected += 1
                    continue
```

- [ ] **Step 4: Fix skipped order accounting**

In `src/quant_trading/paper/engine.py`, ensure the insufficient cash branch uses `mark_order_skipped()` and does not change `portfolio`:

```python
                except ValueError as exc:
                    if str(exc) == "insufficient cash for buy fill":
                        repo.mark_order_skipped(order, decision.decision.value)
                        continue
                    raise
```

- [ ] **Step 5: Retain zero-quantity position rows**

Modify `PaperStateRepository.upsert_positions()` in `src/quant_trading/paper/repositories.py`:

```python
    def upsert_positions(
        self,
        portfolio: Portfolio,
        processed_at: date,
        touched_instrument_ids: set[int] | None = None,
    ) -> None:
        active_instrument_ids: set[int] = set()
        for position in portfolio.positions.values():
            active_instrument_ids.add(position.instrument_id)
            row = self.session.scalar(
                select(PaperPositionORM).where(
                    PaperPositionORM.account_id == portfolio.account_id,
                    PaperPositionORM.instrument_id == position.instrument_id,
                )
            )
            if row is None:
                row = PaperPositionORM(
                    account_id=portfolio.account_id,
                    instrument_id=position.instrument_id,
                    symbol=position.symbol,
                    quantity=position.quantity,
                    avg_cost=position.avg_cost,
                    market_price=position.market_price,
                    realized_pnl=portfolio.realized_pnl,
                    updated_at=processed_at,
                )
                self.session.add(row)
            else:
                row.quantity = position.quantity
                row.avg_cost = position.avg_cost
                row.market_price = position.market_price
                row.realized_pnl = portfolio.realized_pnl
                row.updated_at = processed_at

        for instrument_id in set(touched_instrument_ids or set()) - active_instrument_ids:
            row = self.session.scalar(
                select(PaperPositionORM).where(
                    PaperPositionORM.account_id == portfolio.account_id,
                    PaperPositionORM.instrument_id == instrument_id,
                )
            )
            if row is not None:
                row.quantity = 0
                row.realized_pnl = portfolio.realized_pnl
                row.updated_at = processed_at
        self.session.flush()
```

Modify `PaperTradingEngine.run_one_tick()` in `src/quant_trading/paper/engine.py` to track instruments touched by fills:

```python
            touched_instrument_ids: set[int] = set()

            for intent in strategy.on_bar(bars, portfolio):
                order = repo.create_order(run, intent, latest.timestamp)
                orders_created += 1
```

After `fill_row = repo.record_fill(run, order, fill)`, add:

```python
                touched_instrument_ids.add(fill.instrument_id)
```

Replace the position persistence call:

```python
            repo.upsert_positions(
                portfolio=portfolio,
                processed_at=latest.timestamp,
                touched_instrument_ids=touched_instrument_ids,
            )
```

This keeps a row with `quantity = 0` when a sell closes the full position, while still loading only non-zero rows into the active in-memory portfolio on later ticks.

- [ ] **Step 6: Run rejected, skipped, and zero-position tests**

Run:

```bash
python -m pytest tests/integration/test_paper_engine.py::test_rejected_strategy_status_creates_order_and_risk_decision_without_fill tests/integration/test_paper_engine.py::test_insufficient_cash_marks_order_skipped_without_cash_or_position_change tests/integration/test_paper_engine.py::test_sell_to_zero_retains_position_row_for_audit -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Run full paper engine tests**

Run:

```bash
python -m pytest tests/integration/test_paper_engine.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 8: Commit rejected/skipped/zero-position coverage**

Run:

```bash
git add src/quant_trading/paper/engine.py src/quant_trading/paper/repositories.py tests/integration/test_paper_engine.py
git commit -m "test: cover paper order edge states"
```

Expected commit summary includes:

```text
test: cover paper order edge states
```

---

### Task 5: Paper Account Read APIs

**Files:**
- Modify: `src/quant_trading/api/routes/paper.py`
- Modify: `tests/integration/test_api.py`

- [ ] **Step 1: Add API tests for persisted paper state**

Append to `tests/integration/test_api.py`:

```python
from quant_trading.core.enums import OrderSide, StrategyStatus
from quant_trading.core.models import OrderIntent
from quant_trading.paper.engine import PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import MaxOrderValueRule, NoTradeWithoutDataRule, PriceSanityRule, StrategyStatusRule
from quant_trading.storage.migrate_legacy import import_legacy_sqlite


class ApiBuyIfFlatStrategy:
    name = "api_buy_if_flat"

    def on_bar(self, bars, portfolio):
        latest = bars[-1]
        if latest.instrument_id in portfolio.positions:
            return []
        return [
            OrderIntent(
                instrument_id=latest.instrument_id,
                symbol=latest.symbol,
                side=OrderSide.BUY,
                quantity=100,
                reason="api_paper_tick",
            )
        ]


def seed_paper_run(engine, legacy_sqlite_db):
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine(
            [
                StrategyStatusRule(),
                NoTradeWithoutDataRule(),
                PriceSanityRule(),
                MaxOrderValueRule(max_order_value=Decimal("100000")),
            ]
        ),
    )
    strategy = ApiBuyIfFlatStrategy()
    account_id = paper.create_account("API Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name=strategy.name,
        strategy_status=StrategyStatus.APPROVED,
    )
    paper.run_one_tick(run_id, strategy, StrategyStatus.APPROVED)
    return account_id, run_id


def test_paper_read_apis_list_persisted_account_run_and_execution_state(legacy_sqlite_db):
    client, engine = make_client()
    account_id, run_id = seed_paper_run(engine, legacy_sqlite_db)

    accounts = client.get("/paper/accounts")
    account = client.get(f"/paper/accounts/{account_id}")
    runs = client.get("/paper/runs")
    run = client.get(f"/paper/runs/{run_id}")
    positions = client.get(f"/paper/accounts/{account_id}/positions")
    ledger = client.get(f"/paper/accounts/{account_id}/cash-ledger")
    orders = client.get(f"/paper/runs/{run_id}/orders")
    fills = client.get(f"/paper/runs/{run_id}/fills")
    decisions = client.get(f"/paper/runs/{run_id}/risk-decisions")
    snapshots = client.get(f"/paper/runs/{run_id}/snapshots")

    assert accounts.status_code == 200
    assert account.status_code == 200
    assert runs.status_code == 200
    assert run.status_code == 200
    assert positions.status_code == 200
    assert ledger.status_code == 200
    assert orders.status_code == 200
    assert fills.status_code == 200
    assert decisions.status_code == 200
    assert snapshots.status_code == 200
    assert accounts.json()[0]["id"] == account_id
    assert account.json()["name"] == "API Paper"
    assert runs.json()[0]["id"] == run_id
    assert run.json()["symbol"] == "000001"
    assert positions.json()[0]["quantity"] == 100
    assert [row["event_type"] for row in ledger.json()] == [
        "initial_deposit",
        "buy_notional",
        "commission",
    ]
    assert orders.json()[0]["status"] == "filled"
    assert fills.json()[0]["quantity"] == 100
    assert decisions.json()[0]["decision"] == "approved"
    assert snapshots.json()[0]["account_id"] == account_id
```

- [ ] **Step 2: Run API test and verify failure**

Run:

```bash
python -m pytest tests/integration/test_api.py::test_paper_read_apis_list_persisted_account_run_and_execution_state -q
```

Expected:

```text
FAILED
```

The first failing response should be `404` for `/paper/accounts`.

- [ ] **Step 3: Implement paper read endpoints**

Replace `src/quant_trading/api/routes/paper.py` with:

```python
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from quant_trading.storage.db import session_scope
from quant_trading.storage.models import (
    CashLedgerORM,
    PaperAccountORM,
    PaperFillORM,
    PaperOrderORM,
    PaperPositionORM,
    PaperRunORM,
    PortfolioSnapshotORM,
    RiskDecisionORM,
)

router = APIRouter()


def _not_found(name: str, ident: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{name} not found: {ident}")


@router.get("/paper/accounts")
def list_paper_accounts(request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(select(PaperAccountORM).order_by(PaperAccountORM.id.desc())).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "base_currency": row.base_currency,
                "initial_cash": float(row.initial_cash),
                "status": row.status,
            }
            for row in rows
        ]


@router.get("/paper/accounts/{account_id}")
def get_paper_account(account_id: int, request: Request) -> dict:
    with session_scope(request.app.state.engine) as session:
        row = session.get(PaperAccountORM, account_id)
        if row is None:
            raise _not_found("paper account", account_id)
        return {
            "id": row.id,
            "name": row.name,
            "base_currency": row.base_currency,
            "initial_cash": float(row.initial_cash),
            "status": row.status,
        }


@router.get("/paper/accounts/{account_id}/positions")
def list_paper_positions(account_id: int, request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(
            select(PaperPositionORM)
            .where(PaperPositionORM.account_id == account_id)
            .order_by(PaperPositionORM.symbol)
        ).all()
        return [
            {
                "account_id": row.account_id,
                "instrument_id": row.instrument_id,
                "symbol": row.symbol,
                "quantity": row.quantity,
                "avg_cost": float(row.avg_cost),
                "market_price": float(row.market_price),
                "realized_pnl": float(row.realized_pnl),
            }
            for row in rows
        ]


@router.get("/paper/accounts/{account_id}/cash-ledger")
def list_cash_ledger(account_id: int, request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(
            select(CashLedgerORM)
            .where(CashLedgerORM.account_id == account_id)
            .order_by(CashLedgerORM.id)
        ).all()
        return [
            {
                "id": row.id,
                "account_id": row.account_id,
                "run_id": row.run_id,
                "order_id": row.order_id,
                "fill_id": row.fill_id,
                "event_type": row.event_type,
                "amount": float(row.amount),
                "cash_after": float(row.cash_after),
                "currency": row.currency,
                "occurred_at": row.occurred_at.isoformat(),
            }
            for row in rows
        ]


@router.get("/paper/runs")
def list_paper_runs(request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(select(PaperRunORM).order_by(PaperRunORM.id.desc())).all()
        return [
            {
                "id": row.id,
                "account_id": row.account_id,
                "strategy_name": row.strategy_name,
                "symbol": row.symbol,
                "status": row.status,
                "last_processed_at": row.last_processed_at.isoformat()
                if row.last_processed_at is not None
                else None,
            }
            for row in rows
        ]


@router.get("/paper/runs/{run_id}")
def get_paper_run(run_id: int, request: Request) -> dict:
    with session_scope(request.app.state.engine) as session:
        row = session.get(PaperRunORM, run_id)
        if row is None:
            raise _not_found("paper run", run_id)
        return {
            "id": row.id,
            "account_id": row.account_id,
            "strategy_name": row.strategy_name,
            "symbol": row.symbol,
            "status": row.status,
            "last_processed_at": row.last_processed_at.isoformat()
            if row.last_processed_at is not None
            else None,
        }


@router.get("/paper/runs/{run_id}/orders")
def list_paper_orders(run_id: int, request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(
            select(PaperOrderORM).where(PaperOrderORM.run_id == run_id).order_by(PaperOrderORM.id)
        ).all()
        return [
            {
                "id": row.id,
                "run_id": row.run_id,
                "account_id": row.account_id,
                "symbol": row.symbol,
                "side": row.side,
                "order_type": row.order_type,
                "quantity": row.quantity,
                "status": row.status,
                "risk_decision": row.risk_decision,
                "submitted_at": row.submitted_at.isoformat(),
            }
            for row in rows
        ]


@router.get("/paper/runs/{run_id}/fills")
def list_paper_fills(run_id: int, request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(
            select(PaperFillORM).where(PaperFillORM.run_id == run_id).order_by(PaperFillORM.id)
        ).all()
        return [
            {
                "id": row.id,
                "run_id": row.run_id,
                "account_id": row.account_id,
                "order_id": row.order_id,
                "symbol": row.symbol,
                "side": row.side,
                "quantity": row.quantity,
                "price": float(row.price),
                "commission": float(row.commission),
                "slippage": float(row.slippage),
                "filled_at": row.filled_at.isoformat(),
            }
            for row in rows
        ]


@router.get("/paper/runs/{run_id}/risk-decisions")
def list_paper_risk_decisions(run_id: int, request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(
            select(RiskDecisionORM).where(RiskDecisionORM.run_id == run_id).order_by(RiskDecisionORM.id)
        ).all()
        return [
            {
                "id": row.id,
                "run_id": row.run_id,
                "order_id": row.order_id,
                "decision": row.decision,
                "rule_name": row.rule_name,
                "message": row.message,
            }
            for row in rows
        ]


@router.get("/paper/runs/{run_id}/snapshots")
def list_paper_run_snapshots(run_id: int, request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        run = session.get(PaperRunORM, run_id)
        if run is None:
            raise _not_found("paper run", run_id)
        rows = session.scalars(
            select(PortfolioSnapshotORM)
            .where(PortfolioSnapshotORM.account_id == run.account_id)
            .order_by(PortfolioSnapshotORM.timestamp.desc())
        ).all()
        return [
            {
                "account_id": row.account_id,
                "timestamp": row.timestamp.isoformat(),
                "equity": float(row.equity),
                "cash": float(row.cash),
                "market_value": float(row.market_value),
                "drawdown": float(row.drawdown),
            }
            for row in rows
        ]


@router.get("/paper/snapshots")
def list_paper_snapshots(request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(
            select(PortfolioSnapshotORM).order_by(PortfolioSnapshotORM.timestamp.desc())
        ).all()
        return [
            {
                "account_id": row.account_id,
                "timestamp": row.timestamp.isoformat(),
                "equity": float(row.equity),
                "cash": float(row.cash),
                "market_value": float(row.market_value),
                "drawdown": float(row.drawdown),
            }
            for row in rows
        ]
```

- [ ] **Step 4: Run API test**

Run:

```bash
python -m pytest tests/integration/test_api.py::test_paper_read_apis_list_persisted_account_run_and_execution_state -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Run all API tests**

Run:

```bash
python -m pytest tests/integration/test_api.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit paper read APIs**

Run:

```bash
git add src/quant_trading/api/routes/paper.py tests/integration/test_api.py
git commit -m "feat: expose persisted paper account APIs"
```

Expected commit summary includes:

```text
feat: expose persisted paper account APIs
```

---

### Task 6: Paper Tick Job And Final Verification

**Files:**
- Modify: `src/quant_trading/jobs/tasks.py`
- Modify: `README.md`
- Create: `tests/integration/test_paper_jobs.py`

- [ ] **Step 1: Write failing job test**

Create `tests/integration/test_paper_jobs.py`:

```python
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from quant_trading.core.enums import StrategyStatus
from quant_trading.jobs.tasks import run_paper_tick_task
from quant_trading.paper.engine import PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import MaxOrderValueRule, NoTradeWithoutDataRule, PriceSanityRule, StrategyStatusRule
from quant_trading.storage.db import create_all, make_engine
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.storage.models import PaperFillORM
from quant_trading.storage.db import session_scope
from quant_trading.strategy.builtin.ma_cross import MACrossStrategy


def test_run_paper_tick_task_runs_existing_paper_run(tmp_path: Path, legacy_sqlite_db: Path):
    database_path = tmp_path / "paper.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    engine = make_engine(database_url)
    create_all(engine)
    import_legacy_sqlite(legacy_sqlite_db, engine)
    paper = PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine(
            [
                StrategyStatusRule(),
                NoTradeWithoutDataRule(),
                PriceSanityRule(),
                MaxOrderValueRule(max_order_value=Decimal("100000")),
            ]
        ),
    )
    strategy = MACrossStrategy(short_window=5, long_window=20, order_size=100)
    account_id = paper.create_account("Job Paper", Decimal("100000"))
    run_id = paper.start_run(
        account_id=account_id,
        symbol="000001",
        strategy=strategy,
        strategy_name="ma_cross",
        strategy_status=StrategyStatus.APPROVED,
    )

    result = run_paper_tick_task(database_url=database_url, run_id=run_id)

    with session_scope(engine) as session:
        fills = session.scalars(select(PaperFillORM).where(PaperFillORM.run_id == run_id)).all()

    assert result["run_id"] == run_id
    assert result["account_id"] == account_id
    assert result["idempotent_noop"] is False
    assert result["snapshot_created"] is True
    assert len(fills) == result["fills_created"]
```

- [ ] **Step 2: Run job test and verify failure**

Run:

```bash
python -m pytest tests/integration/test_paper_jobs.py -q
```

Expected:

```text
ImportError: cannot import name 'run_paper_tick_task'
```

- [ ] **Step 3: Implement job wrapper**

Modify `src/quant_trading/jobs/tasks.py` by appending:

```python
from quant_trading.core.enums import StrategyStatus
from quant_trading.paper.engine import PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import (
    MaxOrderValueRule,
    NoTradeWithoutDataRule,
    PriceSanityRule,
    StrategyStatusRule,
)


def run_paper_tick_task(database_url: str, run_id: int) -> dict:
    engine = make_engine(database_url)
    paper = PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine(
            [
                StrategyStatusRule(),
                NoTradeWithoutDataRule(),
                PriceSanityRule(),
                MaxOrderValueRule(max_order_value=Decimal("100000")),
            ]
        ),
    )
    result = paper.run_one_tick(
        run_id=run_id,
        strategy=MACrossStrategy(short_window=5, long_window=20, order_size=100),
        strategy_status=StrategyStatus.APPROVED,
    )
    return {
        "run_id": result.run_id,
        "account_id": result.account_id,
        "processed_at": str(result.processed_at) if result.processed_at is not None else None,
        "orders_created": result.orders_created,
        "orders_filled": result.orders_filled,
        "orders_rejected": result.orders_rejected,
        "fills_created": result.fills_created,
        "snapshot_created": result.snapshot_created,
        "risk_decision_count": result.risk_decision_count,
        "idempotent_noop": result.idempotent_noop,
    }
```

- [ ] **Step 4: Update README**

Modify `README.md` by replacing the paper trading bullet:

```markdown
- Running a persistent, risk-gated paper trading account with simulated orders, fills, positions, cash ledger, and snapshots.
```

Add these API URLs under the API block:

```text
http://localhost:8000/paper/accounts
http://localhost:8000/paper/runs
```

- [ ] **Step 5: Run job test**

Run:

```bash
python -m pytest tests/integration/test_paper_jobs.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run paper/API/job tests**

Run:

```bash
python -m pytest tests/integration/test_paper_lifecycle.py tests/integration/test_paper_engine.py tests/integration/test_api.py tests/integration/test_paper_jobs.py -q
```

Expected:

```text
14 passed
```

- [ ] **Step 7: Run full test suite**

Run:

```bash
python -m pytest tests -q
```

Expected:

```text
32 passed
```

- [ ] **Step 8: Validate Docker Compose config**

Run:

```bash
docker compose config
```

Expected:

```text
services:
```

- [ ] **Step 9: Check worktree status**

Run:

```bash
git status --short
```

Expected output contains only planned files for this task before commit:

```text
 M README.md
 M src/quant_trading/jobs/tasks.py
?? tests/integration/test_paper_jobs.py
```

- [ ] **Step 10: Commit job and docs**

Run:

```bash
git add README.md src/quant_trading/jobs/tasks.py tests/integration/test_paper_jobs.py
git commit -m "feat: add paper tick job task"
```

Expected commit summary includes:

```text
feat: add paper tick job task
```

---

## Final Verification

After all tasks are complete, run:

```bash
python -m pytest tests -q
docker compose config
git status --short
git log --oneline -10
```

Expected:

```text
32 passed
services:
```

`git status --short` should be empty in the implementation worktree. If the main `django-app` checkout still has `M legacy/django_app/quant_web/settings.py`, preserve it as user work and do not include it in this stage 2 branch.

## Self-Review

Spec coverage:

- Persistent paper accounts: Task 2.
- Paper runs: Task 2.
- Orders, fills, positions, ledger schema: Task 1.
- Tick state restoration: Task 3.
- Risk decisions tied to run and order: Task 3 and Task 4.
- Idempotent same-bar tick: Task 3.
- Rejected and skipped order behavior: Task 4.
- Zero-quantity position row retention for auditability: Task 4.
- Read APIs: Task 5.
- Job wrapper: Task 6.
- Single-strategy/single-symbol implementation with future-proof schema: Task 1 and Task 2.

Placeholder scan:

- The plan contains no unresolved marker text.
- Each task has concrete files, tests, commands, and expected outputs.
- Command APIs are deliberately excluded from required implementation and are not left as hidden work.

Type consistency:

- ORM names match tests and implementation snippets: `PaperRunORM`, `PaperOrderORM`, `PaperFillORM`, `PaperPositionORM`, `CashLedgerORM`.
- Engine API is consistent across tasks: `create_account()`, `start_run()`, `run_one_tick(run_id, strategy, strategy_status)`.
- Summary fields match tests, API/job returns, and spec: `orders_created`, `orders_filled`, `orders_rejected`, `fills_created`, `snapshot_created`, `risk_decision_count`, `idempotent_noop`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-16-quant-trading-paper-account-v2.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

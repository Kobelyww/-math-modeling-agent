# Quant Trading Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first productized vertical slice of `quant-trading`: local A-share data migration, normalized storage, portfolio backtesting, risk-gated paper trading, and FastAPI status APIs.

**Architecture:** Rebuild the product core under `src/quant_trading/` while keeping the current Django app as legacy reference. Domain objects stay framework-free; storage, backtest, paper trading, risk, jobs, and API are separate modules. The first milestone uses existing `000001` A-share data from the legacy SQLite database and does not place real broker orders.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL for runtime, SQLite for tests and legacy import, Redis/RQ for background jobs, pytest.

---

## Scope Lock

This plan implements the first milestone from `docs/superpowers/specs/2026-06-16-quant-trading-productization-design.md`.

Implemented in this milestone:

- New `src/quant_trading/` package and `pyproject.toml`.
- Framework-free core models for bars, orders, fills, positions, portfolios, strategies, and risk decisions.
- SQLAlchemy storage models and repositories.
- Local import of existing `quant-trading/django_app/db.sqlite3` `000001` data into the new schema.
- MA cross strategy migrated to the new strategy interface.
- Portfolio-level backtest that persists normalized equity, orders, fills, positions, and metrics.
- Risk engine with hard rules for exposure, order notional, data availability, price sanity, and strategy approval.
- Paper trading one-tick flow using a simulated broker.
- FastAPI endpoints for health, instruments, backtest runs, paper runs, and account snapshots.
- Docker Compose for Postgres, Redis, API, and worker.

Not implemented in this milestone:

- Real broker or exchange adapters.
- Arbitrary uploaded strategy execution.
- Intraday, tick-level, margin, short selling, futures, options, or leveraged trading.
- Full React frontend.

## Repository And Branch Rules

Implementation work happens in the nested repository:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
```

Current observed state before plan creation:

- Branch: `django-app`
- Dirty file: `django_app/quant_web/settings.py`
- That dirty change makes Django `SECRET_KEY` and `DEBUG` environment-driven. Treat it as user work and do not revert it.

Start implementation with:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git switch -c codex/quant-paper-platform-v1
```

Expected:

```text
Switched to a new branch 'codex/quant-paper-platform-v1'
```

If Git refuses because of local changes, stop and ask the user whether to commit, stash, or keep the dirty Django settings change on the existing branch.

## File Structure

Create or modify these files in `quant-trading/`:

```text
pyproject.toml
docker-compose.yml
Dockerfile
.env.example
README.md

src/quant_trading/__init__.py
src/quant_trading/api/__init__.py
src/quant_trading/api/routes/__init__.py
src/quant_trading/backtest/__init__.py
src/quant_trading/core/__init__.py
src/quant_trading/core/enums.py
src/quant_trading/core/models.py
src/quant_trading/core/errors.py

src/quant_trading/data/__init__.py
src/quant_trading/data/providers/__init__.py
src/quant_trading/storage/db.py
src/quant_trading/storage/models.py
src/quant_trading/storage/repositories.py
src/quant_trading/storage/migrate_legacy.py

src/quant_trading/data/validation.py
src/quant_trading/data/providers/base.py
src/quant_trading/data/providers/akshare_provider.py

src/quant_trading/strategy/base.py
src/quant_trading/strategy/registry.py
src/quant_trading/strategy/__init__.py
src/quant_trading/strategy/builtin/__init__.py
src/quant_trading/strategy/builtin/ma_cross.py

src/quant_trading/execution/__init__.py
src/quant_trading/execution/commission.py
src/quant_trading/execution/slippage.py
src/quant_trading/execution/simulator.py
src/quant_trading/portfolio/__init__.py
src/quant_trading/portfolio/accounting.py
src/quant_trading/portfolio/metrics.py

src/quant_trading/risk/__init__.py
src/quant_trading/risk/rules.py
src/quant_trading/risk/engine.py

src/quant_trading/backtest/engine.py
src/quant_trading/paper/__init__.py
src/quant_trading/paper/engine.py

src/quant_trading/api/main.py
src/quant_trading/api/routes/health.py
src/quant_trading/api/routes/instruments.py
src/quant_trading/api/routes/backtests.py
src/quant_trading/api/routes/paper.py
src/quant_trading/jobs/__init__.py
src/quant_trading/jobs/queue.py
src/quant_trading/jobs/tasks.py

tests/unit/test_core_models.py
tests/unit/test_accounting.py
tests/unit/test_risk_engine.py
tests/unit/test_ma_cross_strategy.py
tests/integration/test_storage_repositories.py
tests/integration/test_legacy_migration.py
tests/integration/test_backtest_engine.py
tests/integration/test_paper_engine.py
tests/integration/test_api.py
```

Move legacy code near the end of the plan:

```text
legacy/django_app/
legacy/scripts/
legacy/commands/
legacy/skills/
```

Do not delete legacy code until the new vertical slice has passing tests.

---

### Task 1: Package Scaffold And Baseline Tests

**Files:**
- Create: `pyproject.toml`
- Create: `src/quant_trading/__init__.py`
- Create: `src/quant_trading/core/enums.py`
- Create: `src/quant_trading/core/models.py`
- Create: `src/quant_trading/core/errors.py`
- Create: `tests/unit/test_core_models.py`

- [ ] **Step 1: Write failing core model tests**

Create `tests/unit/test_core_models.py`:

```python
from decimal import Decimal

from quant_trading.core.enums import Market, OrderSide, OrderStatus, OrderType
from quant_trading.core.models import Bar, OrderIntent, Portfolio, Position


def test_bar_rejects_invalid_ohlc():
    try:
        Bar(
            instrument_id=1,
            symbol="000001",
            market=Market.A_STOCK,
            timestamp="2026-05-08",
            open=Decimal("10"),
            high=Decimal("9"),
            low=Decimal("8"),
            close=Decimal("8.5"),
            volume=Decimal("1000"),
        )
    except ValueError as exc:
        assert "high must be greater than or equal to open/close/low" in str(exc)
    else:
        raise AssertionError("invalid OHLC should fail")


def test_order_intent_defaults_to_created_market_buy():
    intent = OrderIntent(
        instrument_id=1,
        symbol="000001",
        side=OrderSide.BUY,
        quantity=100,
        reason="ma_cross_entry",
    )

    assert intent.order_type is OrderType.MARKET
    assert intent.status is OrderStatus.CREATED
    assert intent.quantity == 100


def test_portfolio_equity_includes_cash_and_positions():
    portfolio = Portfolio(
        account_id=1,
        cash=Decimal("10000"),
        positions={
            1: Position(
                instrument_id=1,
                symbol="000001",
                quantity=200,
                avg_cost=Decimal("9.50"),
                market_price=Decimal("10.00"),
            )
        },
    )

    assert portfolio.market_value == Decimal("2000.00")
    assert portfolio.equity == Decimal("12000.00")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit/test_core_models.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading'
```

- [ ] **Step 3: Create packaging metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "quant-trading-platform"
version = "0.1.0"
description = "Research and paper-trading platform for productized quant workflows"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "psycopg[binary]>=3.2",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "pandas>=2.2",
  "numpy>=1.26",
  "redis>=5.0",
  "rq>=1.16",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
data = [
  "akshare>=1.14",
  "yfinance>=0.2",
  "ccxt>=4.3",
]
dev = [
  "pytest>=8.2",
  "httpx>=0.27",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `src/quant_trading/__init__.py`:

```python
"""Productized quant research and paper-trading platform."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create package marker files:

```bash
touch src/quant_trading/api/__init__.py
touch src/quant_trading/api/routes/__init__.py
touch src/quant_trading/backtest/__init__.py
touch src/quant_trading/core/__init__.py
touch src/quant_trading/data/__init__.py
touch src/quant_trading/data/providers/__init__.py
touch src/quant_trading/execution/__init__.py
touch src/quant_trading/jobs/__init__.py
touch src/quant_trading/paper/__init__.py
touch src/quant_trading/portfolio/__init__.py
touch src/quant_trading/risk/__init__.py
touch src/quant_trading/storage/__init__.py
touch src/quant_trading/strategy/__init__.py
touch src/quant_trading/strategy/builtin/__init__.py
```

- [ ] **Step 4: Implement core enums**

Create `src/quant_trading/core/enums.py`:

```python
from enum import StrEnum


class Market(StrEnum):
    A_STOCK = "a_stock"
    US_STOCK = "us_stock"
    CRYPTO = "crypto"


class AssetType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"


class Timeframe(StrEnum):
    DAILY = "1d"


class Adjustment(StrEnum):
    NONE = "none"
    QFQ = "qfq"
    HFQ = "hfq"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    CREATED = "created"
    RISK_CHECKED = "risk_checked"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class StrategyStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    DISABLED = "disabled"


class RiskDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REDUCED = "reduced"
    HALTED = "halted"
```

- [ ] **Step 5: Implement framework-free core models**

Create `src/quant_trading/core/models.py`:

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from quant_trading.core.enums import (
    Adjustment,
    Market,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionType,
    Timeframe,
)


def to_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class Bar:
    instrument_id: int
    symbol: str
    market: Market
    timestamp: date | datetime | str
    open: Decimal | int | float | str
    high: Decimal | int | float | str
    low: Decimal | int | float | str
    close: Decimal | int | float | str
    volume: Decimal | int | float | str
    timeframe: Timeframe = Timeframe.DAILY
    amount: Decimal | int | float | str | None = None
    adjusted: Adjustment = Adjustment.QFQ
    source: str = "legacy"

    def __post_init__(self) -> None:
        object.__setattr__(self, "open", to_decimal(self.open))
        object.__setattr__(self, "high", to_decimal(self.high))
        object.__setattr__(self, "low", to_decimal(self.low))
        object.__setattr__(self, "close", to_decimal(self.close))
        object.__setattr__(self, "volume", to_decimal(self.volume))
        if self.amount is not None:
            object.__setattr__(self, "amount", to_decimal(self.amount))
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open/close/low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open/close/high")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")


@dataclass
class OrderIntent:
    instrument_id: int
    symbol: str
    side: OrderSide
    quantity: int
    reason: str
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    status: OrderStatus = OrderStatus.CREATED

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.limit_price is not None:
            self.limit_price = to_decimal(self.limit_price)


@dataclass
class Fill:
    order_id: int | None
    instrument_id: int
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal
    commission: Decimal
    slippage: Decimal
    filled_at: date | datetime | str

    @property
    def notional(self) -> Decimal:
        return self.price * Decimal(self.quantity)


@dataclass
class Position:
    instrument_id: int
    symbol: str
    quantity: int
    avg_cost: Decimal
    market_price: Decimal

    @property
    def market_value(self) -> Decimal:
        return self.market_price * Decimal(self.quantity)

    @property
    def unrealized_pnl(self) -> Decimal:
        return (self.market_price - self.avg_cost) * Decimal(self.quantity)


@dataclass
class Portfolio:
    account_id: int
    cash: Decimal
    positions: dict[int, Position] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    peak_equity: Decimal | None = None

    @property
    def market_value(self) -> Decimal:
        return sum((p.market_value for p in self.positions.values()), Decimal("0"))

    @property
    def equity(self) -> Decimal:
        return self.cash + self.market_value

    @property
    def drawdown(self) -> Decimal:
        peak = self.peak_equity or self.equity
        if peak <= 0:
            return Decimal("0")
        return (peak - self.equity) / peak


@dataclass(frozen=True)
class RiskDecision:
    decision: RiskDecisionType
    rule_name: str
    message: str
    order_intent: OrderIntent | None = None
```

Create `src/quant_trading/core/errors.py`:

```python
class QuantTradingError(Exception):
    """Base exception for quant trading platform errors."""


class DataValidationError(QuantTradingError):
    """Raised when market data is missing or invalid."""


class RiskRejectedError(QuantTradingError):
    """Raised when a risk rule rejects an order."""
```

- [ ] **Step 6: Run core tests and verify they pass**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit/test_core_models.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit scaffold**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add pyproject.toml src/quant_trading tests/unit/test_core_models.py
git commit -m "feat: add productized quant package scaffold"
```

Expected commit summary includes:

```text
feat: add productized quant package scaffold
```

---

### Task 2: Storage Models, Repositories, And Legacy Data Import

**Files:**
- Create: `src/quant_trading/storage/db.py`
- Create: `src/quant_trading/storage/models.py`
- Create: `src/quant_trading/storage/repositories.py`
- Create: `src/quant_trading/storage/migrate_legacy.py`
- Create: `tests/integration/test_storage_repositories.py`
- Create: `tests/integration/test_legacy_migration.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/integration/test_storage_repositories.py`:

```python
from datetime import date
from decimal import Decimal

from quant_trading.core.enums import Market
from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.repositories import InstrumentRepository, MarketDataRepository


def test_insert_instrument_and_daily_bar_round_trip():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)

    with session_scope(engine) as session:
        instruments = InstrumentRepository(session)
        bars = MarketDataRepository(session)

        instrument = instruments.upsert_symbol(
            symbol="000001",
            name="平安银行",
            market=Market.A_STOCK,
            asset_type="stock",
            currency="CNY",
            exchange="SZSE",
        )
        bars.upsert_daily_bar(
            instrument_id=instrument.id,
            timestamp=date(2026, 5, 8),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.90"),
            close=Decimal("10.20"),
            volume=Decimal("123456"),
            source="legacy_sqlite",
            adjusted="qfq",
        )

    with session_scope(engine) as session:
        loaded = MarketDataRepository(session).list_bars("000001")

    assert len(loaded) == 1
    assert loaded[0].symbol == "000001"
    assert loaded[0].close == Decimal("10.200000")
```

Create `tests/integration/test_legacy_migration.py`:

```python
from pathlib import Path

from quant_trading.storage.db import create_all, make_engine, session_scope
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.storage.repositories import InstrumentRepository, MarketDataRepository


def test_import_existing_legacy_sqlite_sample():
    legacy_db = Path("django_app/db.sqlite3")
    assert legacy_db.exists()

    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)

    result = import_legacy_sqlite(legacy_db, engine)

    assert result.imported_symbols >= 1
    assert result.imported_bars >= 100

    with session_scope(engine) as session:
        instrument = InstrumentRepository(session).get_by_symbol("000001")
        bars = MarketDataRepository(session).list_bars("000001")

    assert instrument is not None
    assert instrument.name == "平安银行"
    assert len(bars) >= 100
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_storage_repositories.py tests/integration/test_legacy_migration.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading.storage'
```

- [ ] **Step 3: Implement database session helpers**

Create `src/quant_trading/storage/db.py`:

```python
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from quant_trading.storage.models import Base


def make_engine(database_url: str, echo: bool = False) -> Engine:
    return create_engine(database_url, echo=echo, future=True)


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = make_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 4: Implement SQLAlchemy models**

Create `src/quant_trading/storage/models.py`:

```python
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class InstrumentORM(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    market: Mapped[str] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(32), default="stock")
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    exchange: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bars: Mapped[list["MarketBarORM"]] = relationship(back_populates="instrument")


class MarketBarORM(Base):
    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "timestamp",
            "timeframe",
            "adjusted",
            "source",
            name="uq_market_bar_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(Date, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d")
    open: Mapped[float] = mapped_column(Numeric(18, 6))
    high: Mapped[float] = mapped_column(Numeric(18, 6))
    low: Mapped[float] = mapped_column(Numeric(18, 6))
    close: Mapped[float] = mapped_column(Numeric(18, 6))
    volume: Mapped[float] = mapped_column(Numeric(24, 6))
    amount: Mapped[float | None] = mapped_column(Numeric(24, 6), nullable=True)
    adjusted: Mapped[str] = mapped_column(String(16), default="qfq")
    source: Mapped[str] = mapped_column(String(64), default="legacy")
    ingestion_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    instrument: Mapped[InstrumentORM] = relationship(back_populates="bars")
```

- [ ] **Step 5: Implement repositories**

Create `src/quant_trading/storage/repositories.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_trading.core.enums import Market
from quant_trading.core.models import Bar
from quant_trading.storage.models import InstrumentORM, MarketBarORM


class InstrumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_symbol(self, symbol: str) -> InstrumentORM | None:
        return self.session.scalar(select(InstrumentORM).where(InstrumentORM.symbol == symbol))

    def upsert_symbol(
        self,
        symbol: str,
        name: str,
        market: Market,
        asset_type: str,
        currency: str,
        exchange: str,
    ) -> InstrumentORM:
        existing = self.get_by_symbol(symbol)
        if existing:
            existing.name = name
            existing.market = market.value
            existing.asset_type = asset_type
            existing.currency = currency
            existing.exchange = exchange
            self.session.flush()
            return existing

        instrument = InstrumentORM(
            symbol=symbol,
            name=name,
            market=market.value,
            asset_type=asset_type,
            currency=currency,
            exchange=exchange,
        )
        self.session.add(instrument)
        self.session.flush()
        return instrument


class MarketDataRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_daily_bar(
        self,
        instrument_id: int,
        timestamp: date,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal,
        source: str,
        adjusted: str,
    ) -> MarketBarORM:
        existing = self.session.scalar(
            select(MarketBarORM).where(
                MarketBarORM.instrument_id == instrument_id,
                MarketBarORM.timestamp == timestamp,
                MarketBarORM.timeframe == "1d",
                MarketBarORM.adjusted == adjusted,
                MarketBarORM.source == source,
            )
        )
        if existing:
            existing.open = open
            existing.high = high
            existing.low = low
            existing.close = close
            existing.volume = volume
            self.session.flush()
            return existing

        row = MarketBarORM(
            instrument_id=instrument_id,
            timestamp=timestamp,
            timeframe="1d",
            open=open,
            high=high,
            low=low,
            close=close,
            volume=volume,
            adjusted=adjusted,
            source=source,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_bars(self, symbol: str) -> list[Bar]:
        rows = self.session.scalars(
            select(MarketBarORM)
            .join(InstrumentORM)
            .where(InstrumentORM.symbol == symbol)
            .order_by(MarketBarORM.timestamp)
        ).all()
        return [
            Bar(
                instrument_id=row.instrument_id,
                symbol=row.instrument.symbol,
                market=Market(row.instrument.market),
                timestamp=row.timestamp,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                source=row.source,
                adjusted=row.adjusted,
            )
            for row in rows
        ]
```

- [ ] **Step 6: Implement local legacy importer**

Create `src/quant_trading/storage/migrate_legacy.py`:

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3

from sqlalchemy import Engine

from quant_trading.core.enums import Market
from quant_trading.storage.db import session_scope
from quant_trading.storage.repositories import InstrumentRepository, MarketDataRepository


@dataclass(frozen=True)
class LegacyImportResult:
    imported_symbols: int
    imported_bars: int


def import_legacy_sqlite(db_path: Path, engine: Engine) -> LegacyImportResult:
    if not db_path.exists():
        raise FileNotFoundError(f"legacy sqlite database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    symbols = conn.execute(
        "select id, code, name, market from data_center_symbol order by id"
    ).fetchall()

    imported_symbols = 0
    imported_bars = 0
    with session_scope(engine) as session:
        instruments = InstrumentRepository(session)
        bars_repo = MarketDataRepository(session)
        for sym in symbols:
            market = Market(sym["market"])
            exchange = "SZSE" if str(sym["code"]).startswith(("0", "3")) else "SSE"
            instrument = instruments.upsert_symbol(
                symbol=sym["code"],
                name=sym["name"] or "",
                market=market,
                asset_type="stock",
                currency="CNY" if market is Market.A_STOCK else "USD",
                exchange=exchange,
            )
            imported_symbols += 1
            rows = conn.execute(
                """
                select date, open, high, low, close, volume
                from data_center_marketdata
                where symbol_id = ?
                order by date
                """,
                (sym["id"],),
            ).fetchall()
            for row in rows:
                bars_repo.upsert_daily_bar(
                    instrument_id=instrument.id,
                    timestamp=date.fromisoformat(row["date"]),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                    source="legacy_sqlite",
                    adjusted="qfq",
                )
                imported_bars += 1

    conn.close()
    return LegacyImportResult(imported_symbols=imported_symbols, imported_bars=imported_bars)
```

- [ ] **Step 7: Run storage and migration tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_storage_repositories.py tests/integration/test_legacy_migration.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 8: Commit storage layer**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add src/quant_trading/storage tests/integration/test_storage_repositories.py tests/integration/test_legacy_migration.py
git commit -m "feat: add storage and legacy market data import"
```

Expected commit summary includes:

```text
feat: add storage and legacy market data import
```

---

### Task 3: Data Validation And MA Cross Strategy

**Files:**
- Create: `src/quant_trading/data/validation.py`
- Create: `src/quant_trading/data/providers/base.py`
- Create: `src/quant_trading/data/providers/akshare_provider.py`
- Create: `src/quant_trading/strategy/base.py`
- Create: `src/quant_trading/strategy/registry.py`
- Create: `src/quant_trading/strategy/builtin/ma_cross.py`
- Create: `tests/unit/test_ma_cross_strategy.py`

- [ ] **Step 1: Write failing strategy tests**

Create `tests/unit/test_ma_cross_strategy.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

from quant_trading.core.enums import Market, OrderSide
from quant_trading.core.models import Bar, Portfolio
from quant_trading.strategy.builtin.ma_cross import MACrossStrategy
from quant_trading.strategy.registry import StrategyRegistry


def make_bar(day: int, close: str) -> Bar:
    price = Decimal(close)
    return Bar(
        instrument_id=1,
        symbol="000001",
        market=Market.A_STOCK,
        timestamp=date(2026, 1, 1) + timedelta(days=day),
        open=price,
        high=price + Decimal("0.5"),
        low=price - Decimal("0.5"),
        close=price,
        volume=Decimal("100000"),
    )


def test_ma_cross_generates_buy_on_bullish_cross():
    bars = [
        make_bar(0, "10"),
        make_bar(1, "10"),
        make_bar(2, "10"),
        make_bar(3, "11"),
        make_bar(4, "12"),
    ]
    strategy = MACrossStrategy(short_window=2, long_window=3, order_size=100)
    portfolio = Portfolio(account_id=1, cash=Decimal("100000"))

    intents = strategy.on_bar(bars=bars, portfolio=portfolio)

    assert len(intents) == 1
    assert intents[0].side is OrderSide.BUY
    assert intents[0].quantity == 100
    assert intents[0].reason == "ma_cross_bullish"


def test_strategy_registry_returns_approved_builtin_strategy():
    registry = StrategyRegistry()
    registry.register_builtin("ma_cross", MACrossStrategy)

    strategy = registry.create("ma_cross", {"short_window": 2, "long_window": 3})

    assert isinstance(strategy, MACrossStrategy)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit/test_ma_cross_strategy.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading.strategy'
```

- [ ] **Step 3: Implement data validation and provider protocols**

Create `src/quant_trading/data/validation.py`:

```python
from quant_trading.core.models import Bar


def validate_bars(bars: list[Bar]) -> list[Bar]:
    seen: set[tuple[int, object]] = set()
    for bar in bars:
        key = (bar.instrument_id, bar.timestamp)
        if key in seen:
            raise ValueError(f"duplicate bar for instrument_id={bar.instrument_id} timestamp={bar.timestamp}")
        seen.add(key)
    return sorted(bars, key=lambda b: b.timestamp)
```

Create `src/quant_trading/data/providers/base.py`:

```python
from typing import Protocol

from quant_trading.core.models import Bar


class MarketDataProvider(Protocol):
    name: str

    def fetch_daily_bars(self, symbol: str, start: str | None, end: str | None) -> list[Bar]:
        raise NotImplementedError
```

Create `src/quant_trading/data/providers/akshare_provider.py`:

```python
from decimal import Decimal

from quant_trading.core.enums import Market
from quant_trading.core.models import Bar
from quant_trading.data.validation import validate_bars


class AkshareProvider:
    name = "akshare"

    def fetch_daily_bars(self, symbol: str, start: str | None, end: str | None) -> list[Bar]:
        import akshare as ak

        exchange_symbol = self._exchange_symbol(symbol)
        df = ak.stock_zh_a_hist_tx(
            symbol=exchange_symbol,
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
        bars = [
            Bar(
                instrument_id=0,
                symbol=symbol,
                market=Market.A_STOCK,
                timestamp=row["date"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row.get("volume", row.get("amount", 0)))),
                source=self.name,
            )
            for _, row in df.iterrows()
        ]
        return validate_bars(bars)

    def _exchange_symbol(self, symbol: str) -> str:
        code = symbol.zfill(6)
        if code.startswith(("600", "601", "603", "605", "688")):
            return f"sh{code}"
        return f"sz{code}"
```

- [ ] **Step 4: Implement strategy protocol and registry**

Create `src/quant_trading/strategy/base.py`:

```python
from typing import Protocol

from quant_trading.core.models import Bar, OrderIntent, Portfolio


class Strategy(Protocol):
    name: str

    def on_bar(self, bars: list[Bar], portfolio: Portfolio) -> list[OrderIntent]:
        raise NotImplementedError
```

Create `src/quant_trading/strategy/registry.py`:

```python
from quant_trading.strategy.base import Strategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._builtins: dict[str, type[Strategy]] = {}

    def register_builtin(self, name: str, strategy_cls: type[Strategy]) -> None:
        self._builtins[name] = strategy_cls

    def create(self, name: str, params: dict | None = None) -> Strategy:
        if name not in self._builtins:
            raise KeyError(f"unknown strategy: {name}")
        return self._builtins[name](**(params or {}))
```

- [ ] **Step 5: Implement MA cross strategy**

Create `src/quant_trading/strategy/builtin/ma_cross.py`:

```python
from decimal import Decimal

from quant_trading.core.enums import OrderSide
from quant_trading.core.models import Bar, OrderIntent, Portfolio


class MACrossStrategy:
    name = "ma_cross"

    def __init__(self, short_window: int = 5, long_window: int = 20, order_size: int = 100):
        if short_window <= 0 or long_window <= 0:
            raise ValueError("windows must be positive")
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        if order_size <= 0:
            raise ValueError("order_size must be positive")
        self.short_window = short_window
        self.long_window = long_window
        self.order_size = order_size

    def on_bar(self, bars: list[Bar], portfolio: Portfolio) -> list[OrderIntent]:
        if len(bars) < self.long_window + 1:
            return []

        closes = [bar.close for bar in bars]
        previous_short = self._mean(closes[-self.short_window - 1 : -1])
        previous_long = self._mean(closes[-self.long_window - 1 : -1])
        current_short = self._mean(closes[-self.short_window :])
        current_long = self._mean(closes[-self.long_window :])
        latest = bars[-1]
        has_position = latest.instrument_id in portfolio.positions and portfolio.positions[latest.instrument_id].quantity > 0

        if previous_short <= previous_long and current_short > current_long and not has_position:
            return [
                OrderIntent(
                    instrument_id=latest.instrument_id,
                    symbol=latest.symbol,
                    side=OrderSide.BUY,
                    quantity=self.order_size,
                    reason="ma_cross_bullish",
                )
            ]
        if previous_short >= previous_long and current_short < current_long and has_position:
            quantity = portfolio.positions[latest.instrument_id].quantity
            return [
                OrderIntent(
                    instrument_id=latest.instrument_id,
                    symbol=latest.symbol,
                    side=OrderSide.SELL,
                    quantity=quantity,
                    reason="ma_cross_bearish",
                )
            ]
        return []

    def _mean(self, values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values))
```

- [ ] **Step 6: Run strategy tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit/test_ma_cross_strategy.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Commit data and strategy layer**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add src/quant_trading/data src/quant_trading/strategy tests/unit/test_ma_cross_strategy.py
git commit -m "feat: add validated data providers and strategy registry"
```

Expected commit summary includes:

```text
feat: add validated data providers and strategy registry
```

---

### Task 4: Accounting, Simulated Execution, And Risk Gate

**Files:**
- Create: `src/quant_trading/execution/commission.py`
- Create: `src/quant_trading/execution/slippage.py`
- Create: `src/quant_trading/execution/simulator.py`
- Create: `src/quant_trading/portfolio/accounting.py`
- Create: `src/quant_trading/risk/rules.py`
- Create: `src/quant_trading/risk/engine.py`
- Create: `tests/unit/test_accounting.py`
- Create: `tests/unit/test_risk_engine.py`

- [ ] **Step 1: Write failing accounting and risk tests**

Create `tests/unit/test_accounting.py`:

```python
from datetime import date
from decimal import Decimal

from quant_trading.core.enums import Market, OrderSide
from quant_trading.core.models import Bar, OrderIntent, Portfolio
from quant_trading.execution.simulator import SimulatedBroker
from quant_trading.portfolio.accounting import apply_fill


def test_buy_fill_reduces_cash_and_creates_position():
    bar = Bar(
        instrument_id=1,
        symbol="000001",
        market=Market.A_STOCK,
        timestamp=date(2026, 5, 8),
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=Decimal("10"),
        volume=Decimal("100000"),
    )
    portfolio = Portfolio(account_id=1, cash=Decimal("100000"))
    broker = SimulatedBroker(commission_rate=Decimal("0.0003"), slippage_rate=Decimal("0.001"))
    intent = OrderIntent(
        instrument_id=1,
        symbol="000001",
        side=OrderSide.BUY,
        quantity=100,
        reason="test",
    )

    fill = broker.execute_market_order(intent, bar)
    updated = apply_fill(portfolio, fill)

    assert fill.price == Decimal("10.010")
    assert fill.commission == Decimal("0.300300")
    assert updated.positions[1].quantity == 100
    assert updated.cash == Decimal("98998.699700")
```

Create `tests/unit/test_risk_engine.py`:

```python
from datetime import date
from decimal import Decimal

from quant_trading.core.enums import Market, OrderSide, RiskDecisionType, StrategyStatus
from quant_trading.core.models import Bar, OrderIntent, Portfolio, Position
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import (
    MaxGrossExposureRule,
    MaxOrderValueRule,
    NoTradeWithoutDataRule,
    PriceSanityRule,
    StrategyStatusRule,
)


def make_bar(close: str = "10") -> Bar:
    price = Decimal(close)
    return Bar(
        instrument_id=1,
        symbol="000001",
        market=Market.A_STOCK,
        timestamp=date(2026, 5, 8),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("100000"),
    )


def test_risk_rejects_unapproved_strategy():
    engine = RiskEngine([StrategyStatusRule()])
    intent = OrderIntent(1, "000001", OrderSide.BUY, 100, "test")
    decision = engine.check_order(
        intent=intent,
        latest_bar=make_bar(),
        portfolio=Portfolio(account_id=1, cash=Decimal("100000")),
        strategy_status=StrategyStatus.DRAFT,
    )

    assert decision.decision is RiskDecisionType.REJECTED
    assert decision.rule_name == "StrategyStatusRule"


def test_risk_approves_valid_order():
    engine = RiskEngine([
        StrategyStatusRule(),
        NoTradeWithoutDataRule(),
        PriceSanityRule(),
        MaxOrderValueRule(max_order_value=Decimal("5000")),
        MaxGrossExposureRule(max_gross_exposure=Decimal("0.95")),
    ])
    intent = OrderIntent(1, "000001", OrderSide.BUY, 100, "test")
    decision = engine.check_order(
        intent=intent,
        latest_bar=make_bar(),
        portfolio=Portfolio(account_id=1, cash=Decimal("100000")),
        strategy_status=StrategyStatus.APPROVED,
    )

    assert decision.decision is RiskDecisionType.APPROVED
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit/test_accounting.py tests/unit/test_risk_engine.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading.execution'
```

- [ ] **Step 3: Implement commission, slippage, and simulated broker**

Create `src/quant_trading/execution/commission.py`:

```python
from decimal import Decimal


def percent_commission(notional: Decimal, rate: Decimal) -> Decimal:
    return notional * rate
```

Create `src/quant_trading/execution/slippage.py`:

```python
from decimal import Decimal

from quant_trading.core.enums import OrderSide


def apply_percent_slippage(price: Decimal, side: OrderSide, rate: Decimal) -> Decimal:
    if side is OrderSide.BUY:
        return price * (Decimal("1") + rate)
    return price * (Decimal("1") - rate)
```

Create `src/quant_trading/execution/simulator.py`:

```python
from decimal import Decimal

from quant_trading.core.enums import OrderSide
from quant_trading.core.models import Bar, Fill, OrderIntent
from quant_trading.execution.commission import percent_commission
from quant_trading.execution.slippage import apply_percent_slippage


class SimulatedBroker:
    def __init__(self, commission_rate: Decimal, slippage_rate: Decimal):
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

    def execute_market_order(self, intent: OrderIntent, bar: Bar) -> Fill:
        price = apply_percent_slippage(bar.close, intent.side, self.slippage_rate)
        notional = price * Decimal(intent.quantity)
        commission = percent_commission(notional, self.commission_rate)
        slippage = abs(price - bar.close) * Decimal(intent.quantity)
        return Fill(
            order_id=None,
            instrument_id=intent.instrument_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            price=price,
            commission=commission,
            slippage=slippage,
            filled_at=bar.timestamp,
        )
```

- [ ] **Step 4: Implement portfolio accounting**

Create `src/quant_trading/portfolio/accounting.py`:

```python
from copy import deepcopy
from decimal import Decimal

from quant_trading.core.enums import OrderSide
from quant_trading.core.models import Fill, Portfolio, Position


def apply_fill(portfolio: Portfolio, fill: Fill) -> Portfolio:
    updated = deepcopy(portfolio)
    notional = fill.price * Decimal(fill.quantity)

    if fill.side is OrderSide.BUY:
        updated.cash -= notional + fill.commission
        existing = updated.positions.get(fill.instrument_id)
        if existing:
            total_quantity = existing.quantity + fill.quantity
            total_cost = existing.avg_cost * Decimal(existing.quantity) + notional
            existing.quantity = total_quantity
            existing.avg_cost = total_cost / Decimal(total_quantity)
            existing.market_price = fill.price
        else:
            updated.positions[fill.instrument_id] = Position(
                instrument_id=fill.instrument_id,
                symbol=fill.symbol,
                quantity=fill.quantity,
                avg_cost=fill.price,
                market_price=fill.price,
            )
    else:
        existing = updated.positions.get(fill.instrument_id)
        if not existing or existing.quantity < fill.quantity:
            raise ValueError("cannot sell more shares than the portfolio holds")
        realized = (fill.price - existing.avg_cost) * Decimal(fill.quantity) - fill.commission
        updated.cash += notional - fill.commission
        updated.realized_pnl += realized
        existing.quantity -= fill.quantity
        existing.market_price = fill.price
        if existing.quantity == 0:
            del updated.positions[fill.instrument_id]

    updated.peak_equity = max(updated.peak_equity or updated.equity, updated.equity)
    return updated
```

Create `src/quant_trading/portfolio/metrics.py`:

```python
from decimal import Decimal


def total_return(initial_equity: Decimal, final_equity: Decimal) -> Decimal:
    if initial_equity == 0:
        return Decimal("0")
    return (final_equity / initial_equity) - Decimal("1")
```

- [ ] **Step 5: Implement risk rules and engine**

Create `src/quant_trading/risk/rules.py`:

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from quant_trading.core.enums import RiskDecisionType, StrategyStatus
from quant_trading.core.models import Bar, OrderIntent, Portfolio, RiskDecision


class RiskRule(Protocol):
    def evaluate(
        self,
        intent: OrderIntent,
        latest_bar: Bar | None,
        portfolio: Portfolio,
        strategy_status: StrategyStatus,
    ) -> RiskDecision:
        raise NotImplementedError


class StrategyStatusRule:
    def evaluate(self, intent: OrderIntent, latest_bar: Bar | None, portfolio: Portfolio, strategy_status: StrategyStatus) -> RiskDecision:
        if strategy_status is not StrategyStatus.APPROVED:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "strategy is not approved", intent)
        return RiskDecision(RiskDecisionType.APPROVED, self.__class__.__name__, "strategy approved", intent)


class NoTradeWithoutDataRule:
    def evaluate(self, intent: OrderIntent, latest_bar: Bar | None, portfolio: Portfolio, strategy_status: StrategyStatus) -> RiskDecision:
        if latest_bar is None:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "latest market bar is missing", intent)
        return RiskDecision(RiskDecisionType.APPROVED, self.__class__.__name__, "market data present", intent)


class PriceSanityRule:
    def evaluate(self, intent: OrderIntent, latest_bar: Bar | None, portfolio: Portfolio, strategy_status: StrategyStatus) -> RiskDecision:
        if latest_bar is None or latest_bar.close <= 0:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "latest close price is invalid", intent)
        return RiskDecision(RiskDecisionType.APPROVED, self.__class__.__name__, "price is valid", intent)


@dataclass(frozen=True)
class MaxOrderValueRule:
    max_order_value: Decimal

    def evaluate(self, intent: OrderIntent, latest_bar: Bar | None, portfolio: Portfolio, strategy_status: StrategyStatus) -> RiskDecision:
        if latest_bar is None:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "latest market bar is missing", intent)
        order_value = latest_bar.close * Decimal(intent.quantity)
        if order_value > self.max_order_value:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "order value exceeds limit", intent)
        return RiskDecision(RiskDecisionType.APPROVED, self.__class__.__name__, "order value within limit", intent)


@dataclass(frozen=True)
class MaxGrossExposureRule:
    max_gross_exposure: Decimal

    def evaluate(self, intent: OrderIntent, latest_bar: Bar | None, portfolio: Portfolio, strategy_status: StrategyStatus) -> RiskDecision:
        if latest_bar is None:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "latest market bar is missing", intent)
        proposed_value = latest_bar.close * Decimal(intent.quantity)
        proposed_exposure = (portfolio.market_value + proposed_value) / portfolio.equity
        if proposed_exposure > self.max_gross_exposure:
            return RiskDecision(RiskDecisionType.REJECTED, self.__class__.__name__, "gross exposure exceeds limit", intent)
        return RiskDecision(RiskDecisionType.APPROVED, self.__class__.__name__, "gross exposure within limit", intent)
```

Create `src/quant_trading/risk/engine.py`:

```python
from quant_trading.core.enums import RiskDecisionType, StrategyStatus
from quant_trading.core.models import Bar, OrderIntent, Portfolio, RiskDecision
from quant_trading.risk.rules import RiskRule


class RiskEngine:
    def __init__(self, rules: list[RiskRule]):
        self.rules = rules

    def check_order(
        self,
        intent: OrderIntent,
        latest_bar: Bar | None,
        portfolio: Portfolio,
        strategy_status: StrategyStatus,
    ) -> RiskDecision:
        for rule in self.rules:
            decision = rule.evaluate(intent, latest_bar, portfolio, strategy_status)
            if decision.decision is not RiskDecisionType.APPROVED:
                return decision
        return RiskDecision(RiskDecisionType.APPROVED, "RiskEngine", "all risk rules approved", intent)
```

- [ ] **Step 6: Run accounting and risk tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit/test_accounting.py tests/unit/test_risk_engine.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit execution, accounting, and risk**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add src/quant_trading/execution src/quant_trading/portfolio src/quant_trading/risk tests/unit/test_accounting.py tests/unit/test_risk_engine.py
git commit -m "feat: add simulated execution and risk gate"
```

Expected commit summary includes:

```text
feat: add simulated execution and risk gate
```

---

### Task 5: Event Backtest Engine With Normalized Results

**Files:**
- Modify: `src/quant_trading/storage/models.py`
- Modify: `src/quant_trading/storage/repositories.py`
- Create: `src/quant_trading/backtest/engine.py`
- Create: `tests/integration/test_backtest_engine.py`

- [ ] **Step 1: Write failing backtest integration test**

Create `tests/integration/test_backtest_engine.py`:

```python
from decimal import Decimal
from pathlib import Path

from quant_trading.backtest.engine import BacktestEngine
from quant_trading.storage.db import create_all, make_engine
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.strategy.builtin.ma_cross import MACrossStrategy


def test_backtest_persists_equity_orders_and_fills():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(Path("django_app/db.sqlite3"), engine)

    backtest = BacktestEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        commission_rate=Decimal("0.0003"),
        slippage_rate=Decimal("0.001"),
    )
    result = backtest.run(
        symbol="000001",
        strategy=MACrossStrategy(short_window=5, long_window=20, order_size=100),
        strategy_name="ma_cross",
    )

    assert result.run_id > 0
    assert result.final_equity > Decimal("0")
    assert result.equity_points >= 100
    assert result.order_count >= 0
    assert result.fill_count >= 0
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_backtest_engine.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading.backtest'
```

- [ ] **Step 3: Extend storage models for backtests**

Add these classes to the end of `src/quant_trading/storage/models.py`:

```python
class BacktestRunORM(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    initial_cash: Mapped[float] = mapped_column(Numeric(18, 6))
    final_equity: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BacktestEquityPointORM(Base):
    __tablename__ = "backtest_equity_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(Date, index=True)
    equity: Mapped[float] = mapped_column(Numeric(18, 6))
    cash: Mapped[float] = mapped_column(Numeric(18, 6))
    market_value: Mapped[float] = mapped_column(Numeric(18, 6))
    drawdown: Mapped[float] = mapped_column(Numeric(18, 6))


class BacktestOrderORM(Base):
    __tablename__ = "backtest_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="filled")
    submitted_at: Mapped[datetime] = mapped_column(Date)


class BacktestFillORM(Base):
    __tablename__ = "backtest_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(18, 6))
    commission: Mapped[float] = mapped_column(Numeric(18, 6))
    slippage: Mapped[float] = mapped_column(Numeric(18, 6))
    filled_at: Mapped[datetime] = mapped_column(Date)
```

- [ ] **Step 4: Implement backtest engine**

Create `src/quant_trading/backtest/engine.py`:

```python
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Engine

from quant_trading.core.enums import StrategyStatus
from quant_trading.core.models import Portfolio
from quant_trading.execution.simulator import SimulatedBroker
from quant_trading.portfolio.accounting import apply_fill
from quant_trading.storage.db import session_scope
from quant_trading.storage.models import (
    BacktestEquityPointORM,
    BacktestFillORM,
    BacktestOrderORM,
    BacktestRunORM,
)
from quant_trading.storage.repositories import MarketDataRepository
from quant_trading.strategy.base import Strategy


@dataclass(frozen=True)
class BacktestSummary:
    run_id: int
    final_equity: Decimal
    equity_points: int
    order_count: int
    fill_count: int


class BacktestEngine:
    def __init__(
        self,
        engine: Engine,
        initial_cash: Decimal,
        commission_rate: Decimal,
        slippage_rate: Decimal,
    ):
        self.engine = engine
        self.initial_cash = initial_cash
        self.broker = SimulatedBroker(commission_rate=commission_rate, slippage_rate=slippage_rate)

    def run(self, symbol: str, strategy: Strategy, strategy_name: str) -> BacktestSummary:
        with session_scope(self.engine) as session:
            bars = MarketDataRepository(session).list_bars(symbol)
            run = BacktestRunORM(
                strategy_name=strategy_name,
                symbol=symbol,
                initial_cash=self.initial_cash,
                status="running",
            )
            session.add(run)
            session.flush()

            portfolio = Portfolio(account_id=run.id, cash=self.initial_cash)
            order_count = 0
            fill_count = 0

            for index in range(len(bars)):
                history = bars[: index + 1]
                latest = history[-1]
                intents = strategy.on_bar(history, portfolio)
                for intent in intents:
                    fill = self.broker.execute_market_order(intent, latest)
                    portfolio = apply_fill(portfolio, fill)
                    order_count += 1
                    fill_count += 1
                    session.add(
                        BacktestOrderORM(
                            run_id=run.id,
                            instrument_id=intent.instrument_id,
                            symbol=intent.symbol,
                            side=intent.side.value,
                            quantity=intent.quantity,
                            reason=intent.reason,
                            status="filled",
                            submitted_at=latest.timestamp,
                        )
                    )
                    session.add(
                        BacktestFillORM(
                            run_id=run.id,
                            instrument_id=fill.instrument_id,
                            symbol=fill.symbol,
                            side=fill.side.value,
                            quantity=fill.quantity,
                            price=fill.price,
                            commission=fill.commission,
                            slippage=fill.slippage,
                            filled_at=fill.filled_at,
                        )
                    )

                for position in portfolio.positions.values():
                    if position.instrument_id == latest.instrument_id:
                        position.market_price = latest.close
                session.add(
                    BacktestEquityPointORM(
                        run_id=run.id,
                        timestamp=latest.timestamp,
                        equity=portfolio.equity,
                        cash=portfolio.cash,
                        market_value=portfolio.market_value,
                        drawdown=portfolio.drawdown,
                    )
                )

            run.final_equity = portfolio.equity
            run.status = "done"
            return BacktestSummary(
                run_id=run.id,
                final_equity=portfolio.equity,
                equity_points=len(bars),
                order_count=order_count,
                fill_count=fill_count,
            )
```

- [ ] **Step 5: Run backtest integration test**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_backtest_engine.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run all current tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit tests/integration -q
```

Expected:

```text
11 passed
```

- [ ] **Step 7: Commit backtest engine**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add src/quant_trading/backtest src/quant_trading/storage tests/integration/test_backtest_engine.py
git commit -m "feat: add normalized event backtest engine"
```

Expected commit summary includes:

```text
feat: add normalized event backtest engine
```

---

### Task 6: Paper Trading One-Tick Engine

**Files:**
- Modify: `src/quant_trading/storage/models.py`
- Create: `src/quant_trading/paper/engine.py`
- Create: `tests/integration/test_paper_engine.py`

- [ ] **Step 1: Write failing paper engine test**

Create `tests/integration/test_paper_engine.py`:

```python
from decimal import Decimal
from pathlib import Path

from quant_trading.core.enums import StrategyStatus
from quant_trading.paper.engine import PaperTradingEngine
from quant_trading.risk.engine import RiskEngine
from quant_trading.risk.rules import MaxOrderValueRule, NoTradeWithoutDataRule, PriceSanityRule, StrategyStatusRule
from quant_trading.storage.db import create_all, make_engine
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.strategy.builtin.ma_cross import MACrossStrategy


def test_paper_tick_persists_snapshot_and_risk_decision():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    import_legacy_sqlite(Path("django_app/db.sqlite3"), engine)

    paper = PaperTradingEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        risk_engine=RiskEngine([
            StrategyStatusRule(),
            NoTradeWithoutDataRule(),
            PriceSanityRule(),
            MaxOrderValueRule(max_order_value=Decimal("100000")),
        ]),
    )
    result = paper.run_one_tick(
        symbol="000001",
        strategy=MACrossStrategy(short_window=5, long_window=20, order_size=100),
        strategy_status=StrategyStatus.APPROVED,
    )

    assert result.account_id > 0
    assert result.snapshot_count == 1
    assert result.risk_decision_count >= 0
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_paper_engine.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading.paper'
```

- [ ] **Step 3: Extend storage models for paper trading**

Add these classes to `src/quant_trading/storage/models.py`:

```python
class PaperAccountORM(Base):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="Default Paper Account")
    base_currency: Mapped[str] = mapped_column(String(16), default="CNY")
    initial_cash: Mapped[float] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PortfolioSnapshotORM(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(Date)
    equity: Mapped[float] = mapped_column(Numeric(18, 6))
    cash: Mapped[float] = mapped_column(Numeric(18, 6))
    market_value: Mapped[float] = mapped_column(Numeric(18, 6))
    realized_pnl: Mapped[float] = mapped_column(Numeric(18, 6))
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(18, 6))
    drawdown: Mapped[float] = mapped_column(Numeric(18, 6))


class RiskDecisionORM(Base):
    __tablename__ = "risk_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str] = mapped_column(String(32))
    rule_name: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Implement paper trading engine**

Create `src/quant_trading/paper/engine.py`:

```python
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Engine

from quant_trading.core.enums import RiskDecisionType, StrategyStatus
from quant_trading.core.models import Portfolio
from quant_trading.execution.simulator import SimulatedBroker
from quant_trading.portfolio.accounting import apply_fill
from quant_trading.risk.engine import RiskEngine
from quant_trading.storage.db import session_scope
from quant_trading.storage.models import PaperAccountORM, PortfolioSnapshotORM, RiskDecisionORM
from quant_trading.storage.repositories import MarketDataRepository
from quant_trading.strategy.base import Strategy


@dataclass(frozen=True)
class PaperTickSummary:
    account_id: int
    snapshot_count: int
    risk_decision_count: int


class PaperTradingEngine:
    def __init__(
        self,
        engine: Engine,
        initial_cash: Decimal,
        risk_engine: RiskEngine,
        commission_rate: Decimal = Decimal("0.0003"),
        slippage_rate: Decimal = Decimal("0.001"),
    ):
        self.engine = engine
        self.initial_cash = initial_cash
        self.risk_engine = risk_engine
        self.broker = SimulatedBroker(commission_rate=commission_rate, slippage_rate=slippage_rate)

    def run_one_tick(self, symbol: str, strategy: Strategy, strategy_status: StrategyStatus) -> PaperTickSummary:
        with session_scope(self.engine) as session:
            account = PaperAccountORM(initial_cash=self.initial_cash)
            session.add(account)
            session.flush()

            bars = MarketDataRepository(session).list_bars(symbol)
            if not bars:
                raise ValueError(f"no market bars found for symbol: {symbol}")

            latest = bars[-1]
            portfolio = Portfolio(account_id=account.id, cash=self.initial_cash)
            risk_decision_count = 0
            for intent in strategy.on_bar(bars, portfolio):
                decision = self.risk_engine.check_order(intent, latest, portfolio, strategy_status)
                session.add(
                    RiskDecisionORM(
                        run_id=account.id,
                        decision=decision.decision.value,
                        rule_name=decision.rule_name,
                        message=decision.message,
                    )
                )
                risk_decision_count += 1
                if decision.decision is RiskDecisionType.APPROVED:
                    fill = self.broker.execute_market_order(intent, latest)
                    portfolio = apply_fill(portfolio, fill)

            session.add(
                PortfolioSnapshotORM(
                    account_id=account.id,
                    timestamp=latest.timestamp,
                    equity=portfolio.equity,
                    cash=portfolio.cash,
                    market_value=portfolio.market_value,
                    realized_pnl=portfolio.realized_pnl,
                    unrealized_pnl=sum((p.unrealized_pnl for p in portfolio.positions.values()), Decimal("0")),
                    drawdown=portfolio.drawdown,
                )
            )
            return PaperTickSummary(
                account_id=account.id,
                snapshot_count=1,
                risk_decision_count=risk_decision_count,
            )
```

- [ ] **Step 5: Run paper engine test**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_paper_engine.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run all current tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit tests/integration -q
```

Expected:

```text
12 passed
```

- [ ] **Step 7: Commit paper engine**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add src/quant_trading/paper src/quant_trading/storage tests/integration/test_paper_engine.py
git commit -m "feat: add risk-gated paper trading tick"
```

Expected commit summary includes:

```text
feat: add risk-gated paper trading tick
```

---

### Task 7: FastAPI Read APIs And Job Entrypoints

**Files:**
- Create: `src/quant_trading/api/main.py`
- Create: `src/quant_trading/api/routes/health.py`
- Create: `src/quant_trading/api/routes/instruments.py`
- Create: `src/quant_trading/api/routes/backtests.py`
- Create: `src/quant_trading/api/routes/paper.py`
- Create: `src/quant_trading/jobs/queue.py`
- Create: `src/quant_trading/jobs/tasks.py`
- Create: `tests/integration/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/integration/test_api.py`:

```python
from fastapi.testclient import TestClient

from quant_trading.api.main import create_app
from quant_trading.storage.db import create_all, make_engine


def test_health_endpoint_returns_ok():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    app = create_app(engine)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_instruments_endpoint_starts_empty():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    app = create_app(engine)
    client = TestClient(app)

    response = client.get("/instruments")

    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_api.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'quant_trading.api'
```

- [ ] **Step 3: Implement FastAPI app and routes**

Create `src/quant_trading/api/main.py`:

```python
import os

from fastapi import FastAPI
from sqlalchemy import Engine

from quant_trading.api.routes import backtests, health, instruments, paper
from quant_trading.storage.db import create_all, make_engine


def create_app(engine: Engine | None = None) -> FastAPI:
    if engine is None:
        database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///quant_trading.db")
        engine = make_engine(database_url)
        create_all(engine)
    app = FastAPI(title="Quant Trading Platform")
    app.state.engine = engine
    app.include_router(health.router)
    app.include_router(instruments.router)
    app.include_router(backtests.router)
    app.include_router(paper.router)
    return app
```

Create `src/quant_trading/api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

Create `src/quant_trading/api/routes/instruments.py`:

```python
from fastapi import APIRouter, Request
from sqlalchemy import select

from quant_trading.storage.db import session_scope
from quant_trading.storage.models import InstrumentORM

router = APIRouter()


@router.get("/instruments")
def list_instruments(request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(select(InstrumentORM).order_by(InstrumentORM.symbol)).all()
        return [
            {
                "id": row.id,
                "symbol": row.symbol,
                "name": row.name,
                "market": row.market,
                "asset_type": row.asset_type,
                "currency": row.currency,
                "exchange": row.exchange,
                "status": row.status,
            }
            for row in rows
        ]
```

Create `src/quant_trading/api/routes/backtests.py`:

```python
from fastapi import APIRouter, Request
from sqlalchemy import select

from quant_trading.storage.db import session_scope
from quant_trading.storage.models import BacktestRunORM

router = APIRouter()


@router.get("/backtests")
def list_backtests(request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(select(BacktestRunORM).order_by(BacktestRunORM.id.desc())).all()
        return [
            {
                "id": row.id,
                "symbol": row.symbol,
                "strategy_name": row.strategy_name,
                "initial_cash": float(row.initial_cash),
                "final_equity": float(row.final_equity),
                "status": row.status,
            }
            for row in rows
        ]
```

Create `src/quant_trading/api/routes/paper.py`:

```python
from fastapi import APIRouter, Request
from sqlalchemy import select

from quant_trading.storage.db import session_scope
from quant_trading.storage.models import PortfolioSnapshotORM

router = APIRouter()


@router.get("/paper/snapshots")
def list_paper_snapshots(request: Request) -> list[dict]:
    with session_scope(request.app.state.engine) as session:
        rows = session.scalars(select(PortfolioSnapshotORM).order_by(PortfolioSnapshotORM.id.desc())).all()
        return [
            {
                "account_id": row.account_id,
                "timestamp": str(row.timestamp),
                "equity": float(row.equity),
                "cash": float(row.cash),
                "market_value": float(row.market_value),
                "drawdown": float(row.drawdown),
            }
            for row in rows
        ]
```

- [ ] **Step 4: Implement RQ queue and task wrappers**

Create `src/quant_trading/jobs/queue.py`:

```python
from redis import Redis
from rq import Queue


def make_queue(redis_url: str = "redis://localhost:6379/0") -> Queue:
    return Queue("quant-trading", connection=Redis.from_url(redis_url))
```

Create `src/quant_trading/jobs/tasks.py`:

```python
from decimal import Decimal
from pathlib import Path

from quant_trading.backtest.engine import BacktestEngine
from quant_trading.storage.db import create_all, make_engine
from quant_trading.storage.migrate_legacy import import_legacy_sqlite
from quant_trading.strategy.builtin.ma_cross import MACrossStrategy


def import_legacy_data_task(legacy_db_path: str, database_url: str) -> dict:
    engine = make_engine(database_url)
    create_all(engine)
    result = import_legacy_sqlite(Path(legacy_db_path), engine)
    return {"imported_symbols": result.imported_symbols, "imported_bars": result.imported_bars}


def run_ma_cross_backtest_task(database_url: str, symbol: str = "000001") -> dict:
    engine = make_engine(database_url)
    backtest = BacktestEngine(
        engine=engine,
        initial_cash=Decimal("100000"),
        commission_rate=Decimal("0.0003"),
        slippage_rate=Decimal("0.001"),
    )
    result = backtest.run(
        symbol=symbol,
        strategy=MACrossStrategy(short_window=5, long_window=20, order_size=100),
        strategy_name="ma_cross",
    )
    return {
        "run_id": result.run_id,
        "final_equity": str(result.final_equity),
        "equity_points": result.equity_points,
    }
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/integration/test_api.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run all current tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit tests/integration -q
```

Expected:

```text
14 passed
```

- [ ] **Step 7: Commit API and jobs**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add src/quant_trading/api src/quant_trading/jobs tests/integration/test_api.py
git commit -m "feat: add FastAPI status APIs and job tasks"
```

Expected commit summary includes:

```text
feat: add FastAPI status APIs and job tasks
```

---

### Task 8: Docker Compose, Runtime Entrypoint, And Documentation

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Add runtime Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "quant_trading.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Add Docker Compose**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: quant_trading
      POSTGRES_USER: quant
      POSTGRES_PASSWORD: quant
    ports:
      - "5432:5432"
    volumes:
      - quant_postgres:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  api:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg://quant:quant@postgres:5432/quant_trading
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  worker:
    build: .
    command: rq worker quant-trading --url redis://redis:6379/0
    environment:
      DATABASE_URL: postgresql+psycopg://quant:quant@postgres:5432/quant_trading
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis

volumes:
  quant_postgres:
```

- [ ] **Step 3: Add environment example**

Create `.env.example`:

```bash
DATABASE_URL=postgresql+psycopg://quant:quant@localhost:5432/quant_trading
REDIS_URL=redis://localhost:6379/0
QT_INITIAL_CASH=100000
QT_COMMISSION_RATE=0.0003
QT_SLIPPAGE_RATE=0.001
```

- [ ] **Step 4: Replace README with productized platform guide**

Replace `README.md` with:

```markdown
# Quant Trading Platform

Research and paper-trading platform for productized quantitative workflows.

## Current Milestone

This version supports:

- Importing legacy A-share daily data from `django_app/db.sqlite3`.
- Storing instruments and market bars in normalized SQLAlchemy models.
- Running a portfolio-style MA cross backtest.
- Running a risk-gated paper trading tick with simulated fills.
- Reading health, instruments, backtests, and paper snapshots through FastAPI.

This version does not place real broker or exchange orders.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit tests/integration -q
```

## Local Services

```bash
docker compose up --build
```

API:

```text
http://localhost:8000/health
http://localhost:8000/instruments
http://localhost:8000/backtests
http://localhost:8000/paper/snapshots
```

## Legacy Data

The first migration source is:

```text
django_app/db.sqlite3
```

The importer maps `data_center_symbol` to `instruments` and `data_center_marketdata` to `market_bars`.

## Safety

AI-generated and custom strategies are research artifacts only. Paper trading requires approved, registered strategies. Real broker adapters are outside this milestone.
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit tests/integration -q
```

Expected:

```text
14 passed
```

- [ ] **Step 6: Validate Docker Compose config**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
docker compose config
```

Expected:

```text
services:
```

If Docker is unavailable, record the exact error in the implementation handoff and do not claim Docker verification passed.

- [ ] **Step 7: Commit runtime docs**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add Dockerfile docker-compose.yml .env.example README.md
git commit -m "docs: add productized runtime guide"
```

Expected commit summary includes:

```text
docs: add productized runtime guide
```

---

### Task 9: Legacy Relocation And Final Verification

**Files:**
- Move: `django_app/` to `legacy/django_app/`
- Move: `scripts/` to `legacy/scripts/`
- Move: `commands/` to `legacy/commands/`
- Move: `skills/` to `legacy/skills/`
- Modify: `README.md`

- [ ] **Step 1: Move legacy directories with Git**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
mkdir -p legacy
git mv django_app legacy/django_app
git mv scripts legacy/scripts
git mv commands legacy/commands
git mv skills legacy/skills
```

Expected:

```text
```

The command should be silent on success.

- [ ] **Step 2: Update README legacy section**

Append this section to `README.md`:

```markdown

## Legacy Reference

The original Claude plugin, scripts, slash commands, skills, and Django demo app live under `legacy/`.

They are kept for migration reference only. New product code lives under `src/quant_trading/`.
```

- [ ] **Step 3: Update legacy fixture paths in integration tests**

Change each legacy database path from:

```python
Path("django_app/db.sqlite3")
```

to:

```python
Path("legacy/django_app/db.sqlite3")
```

in these files:

```text
tests/integration/test_legacy_migration.py
tests/integration/test_backtest_engine.py
tests/integration/test_paper_engine.py
```

- [ ] **Step 4: Run full verification**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
python -m pytest tests/unit tests/integration -q
```

Expected:

```text
14 passed
```

- [ ] **Step 5: Check working tree**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git status --short
```

Expected includes only planned changes from this task:

```text
R  django_app/ -> legacy/django_app/
R  scripts/ -> legacy/scripts/
R  commands/ -> legacy/commands/
R  skills/ -> legacy/skills/
M  README.md
M  tests/integration/test_legacy_migration.py
M  tests/integration/test_backtest_engine.py
M  tests/integration/test_paper_engine.py
```

If `django_app/quant_web/settings.py` appears as a modification inside the move, preserve it. That dirty change existed before productization work.

- [ ] **Step 6: Commit legacy relocation**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git add README.md legacy tests/integration/test_legacy_migration.py tests/integration/test_backtest_engine.py tests/integration/test_paper_engine.py
git commit -m "chore: move legacy quant app aside"
```

Expected commit summary includes:

```text
chore: move legacy quant app aside
```

- [ ] **Step 7: Summarize final branch state**

Run:

```bash
cd "/Users/haobowang/Desktop/Code file/Python/LLM-Study/quant-trading"
git log --oneline -8
git status --short
```

Expected:

```text
```

`git log` shows the task commits. `git status --short` is empty, unless the pre-existing Django settings change was not included in the legacy relocation commit; in that case explicitly report it as pre-existing user work.

## Self-Review

Spec coverage:

- New package structure: Task 1.
- Existing A-share data migration: Task 2.
- Provider and validation boundary: Task 3.
- Strategy interface and MA cross migration: Task 3.
- Order, fill, position, portfolio accounting: Task 4.
- Risk rules and risk engine: Task 4.
- Portfolio event backtest with normalized persistence: Task 5.
- Paper trading one-tick flow: Task 6.
- API and jobs: Task 7.
- Docker Compose and docs: Task 8.
- Legacy separation: Task 9.

Placeholder scan:

- The plan contains no unresolved marker text or unspecified implementation steps.
- Phase-two capabilities are explicitly excluded from this milestone instead of left ambiguous.

Type consistency:

- Core type names match across tests and implementation snippets: `Bar`, `OrderIntent`, `Fill`, `Position`, `Portfolio`, `RiskDecision`.
- Enum names match across tests and implementation snippets: `Market`, `OrderSide`, `OrderStatus`, `OrderType`, `StrategyStatus`, `RiskDecisionType`.
- Repository and engine names match across integration tests and implementation snippets.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-16-quant-trading-productization.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

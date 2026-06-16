# Quant Trading Productization Design

Date: 2026-06-16
Status: Ready for user review
Scope: Rebuild `quant-trading` into a research and paper-trading platform suitable for quasi-live operation, with real-market adapters left behind explicit extension boundaries.

## Context

The current `quant-trading` project is a Claude plugin and Django demonstration app around educational scripts:

- `scripts/` contains single-asset data fetching, strategy, backtest, risk, performance, and chart helpers.
- `django_app/` provides a UI with SQLite storage, JSON result fields, direct background threads, and view-level orchestration.
- Built-in strategies use a batch `generate_signals(dataframe)` interface.
- The existing backtest engine is single-symbol and long-only, with simplified buy/sell signal execution.
- Custom Django strategies can be executed with `exec()`, which is not acceptable for productized or quasi-live operation.

Existing persisted market data was checked in `quant-trading/django_app/db.sqlite3`:

- `a_stock`: `000001 / 平安银行`, 123 daily bars from 2025-11-03 to 2026-05-08.
- `us_stock`: `AAPL` and `MSFT`, but no stored market bars.
- `crypto`: no stored symbols or market bars.

Because the only existing historical data is A-share data, phase one should use A-share daily bars as the migration and regression sample. The system must still keep provider and broker boundaries open for future US stock and crypto support.

## Goals

- Rebuild the project as a product-shaped research and paper-trading platform.
- Support reproducible historical data ingestion, validation, and storage.
- Upgrade backtesting from single-asset signal replay to portfolio-level event simulation.
- Add paper trading with realistic order lifecycle, simulated broker, portfolio accounting, and risk gates.
- Make strategy execution auditable and controlled; AI or custom strategies must not run directly in paper trading.
- Provide API and UI workflows for data, strategy, backtest, paper account, portfolio, orders, fills, and risk events.
- Provide a migration path from the current SQLite/Django sample data.

## Non-Goals

- No real broker or exchange order placement in phase one.
- No high-frequency or tick-level engine in phase one.
- No arbitrary custom Python execution in the API or UI.
- No margin, short selling, futures, options, or leveraged trading in phase one.
- No claim that any generated strategy is suitable for real-money trading.

## Recommended Route

Use route B: preserve useful domain knowledge and strategy examples, but rebuild the product core.

Rejected alternatives:

- Route A, incremental Django enhancement: faster initially, but keeps the current view-thread-JSON-script structure and unsafe custom strategy execution path.
- Route C, direct real-trading system: premature for the current data and test maturity. It would add broker risk before the platform can produce auditable research and paper results.

## Architecture

The new system is divided into seven layers:

1. Core Domain
   Pure Python domain objects and enums for bars, signals, orders, fills, positions, portfolios, risk decisions, backtest runs, and paper runs. This layer must not depend on FastAPI, SQLAlchemy, pandas, or external provider SDKs.

2. Data Platform
   Provider interfaces, ingestion jobs, validation, repositories, and market data storage. First provider is Akshare for existing A-share workflows. YFinance and CCXT adapters remain extension points.

3. Research and Backtest Engine
   Event-driven engine for portfolio-level simulation. It reuses the same order, fill, commission, slippage, risk, and accounting components that paper trading uses.

4. Paper Trading Engine
   A quasi-live loop driven by scheduled ticks. It reads latest bars, invokes approved strategies, passes intended orders through risk checks, simulates fills, updates portfolio state, and stores snapshots.

5. Risk and Compliance Gate
   Pre-trade and post-trade rules that can approve, reject, reduce, or halt orders/runs. All decisions are persisted.

6. API and UI
   FastAPI exposes operational APIs. The first UI can be FastAPI templates with HTMX or a simple React/Next app. The design priority is workflow clarity over a complex frontend.

7. Jobs and Operations
   Redis-backed task queue for ingestion, backtests, parameter experiments, paper ticks, and reports. Docker Compose provides local Postgres, Redis, and API services.

## Proposed Directory Structure

```text
quant-trading/
  pyproject.toml
  src/quant_trading/
    core/
      models.py
      enums.py
      clocks.py
      errors.py
    data/
      providers/
        base.py
        akshare_provider.py
        yfinance_provider.py
        ccxt_provider.py
      repository.py
      validation.py
      ingestion.py
    strategy/
      base.py
      registry.py
      sandbox.py
      builtin/
        ma_cross.py
        momentum.py
        mean_reversion.py
        grid.py
    portfolio/
      accounting.py
      valuation.py
      metrics.py
    execution/
      broker.py
      simulator.py
      slippage.py
      commission.py
      order_manager.py
    risk/
      rules.py
      engine.py
    backtest/
      engine.py
      result.py
      experiment.py
    paper/
      engine.py
      state.py
    api/
      main.py
      routes/
        data.py
        strategies.py
        backtests.py
        paper.py
        portfolios.py
    jobs/
      queue.py
      tasks.py
    storage/
      db.py
      models.py
      migrations/
    reporting/
      tear_sheet.py
      charts.py
  tests/
    unit/
    integration/
    fixtures/
```

The current Django app should move to `legacy/django_app` during implementation. It is a migration reference, not the foundation of the new product core.

## Data Model

Use PostgreSQL in development and production-like environments. If TimescaleDB is available, `market_bars`, equity curves, and snapshots can become hypertables; the schema must still run on plain PostgreSQL.

### Market Data

```text
instruments
- id
- symbol
- name
- market
- asset_type
- currency
- exchange
- status
- created_at

market_bars
- instrument_id
- timestamp
- timeframe
- open
- high
- low
- close
- volume
- amount
- adjusted
- source
- ingestion_batch_id

ingestion_batches
- id
- provider
- market
- started_at
- finished_at
- status
- row_count
- error_message
```

`market_bars` has a uniqueness constraint on `instrument_id, timestamp, timeframe, adjusted, source`.

### Strategy and Backtest

```text
strategies
- id
- name
- strategy_type
- version
- parameters_schema
- source_kind
- status
- created_at

backtest_runs
- id
- strategy_id
- universe_config
- parameter_config
- start_at
- end_at
- initial_cash
- commission_model
- slippage_model
- benchmark_instrument_id
- status
- metrics_json
- created_at

backtest_equity_points
- run_id
- timestamp
- equity
- cash
- market_value
- drawdown

backtest_orders
backtest_fills
backtest_positions
```

JSON fields can store summaries and configs, but queryable entities such as orders, fills, equity points, and positions must be normalized.

### Paper Trading

```text
paper_accounts
- id
- name
- base_currency
- initial_cash
- status

paper_runs
- id
- account_id
- strategy_id
- universe_config
- schedule_config
- risk_config
- status
- started_at
- stopped_at

orders
- id
- run_id
- instrument_id
- side
- order_type
- quantity
- limit_price
- status
- submitted_at
- reason
- risk_decision_id

fills
- id
- order_id
- instrument_id
- quantity
- price
- commission
- slippage
- filled_at

positions
- account_id
- instrument_id
- quantity
- avg_cost
- market_price
- unrealized_pnl
- updated_at

portfolio_snapshots
- account_id
- timestamp
- equity
- cash
- market_value
- realized_pnl
- unrealized_pnl
- drawdown
```

### Risk and Audit

```text
risk_decisions
- id
- order_id nullable
- run_id
- decision
- rule_name
- message
- created_at

audit_events
- id
- actor
- action
- entity_type
- entity_id
- payload_json
- created_at
```

## Strategy Interface

The new strategy interface is event-oriented:

```python
class Strategy:
    def on_start(self, context): ...
    def on_bar(self, context, bars): ...
    def on_stop(self, context): ...
```

`on_bar` returns either order intents or a target portfolio. A compatibility adapter can wrap existing `generate_signals(dataframe)` strategies so the current built-ins can be migrated and regression tested.

First phase allowed strategy sources:

- Built-in strategies.
- Parameterized registered strategies.
- AI-generated strategy drafts for offline review and backtest only.

AI-generated or uploaded strategies cannot enter a paper run until manually approved. Arbitrary `exec()` is removed from the product path.

## Paper Trading Flow

```text
Scheduler tick
-> MarketDataRepository reads latest bars
-> Strategy.on_bar/on_snapshot creates order intents or targets
-> RiskEngine.pre_trade_check
-> OrderManager creates orders
-> PaperBroker simulates fills
-> PortfolioAccounting updates cash, positions, and PnL
-> RiskEngine.post_trade_check
-> PortfolioSnapshot is stored
-> Metrics and reports are updated
-> API/UI exposes current state
```

Order lifecycle:

```text
CREATED
-> RISK_CHECKED
-> SUBMITTED
-> PARTIALLY_FILLED
-> FILLED / CANCELLED / REJECTED
```

Phase one execution assumptions:

- Daily bars.
- Market order simulation.
- Limit order model can exist, but full behavior is not required.
- Fixed commission model.
- Fixed or percent slippage model.
- No short selling.
- No real broker submission.

For A-shares:

- No short selling.
- Default lot size is 100 shares.
- Daily close-price matching is acceptable for phase one, but every report must state the matching assumption.
- T+1 can be modeled as a configurable rule; initial implementation may keep it disabled if clearly reported.

## Risk Rules

Phase one includes these hard rules:

- `MaxGrossExposureRule`: total exposure limit.
- `MaxInstrumentWeightRule`: single-instrument concentration limit.
- `MaxOrderValueRule`: per-order notional limit.
- `MaxDrawdownRule`: drawdown halt.
- `DailyLossLimitRule`: daily loss halt.
- `NoTradeWithoutDataRule`: reject trading when bars are missing or stale.
- `PriceSanityRule`: reject orders when prices are invalid or abnormal.
- `StrategyStatusRule`: reject unapproved strategies for paper trading.

Risk decisions must be persisted and visible in UI/API responses.

## Technology Stack

Recommended stack:

```text
Backend: FastAPI
Domain: Python dataclasses plus Pydantic DTOs
ORM: SQLAlchemy 2.x plus Alembic
Database: PostgreSQL, optional TimescaleDB
Queue: Redis plus RQ
Frontend: FastAPI templates with HTMX or a simple React/Next app
Charts: ECharts
Testing: pytest
Packaging: pyproject.toml with src layout
Deploy: Docker Compose
```

Rationale:

- FastAPI keeps the API surface explicit and works well with a separate domain package.
- SQLAlchemy and Alembic make schema ownership explicit.
- PostgreSQL gives queryable market, order, fill, and audit data; SQLite remains acceptable only for isolated tests.
- RQ is enough for the first set of ingestion, backtest, report, and paper tick jobs. Celery can replace it later if workflow complexity grows.

## Migration Plan

### Phase 1: Skeleton and Infrastructure

- Create `src/quant_trading/`.
- Add `pyproject.toml`.
- Configure pytest.
- Add Docker Compose for Postgres, Redis, and API.
- Create database session and migration framework.

### Phase 2: Data Layer

- Implement `Instrument`, `MarketBar`, and `IngestionBatch`.
- Implement `MarketDataProvider`.
- Port Akshare provider first.
- Import existing `000001` bars from the legacy SQLite database.
- Add OHLCV validation, duplicate detection, and range queries.

### Phase 3: Core Trading Domain

- Implement `Order`, `Fill`, `Position`, and `Portfolio`.
- Implement commission, slippage, and simulated matching.
- Implement portfolio valuation and snapshots.
- Add unit tests for order lifecycle and cash/position accounting.

### Phase 4: Backtest Engine

- Implement event-driven portfolio backtest.
- Migrate built-in strategies.
- Add adapter for legacy signal strategies.
- Persist equity points, orders, fills, positions, and metrics.
- Use existing `000001` data as the first regression fixture.

### Phase 5: Paper Trading

- Implement `PaperBroker`.
- Implement `paper_runs`.
- Add RQ-driven paper ticks.
- Support start, pause, stop, and status queries.
- Persist portfolio snapshots.

### Phase 6: Risk and Audit

- Implement pre-trade risk rules.
- Implement drawdown and daily-loss halts.
- Store `risk_decisions` and `audit_events`.
- Enforce approved-only strategies for paper runs.

### Phase 7: API and UI

- Add data management views.
- Add strategy list and parameter views.
- Add backtest run and result views.
- Add paper account monitoring.
- Add portfolio, order, fill, and risk event views.

### Phase 8: Legacy Cleanup

- Move Django app to `legacy/django_app`.
- Rewrite README for the new platform.
- Keep a migration note for the old plugin and Django app.
- Remove unsafe custom strategy execution from supported flows.

## Testing Strategy

- Unit tests for domain models, accounting, risk rules, strategy registry, and provider normalization.
- Integration tests for database repositories and migrations.
- Backtest regression tests using imported `000001` sample data.
- Paper engine tests for order lifecycle, rejected orders, halted runs, and portfolio snapshots.
- API tests for core workflow endpoints.
- Legacy migration test that imports the current SQLite sample into the new schema.

## Acceptance Criteria

The first productized milestone is complete when:

- The new project installs from `pyproject.toml`.
- Postgres, Redis, and API start with Docker Compose.
- Existing `000001` data imports into `instruments` and `market_bars`.
- A built-in MA cross strategy runs through the new backtest engine.
- Backtest results persist as normalized equity, order, fill, and metric records.
- A paper account can run one scheduled simulated tick against existing data.
- Risk rules can reject at least one invalid order and record the decision.
- API/UI can display instruments, backtest results, paper account state, orders, fills, and risk decisions.
- Tests cover the domain accounting, risk rules, backtest path, paper tick path, and legacy data import.

## Review Notes

This design intentionally does not optimize for real broker integration in phase one. The correct sequence is to build auditable research and paper trading first, then add broker adapters once data quality, strategy approval, accounting, and risk controls are reliable.

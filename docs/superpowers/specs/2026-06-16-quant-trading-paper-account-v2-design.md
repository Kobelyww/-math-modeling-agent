# Quant Trading Paper Account V2 Design

Date: 2026-06-16
Status: Ready for user review
Scope: Stage 2 for `quant-trading`: persistent paper-trading accounts, order/fill/position/cash ledgers, and query APIs. The schema should not block future multi-strategy and multi-symbol paper runs, but the implementation milestone only delivers a single strategy on a single symbol.

## Context

Stage 1 rebuilt `quant-trading` into a product-shaped Python package under `src/quant_trading/` with normalized market data, MA cross strategy support, portfolio backtesting, risk-gated paper ticks, FastAPI read APIs, Docker Compose, and legacy code moved under `legacy/`.

The current paper engine is intentionally thin:

- `PaperTradingEngine.run_one_tick(symbol, strategy, strategy_status)` creates a new `PaperAccountORM` every call.
- The tick builds a fresh in-memory `Portfolio` from `initial_cash`.
- Approved fills update only the in-memory portfolio and the final `PortfolioSnapshotORM`.
- The database persists snapshots and risk decisions, but not paper orders, fills, current positions, or cash ledger events.
- There is no `paper_run` state, no account restoration across ticks, and no API to inspect paper orders, fills, or positions.

That is enough for a first vertical slice, but not enough for quasi-live validation. A realistic paper system must be able to recover state from storage, prove why every order happened, and keep cash, positions, fills, and snapshots consistent over time.

## Goals

- Turn paper trading from a stateless one-tick demo into a persistent account workflow.
- Preserve clear future extension points for multi-strategy and multi-symbol accounts.
- Implement only one strategy on one symbol for this milestone.
- Persist paper runs, orders, fills, positions, cash ledger entries, snapshots, and risk decisions.
- Make `run_one_tick(run_id)` deterministic, idempotent for an already-processed bar, and recoverable from database state.
- Add query APIs for accounts, runs, orders, fills, positions, snapshots, and risk decisions.
- Keep real broker integration out of scope while using real broker-like state transitions.

## Non-Goals

- No real broker or exchange adapter.
- No live scheduler daemon in this milestone; job wrappers may call the tick engine manually.
- No multi-strategy order netting in the implementation milestone.
- No multi-symbol valuation in the implementation milestone.
- No partial fills, cancels, replace orders, or asynchronous broker callbacks.
- No strategy upload or arbitrary Python execution.
- No frontend beyond API readiness.

## Recommended Approach

Use an account state machine with an event ledger:

1. `paper_accounts` stores long-lived accounts.
2. `paper_runs` binds an account to a strategy, universe config, risk config, and run status.
3. Each tick restores the latest portfolio state from `paper_positions` and `cash_ledger`.
4. Strategy intents become `paper_orders`.
5. Risk checks update the order and create `risk_decisions`.
6. Approved market orders produce `paper_fills` and cash ledger rows.
7. Positions are updated in `paper_positions`.
8. The tick writes one `portfolio_snapshots` row for the processed bar.

This keeps every state change explainable. It also avoids overbuilding a full OMS/EMS before the platform has production-like account persistence.

Rejected alternatives:

- Minimal patch with `account_id` on current `run_one_tick`: too easy to keep hidden state in memory and still miss order/fill/cash auditability.
- Full OMS/EMS simulation: useful later, but partial fills, cancel/replace, and asynchronous broker states are too much for this stage.

## Operating Model

The data model should represent multi-strategy and multi-symbol concepts, but the stage 2 engine will validate one run with one strategy and one symbol.

### Future-Proof Shape

- `paper_runs.universe_config` is JSON text that can later hold multiple symbols.
- `paper_orders` and `paper_fills` carry `run_id`, `account_id`, `instrument_id`, and `symbol`.
- `paper_positions` are keyed by account and instrument, not only by run.
- Risk decisions can reference both `run_id` and `order_id`.

### Stage 2 Constraint

For this milestone:

- A run has exactly one symbol.
- A run has exactly one strategy name and parameter config.
- The engine processes one latest daily bar per tick.
- If that bar was already processed for the run, the tick returns a no-op summary and does not duplicate orders, fills, ledgers, or snapshots.

## Data Model Changes

Existing tables remain:

- `paper_accounts`
- `portfolio_snapshots`
- `risk_decisions`

Add or extend these tables.

### paper_runs

```text
id
account_id
strategy_name
symbol
universe_config
strategy_config
risk_config
status
last_processed_at
started_at
stopped_at
created_at
```

Status values:

- `created`
- `running`
- `paused`
- `stopped`
- `error`

### paper_orders

```text
id
run_id
account_id
instrument_id
symbol
side
order_type
quantity
limit_price
reason
status
risk_decision
submitted_at
created_at
```

Status values for stage 2:

- `created`
- `risk_rejected`
- `filled`
- `skipped`

`skipped` is used when an order intent is approved but cannot be executed because account state prevents it, such as insufficient cash.

### paper_fills

```text
id
run_id
account_id
order_id
instrument_id
symbol
side
quantity
price
commission
slippage
filled_at
created_at
```

### paper_positions

```text
id
account_id
instrument_id
symbol
quantity
avg_cost
market_price
realized_pnl
updated_at
```

Unique key:

```text
account_id, instrument_id
```

Rows with zero quantity may be deleted or retained with `quantity = 0`; the implementation must choose one behavior and tests must lock it down. Preferred behavior: retain the row with zero quantity for audit-friendly history of previously held symbols.

### cash_ledger

```text
id
account_id
run_id
order_id
fill_id
event_type
amount
cash_after
currency
occurred_at
created_at
```

Event types for stage 2:

- `initial_deposit`
- `buy_notional`
- `sell_notional`
- `commission`
- `manual_adjustment`

The initial deposit ledger row is created once per account.

### risk_decisions Extension

Current table:

```text
id
run_id
order_id
decision
rule_name
message
created_at
```

Stage 2 keeps this shape, but `order_id` must be populated whenever the decision came from a paper order. `run_id` must point to the paper run, not the account id.

## Domain Objects

Add framework-free models where useful:

- `PaperRun`
- `PaperOrder`
- `CashLedgerEntry`
- `PaperTickSummary`

`PaperTickSummary` should include:

```text
run_id
account_id
processed_at
orders_created
orders_filled
orders_rejected
fills_created
snapshot_created
idempotent_noop
```

## Engine API

Replace the account-creating tick call with explicit lifecycle methods.

```python
class PaperTradingEngine:
    def create_account(name: str, initial_cash: Decimal, base_currency: str = "CNY") -> int:
        ...

    def start_run(
        account_id: int,
        symbol: str,
        strategy: Strategy,
        strategy_name: str,
        strategy_status: StrategyStatus,
        risk_config: dict | None = None,
    ) -> int:
        ...

    def run_one_tick(run_id: int, strategy: Strategy, strategy_status: StrategyStatus) -> PaperTickSummary:
        ...
```

The strategy object is still supplied by the caller in stage 2 to avoid persisting or dynamically loading arbitrary Python. Later stages can add a strategy registry-backed loader.

## Tick Flow

1. Load `paper_run` and validate status.
2. Load bars for the run symbol.
3. Select latest daily bar.
4. If `latest.timestamp <= paper_run.last_processed_at`, return an idempotent no-op summary.
5. Restore portfolio from current `paper_positions` and latest cash derived from `cash_ledger`.
6. Invoke strategy with full bar history and restored portfolio.
7. For each intent:
   - Insert `paper_order` with status `created`.
   - Run risk checks.
   - Insert `risk_decision` with `run_id` and `order_id`.
   - If rejected, update order status to `risk_rejected` and continue.
   - If approved, simulate a market fill.
   - Apply fill to the restored portfolio.
   - If accounting fails, update order status to `skipped` and continue for insufficient cash; re-raise unexpected accounting errors.
   - Insert `paper_fill`.
   - Insert cash ledger rows for notional and commission.
   - Upsert `paper_positions`.
   - Update order status to `filled`.
8. Update mark prices for existing positions using the latest bar.
9. Insert `portfolio_snapshot`.
10. Update `paper_run.last_processed_at`.

All writes for one tick must happen inside one database transaction.

## API Changes

Add read APIs:

```text
GET /paper/accounts
GET /paper/accounts/{account_id}
GET /paper/accounts/{account_id}/positions
GET /paper/accounts/{account_id}/cash-ledger
GET /paper/runs
GET /paper/runs/{run_id}
GET /paper/runs/{run_id}/orders
GET /paper/runs/{run_id}/fills
GET /paper/runs/{run_id}/risk-decisions
GET /paper/runs/{run_id}/snapshots
```

Add minimal command APIs:

```text
POST /paper/accounts
POST /paper/runs
POST /paper/runs/{run_id}/ticks
POST /paper/runs/{run_id}/pause
POST /paper/runs/{run_id}/resume
POST /paper/runs/{run_id}/stop
```

Command APIs are not part of the stage 2 acceptance bar. If implementation capacity remains after persistence and read APIs are complete, they may be added, but they are not required for this milestone. Read APIs for persisted state are required.

## Job Changes

Add job task:

```python
run_paper_tick_task(database_url: str, run_id: int) -> dict
```

This task should call the engine and return the `PaperTickSummary` fields. It should not silently create a new account or run.

## Testing Strategy

Use TDD for implementation. Required tests:

1. Creating an account writes exactly one initial deposit ledger entry.
2. Starting a run links account, strategy, symbol, and status.
3. First approved buy tick creates one order, one risk decision, one fill, cash ledger rows, one position, and one snapshot.
4. Second tick on the same already-processed bar is idempotent and creates no duplicate rows.
5. A later bar restores the existing position and cash before strategy evaluation.
6. A rejected strategy status creates an order and risk decision but no fill, no cash ledger entry, and no position change.
7. Insufficient cash marks the order as `skipped` without changing cash or positions.
8. API endpoints list the persisted account, run, orders, fills, positions, ledger, snapshots, and risk decisions.
9. Full current test suite passes after migration.

## Acceptance Criteria

- Paper trading no longer creates a new account for every tick.
- Paper account cash is reconstructable from `cash_ledger`.
- Current positions are stored in `paper_positions`.
- Every approved executed order has a fill and ledger entries.
- Every rejected order has a persisted risk decision.
- Snapshot equity equals cash plus current market value at the processed bar.
- Re-running a tick for the same bar does not duplicate side effects.
- Existing backtest, storage, strategy, risk, API, and legacy migration tests still pass.

## Migration Notes

Existing stage 1 data does not need a production migration. The implementation will use SQLAlchemy `create_all()` for local/test setup. If a developer already has a local `quant_trading.db`, they should recreate it for this milestone.

## Risks

- If current positions are derived only from snapshots, state will drift. Positions must be authoritative in `paper_positions`.
- If cash is stored only on snapshots, cash changes cannot be audited. Cash ledger must be authoritative.
- If idempotency is missing, scheduled ticks can duplicate orders and fills.
- If order status is inferred from fills, rejected/skipped orders become invisible. Orders need explicit status.

## Implementation Choices

- Keep zero-quantity position rows for auditability. This spec chooses yes.
- Exclude command APIs from the required stage 2 acceptance bar. Read APIs are required.
- Persist strategy object code. This spec chooses no; strategy instances remain caller-supplied for stage 2.

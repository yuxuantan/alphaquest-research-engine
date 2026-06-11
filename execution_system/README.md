# Databento Signal Engine

`execution_system` is now an alert-only trading signal engine. It does not send
orders, talk to IBKR or Tradovate, or enforce prop-firm guardrails.

The engine:

1. Loads campaign-style strategy YAML files from `configs/campaigns`.
2. Warms strategy state from historical ES Databento trade ticks or a cached
   1-minute orderflow seed file.
3. Aggregates live Databento trade ticks into completed 1-minute orderflow bars.
4. Builds the same `propstack` features and modular strategy objects used by
   backtests.
5. Queues a signal when a completed strategy bar triggers.
6. Emits `ENTRY_SIGNAL` on the next tradable tick/open with direction, contract
   size, entry price, take profit, and stop loss.

## Files

- `databento_signal_engine.py`: main engine and CLI.
- `strategy_execution_bridge.py`: compatibility wrapper that launches the new
  engine.
- `signal_engine.example.yaml`: execution config, selected strategies, Databento
  settings, sizing account assumptions, and alert output path.

## Preflight

Validate the selected strategy YAMLs without connecting to Databento:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --preflight-only
```

## Historical Seed

Set a Databento key, then fetch/cache historical trade ticks as 1-minute
orderflow bars and hydrate strategy state:

```bash
export DATABENTO_API_KEY="..."

python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --seed-only
```

The default seed cache is:

```text
execution_system/data/databento/es_trade_orderflow_seed_1m.csv
```

Use `--refresh-historical` to ignore that cache and fetch again.

## Replay

Replay cached 1-minute orderflow bars through the live-style path:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --skip-historical \
  --replay-bars execution_system/data/databento/es_trade_orderflow_seed_1m.csv \
  --replay-stop-after-signal
```

Replay alerts are emitted on the next bar open, matching the live next-tick
entry timing.

## Live

Enable live streaming with either `databento.live.enabled: true` or `--live`:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --live
```

For lower bandwidth, override the configured Databento symbol with the current
front contract:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --databento-symbols ESM6 \
  --databento-stype-in raw_symbol \
  --live
```

## Alert Contract

Each actionable alert is printed as one JSON object prefixed with
`ENTRY_SIGNAL` and appended to `engine.alerts_path` when configured.

Important fields:

- `direction`: `long` or `short`
- `side`: `buy` or `sell`
- `quantity`: contract size after configured sizing clamps
- `entry_price`: market-entry estimate using the next tick/open plus configured
  slippage
- `take_profit_price`
- `stop_loss_price`
- `take_profit_points`
- `stop_loss_points`
- `risk_dollars`
- `reward_dollars`
- `signal`: raw strategy signal metadata
- `sizing`: sizing-mode details from `propstack.backtest.sizing`

Signals that cannot produce valid stops, targets, or size are printed as
`SIGNAL_REJECTED`.

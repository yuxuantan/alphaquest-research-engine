# Signal Engine Run Commands

Run these from the repo root:

```bash
cd /Users/yx/Desktop/prop_stack_automation
```

Default morning orderflow config:

```bash
CONFIG=execution_system/morning_orderflow_momentum_signal_engine.example.yaml
SCRIPT=execution_system/databento_signal_engine.py
```

Important: this config currently has `databento.live.enabled: true` and the live
subscription guard acknowledged. Commands that are not explicitly exit-only can
start live mode after historical seed loading.

## Safe Checks

Config-only preflight:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --preflight-only
```

Readiness check. Uses metadata/local cache checks and does not open a live
subscription:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --readiness-check
```

Databento metadata/schema/cost check only:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --check-databento-metadata
```

Load historical seed bars and exit:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --seed-only
```

## Dummy ETH Test

The dummy config is intended for live plumbing tests and now has an explicit
ETH window so it can evaluate outside RTH. Use it when you only want to verify
live subscription, source-bar building, setup/entry output, and health stops:

```bash
DUMMY_CONFIG=execution_system/dummy_delta_signal_engine.example.yaml
python3 -B "$SCRIPT" --config "$DUMMY_CONFIG" --live
```

It keeps `stop_on_no_evaluable_strategies: true`. If that stop fires, the live
feed is moving but the dummy strategy still is not receiving evaluable bars.

## Replay

Replay the local Databento-derived orderflow cache and stop after the first
entry signal:

```bash
python3 -B "$SCRIPT" \
  --config "$CONFIG" \
  --skip-historical \
  --dry-run-alerts \
  --replay-bars data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv \
  --replay-stop-after-signal \
  --replay-require-signal \
  --replay-require-healthy-strategies
```

Replay with full JSON output for debugging:

```bash
python3 -B "$SCRIPT" \
  --config "$CONFIG" \
  --skip-historical \
  --dry-run-alerts \
  --debug \
  --replay-bars data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv \
  --replay-stop-after-signal \
  --replay-require-signal \
  --replay-require-healthy-strategies
```

Replay without stopping after the first signal:

```bash
python3 -B "$SCRIPT" \
  --config "$CONFIG" \
  --skip-historical \
  --dry-run-alerts \
  --replay-bars data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv \
  --replay-require-healthy-strategies
```

## Sound Checks

Play the configured warning/setup sound and exit without Databento access:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --test-sound setup
```

Play the configured entry sound:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --test-sound entry
```

Play all configured operator sounds:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --test-sound all
```

Do not combine `--test-sound` with `--dry-run-alerts`; dry-run mode suppresses
sound by design.

## Live

Live mode receives only new Databento records from the time the subscription
connects. For `morning_orderflow_momentum`, the engine must already have the
current RTH session's completed 1-minute bars from 09:30 ET because the strategy
uses cumulative signed volume from the open and price change from the open.

On live startup, the morning config checks that required current-session context
exists before it emits any strategy signals. If you start at 10:00 ET, it
requires the completed 09:30-09:59 ET source bars. If any required bars are
missing or gapped, it tries `databento.historical.current_session_backfill`
through the existing historical cost guard. If gaps remain, this config starts
live in deferred catch-up mode: live source bars are buffered, but
`TRADE_WARNING`, `TRADE_SETUP`, and `ENTRY_SIGNAL` are disabled until historical
backfill fills the missing gap and the 09:30-to-live bar chain is continuous.
If Databento reports a paid or unavailable cost estimate, the guard stops before
the historical download. Databento historical metadata can lag the current live
session; in that case the backfill may be free and still only return finalized
bars up to an earlier minute, so the engine keeps retrying.

Do not use `--skip-historical` for a mid-session live run of this strategy unless
you are intentionally testing the failure path or you already seeded the process
some other way.

Start live mode. This can open a Databento live subscription:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --live
```

Live dry run. This can still open a Databento live subscription, but it does not
write alert JSONL files or play sounds:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --live --dry-run-alerts
```

Short live smoke run:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --live --max-runtime 120
```

Stop after the first completed live source bar:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --live --once
```

Live with full JSON output:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --live --debug
```

The morning config also prints streamed live data in normal console mode:

- `LIVE_TICK`: accepted live trade ticks, throttled by
  `engine.console.live_stream.tick_throttle_seconds`.
- `LIVE_BAR`: completed 1-minute source bars.
- `LIVE_SESSION`: after each completed live bar, current RTH-session market
  open price, current price, total volume, cumulative delta, and price change.
- `TRADE_WARNING`: prep warning before setup; for the morning strategy this is
  printed one completed bar before the intended entry when non-time criteria are
  already satisfied.
- `TRADE_SETUP`: strategy fired; prepare but wait for entry trigger.
- `ENTRY_SIGNAL`: actionable manual/future-router trade instruction.

## Outbox Checks

Validate execution-intent records:

```bash
python3 -B "$SCRIPT" --config "$CONFIG" --check-execution-intents
```

Require at least one currently actionable execution intent:

```bash
python3 -B "$SCRIPT" \
  --config "$CONFIG" \
  --check-execution-intents \
  --require-actionable-intent
```

Strict outbox validation:

```bash
python3 -B "$SCRIPT" \
  --config "$CONFIG" \
  --check-execution-intents \
  --strict-execution-intents
```

## Common Flags

- `--preflight-only`: validate config and exit.
- `--readiness-check`: fail-closed startup checks without live subscription.
- `--check-databento-metadata`: metadata/schema/cost validation.
- `--seed-only`: load/fetch historical context and exit.
- `--skip-historical`: do not load historical seed data.
- `--refresh-historical`: ignore seed/cache and run the guarded historical fetch path.
- `--replay-bars PATH`: replay cached 1-minute bars.
- `--replay-stop-after-signal`: stop replay after first `ENTRY_SIGNAL`.
- `--replay-require-signal`: fail if replay produces no `ENTRY_SIGNAL`.
- `--replay-require-healthy-strategies`: fail on disabled/unevaluated/error strategies.
- `--dry-run-alerts`: print and validate alerts without JSONL writes or sounds.
- `--live`: start Databento live mode.
- `--once`: stop after first completed live source bar.
- `--max-runtime SECONDS`: cap live runtime.
- `--debug`: print full JSON console payloads.
- `--test-sound {setup,entry,system,all}`: play configured operator sound(s) and exit.

# Databento Signal Engine

`execution_system` is an alert-only trading signal engine for ES. It does not
place orders, talk to IBKR or Tradovate, or enforce prop-firm guardrails. Its
job is to turn Databento historical/live ticks into the same 1-minute orderflow
feature stream used by the backtester, run selected strategies, and print an
actionable `ENTRY_SIGNAL` when a trade should be taken.

An alert includes:

- direction: `long` or `short`
- side: `buy` or `sell`
- contract size after configured sizing rules
- market-entry estimate
- take profit
- stop loss
- optional setup/entry terminal sound
- risk/reward in points and dollars
- raw strategy metadata used to produce the signal

## Mental Model

The engine is a deterministic pipeline:

```text
Databento records
  -> normalized TradeTick objects
  -> completed 1-minute SourceMinuteBar objects
  -> BarStore rolling source-bar history
  -> StrategyRuntime feature frame
  -> PendingSignal on completed strategy bars
  -> ENTRY_SIGNAL plus execution_intent on the next tradable tick/open
```

The most important design rule is that strategy decisions are made only after a
bar is complete. For a 1-minute strategy, the 09:31:00 bar represents the minute
from 09:31:00 through 09:31:59.999. The engine can evaluate that bar only after
the next minute starts. If that completed bar produces a setup, the actionable
entry is the first tradable live tick at or after 09:32:00. In replay mode, the
engine uses the next bar's open as that entry tick.

This means there are two separate moments:

- `TRADE_SETUP`: the strategy has fired on a completed bar, but the engine is
  waiting for the next entry tick/open.
- `ENTRY_SIGNAL`: the trade is actionable now, with final entry, quantity, stop,
  target, risk, reward, and an automation-facing `execution_intent`.

The engine is intentionally not an order router. It produces a complete and
validated trade instruction that can be used manually today and by a future
router later.

## How The Engine Runs

The engine has one main executable:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml
```

The YAML config tells it which Databento feed to use, which strategies to load,
how much historical context to seed, how to size trades, where to write alerts,
and how to monitor the live stream. CLI flags then choose the run mode:

- `--preflight-only`: validate config and strategy wiring, then exit.
- `--check-databento-metadata`: validate Databento metadata/cost without
  downloading ticks or subscribing live.
- `--seed-only`: load or fetch historical bars, hydrate strategies, then exit.
- `--replay-bars path.csv`: replay cached 1-minute bars through the live signal
  path.
- `--live`: connect to Databento live and keep streaming until stopped.

At startup, `run()` performs these steps:

1. Loads the YAML config and applies CLI overrides.
2. Creates `SignalEngine`, which validates runtime settings, strategy ids,
   Databento settings, alert sinks, execution-intent sinks, and inferred data
   requirements.
3. Prints a `preflight` JSON object so the exact config, strategy modules,
   Databento subscription, alert paths, and data plan are visible before work
   starts.
4. Acquires the process lock for mutating modes so two engine processes do not
   write the same alert/outbox files.
5. Loads historical seed bars unless `--skip-historical` is set.
6. Before live mode, optionally runs a metadata-only Databento preflight that
   validates dataset/schema/fields/symbology and historical cost guard without
   downloading timeseries data or subscribing live.
7. Before live mode, audits whether the current in-memory bars satisfy the
   selected strategies' inferred warmup sessions.
8. Runs one of the selected modes: seed-only, replay, live, or exit.

The important point is that historical, replay, and live data all converge into
the same internal object: `SourceMinuteBar`. Once a bar reaches `BarStore`, the
strategy evaluation path is the same regardless of where the bar came from.

### Seed Mode

`--seed-only` exists to build or validate the historical context that live
strategies need before real-time ticks arrive.

When you run:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --seed-only
```

the engine:

1. Checks whether `databento.historical.cache_path` already exists.
2. If the cache exists and refresh is false, loads the cached 1-minute bars.
3. If the cache is missing or `--refresh-historical` is used, requests
   historical Databento ticks, aggregates them into 1-minute orderflow bars,
   writes the CSV cache, and writes a `.metadata.json` sidecar.
4. Validates source-bar quality.
5. Seeds `BarStore`.
6. Hydrates each strategy so rolling features, ranks, session counters, and
   daily trade counters begin from realistic context.
7. Exits without producing live alerts.

This mode intentionally may download or load multiple days of data. The engine
is not trying to get "today only"; it is trying to provide enough completed
1-minute bars for the selected strategies' feature windows and warmup sessions.

### Replay Mode

Replay mode is the offline approximation of live signal timing. It does not
cheat by entering on the same bar that produced the signal.

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/dummy_delta_signal_engine.example.yaml \
  --skip-historical \
  --replay-bars execution_system/data/databento/es_trade_orderflow_seed_1m.csv \
  --replay-stop-after-signal
```

The replay loop keeps two bars in mind:

```text
previous replay bar -> treated as the newly completed signal bar
current replay bar  -> its open is treated as the next tradable entry tick
```

For each replay step, the engine:

1. Pushes the previous bar through `on_completed_source_bar()`.
2. Rebuilds features and lets strategies evaluate the completed bar.
3. Queues any setup as a `PendingSignal`.
4. Converts the current bar open into a synthetic entry tick.
5. Calls `on_entry_tick()` so due pending setups can become `ENTRY_SIGNAL`
   records.

This is why replay is useful for checking whether a strategy fires, whether the
entry delay is correct, whether stop/target math is correct, and whether JSONL
alert output is valid.

### Live Mode

Live mode subscribes to Databento and keeps running:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/dummy_delta_signal_engine.example.yaml \
  --live
```

The live loop has two threads of work:

- Databento callbacks process records as they arrive.
- A maintenance loop finalizes wall-clock-complete bars and expires stale
  pending entries.
- A status loop prints `live_status` and emits feed-health `SYSTEM_ALERT`
  messages.

For every Databento live record, the callback does this:

1. Counts the raw record for health monitoring.
2. Converts trade records into `TradeTick` with timestamp, price, size, side,
   contract, and optional bid/ask.
3. Updates clock-lag diagnostics by comparing Databento `ts_event` with local
   UTC wall clock.
4. Adds the tick to `TradeBarBuilder`.
5. If the tick starts a later minute, flushes the previous minute into one or
   more completed `SourceMinuteBar` objects.
6. On each maintenance heartbeat, optionally flushes any active minute whose
   end time is at least `bar_flush_delay_seconds` behind local UTC wall clock.
7. Drops the first completed live bar when
   `drop_partial_first_live_bar: true`, because the process may have started
   mid-minute.
8. Evaluates strategies on completed bars.
9. Uses the current tick as the possible entry tick for any pending setup whose
   due time has arrived.

Live alerts only happen at step 8. A strategy can fire on a completed bar, but
the final actionable alert waits for the next tradable tick/open so the engine
does not enter using incomplete bar information.

### Strategy State Machine

Every strategy follows this state machine:

```text
historical/replay/live source bar
  -> validate source bar
  -> append to BarStore
  -> build or update feature dataframe
  -> call strategy.on_bar_close()
  -> no signal: stop
  -> signal: create PendingSignal due at next bar open
  -> wait for next entry tick/open
  -> validate lag, direction, stop, target, tick grid, and sizing
  -> emit ENTRY_SIGNAL or SIGNAL_REJECTED
```

`PendingSignal` is the key separation between "the strategy has a setup" and
"the user should enter now." A setup is only actionable when an entry tick/open
arrives at or after:

```text
signal bar timestamp + strategy timeframe
```

If that entry tick arrives too late, the setup is rejected with
`SIGNAL_REJECTED` instead of being turned into an old trade idea.

### What Gets Persisted

The engine writes three optional JSONL streams:

- `engine.setup_alerts.path`: durable `TRADE_SETUP` records for preparation and
  audit. These are not executable instructions.
- `engine.alerts_path`: full `ENTRY_SIGNAL` records for audit/manual use.
- `engine.execution_intents.path`: smaller router-facing
  `execution_intent_ready` records for future automation.

Setup notices suppress duplicates by deterministic `setup_id`; entry alerts and
execution intents suppress duplicates by deterministic `alert_id`. The two ids
are namespace-separated even when a setup due timestamp equals the entry tick
timestamp. This matters for replay and restarts: the same signal should not
become a new preparation record or router instruction just because the process
was restarted.

## Signal Timeline Example

Assume a 1-minute strategy and a live ES trade stream:

```text
09:31:00.000  first trade of the 09:31 bar arrives
09:31:00-59   the engine keeps accumulating OHLCV and delta
09:32:00.000  a later-minute trade arrives, so the 09:31 bar is complete
09:32:00.xxx  the completed 09:31 bar is added to BarStore
09:32:00.xxx  features are rebuilt and the strategy evaluates the 09:31 row
09:32:00.xxx  if the strategy fires, TRADE_SETUP is printed
09:32:00.xxx  the same tick, or next eligible tick, becomes the market entry
09:32:00.xxx  ENTRY_SIGNAL is printed with entry, quantity, stop, and target
```

The engine never decides on an incomplete 1-minute bar. This avoids lookahead
but means the entry alert is always one step after the signal bar. A setup on
the 09:31 bar is entered at the first tradable tick/open of the 09:32 bar.

For replay, the same rule is simulated with bars:

```text
previous replay bar -> treated as the just-completed signal bar
current replay bar open -> used as the entry tick/open
```

This is why replay is useful for validating timing. It does not simply scan a
CSV and alert on the same row; it uses the next row's open as the tradable entry
moment.

## Files

- `databento_signal_engine.py`: main engine, Databento ingestion, replay, live
  loop, strategy runtime, alert building, and CLI.
- `strategy_execution_bridge.py`: compatibility wrapper that launches the new
  engine.
- `signal_engine.example.yaml`: example production-style config using a
  campaign YAML from `configs/campaigns`.
- `dummy_delta_signal_engine.example.yaml`: simple built-in strategy for
  verifying the live/replay path.
- `data/databento/`: default location for generated historical bar caches.
- `data/alerts/`: default location for emitted JSONL alerts.

## Runtime Flow

The engine has five phases: boot, data planning, warmup, event processing, and
alert emission.

1. `run()` loads the YAML config, applies CLI overrides, builds a `SignalEngine`,
   and prints a preflight JSON object.
2. `SignalEngine` loads each enabled strategy, infers required data columns and
   warmup depth, validates the Databento schema, and reports the resulting
   `data_plan`.
3. Unless `--skip-historical` is set, the engine loads historical 1-minute bars
   from cache or fetches Databento historical ticks and builds a cache.
4. Historical bars are inserted into `BarStore`, and each strategy is hydrated so
   rolling state, feature windows, same-clock ranks, and daily trade counters
   start from realistic context.
5. In replay mode, cached bars are fed through the same completed-bar path used
   by live mode.
6. In live mode, Databento records are normalized into `TradeTick` objects,
   accumulated into completed `SourceMinuteBar` objects, and pushed into the
   store.
7. Every new completed source bar triggers strategy evaluation against the full
   rolling feature frame.
8. If a strategy returns a signal, the engine creates a `PendingSignal` due at
   the next strategy-bar open.
9. On that entry tick/open, the engine computes entry, stop, target, sizing,
   validates the alert contract, prints `ENTRY_SIGNAL`, and appends JSONL to the
   configured alerts file.

The engine intentionally evaluates strategies only on completed bars. The
entry alert is emitted on the next tick/open, not inside the still-forming bar
that produced the setup.

The live and replay paths converge before strategy evaluation. Replay therefore
tests timing, setup queuing, entry math, stop/target math, sizing, alert
validation, and JSONL output without using Databento live.

## Main Components

`TradeTick` is the normalized live tick. It contains timestamp, price, size,
Databento side, contract symbol, action, and optional top-of-book bid/ask
prices when the subscribed schema provides them.

`SourceMinuteBar` is the normalized 1-minute bar the rest of the engine uses.
Its timestamp is the bar open in UTC. It stores OHLCV, selected `signed_volume`,
derived buy/sell volume, trade count, contract symbol, source label, and extra
diagnostic fields such as quote delta and tick-rule delta.

`MinuteAccumulator` turns ticks for one contract and one UTC minute into OHLCV
orderflow bars. It computes `signed_volume`, `buy_volume`, `sell_volume`,
trade count, large-trade fields, and diagnostic delta fields.

`TradeBarBuilder` owns active minute accumulators across contracts. When a new
tick arrives in a later minute, it flushes completed bars. If multiple ES
contracts produce bars for the same minute, `active_contract_mode` decides
which bars to emit:

- `highest_session_volume`: default; selects the contract with the highest
  cumulative session volume.
- `highest_minute_volume`: selects the highest-volume contract in that minute.
- `emit_all`: emits all completed contract bars.

The same policy is applied again before strategy feature construction. This
matters for cached or replayed parent-symbol data, where multiple contracts may
already be present in the file. Non-active contract rows are filtered out before
`build_features()` runs and are reported as `SYSTEM_ALERT
non_active_contract_bars_filtered`; strategy health includes
`non_active_contract_filter_drops` and `last_contract_filter_report`.

`BarStore` keeps the latest source bars in memory. `engine.max_source_bars`
controls retention. The store is the only input to feature building, so live,
historical, and replay bars all go through the same in-memory shape.

`StrategyRuntime` wraps either a campaign YAML strategy or a built-in strategy.
For campaign strategies it loads the YAML, validates the `strategy.entry`,
`strategy.sl`, and `strategy.tp` modules, resolves project-relative file paths,
and builds the same `propstack.strategy.ModularStrategy` used in backtests.

`PendingSignal` is a setup that has fired but is not actionable yet. It stores
the strategy, completed feature row, raw signal object, due timestamp, and a
dedupe key. Pending signals are removed after a valid alert is emitted or after
they expire beyond `engine.max_entry_lag_seconds`.

`SignalEngine` owns the bar store, strategies, pending entries, sizing account
settings, operator notifications, live health state, and alert emission.

`LiveHealth` tracks whether live data is actually moving: total Databento
records, parsed trade ticks, completed bars, dropped partial first bars, stale
feed timing, and connection state. It powers `live_status` and `SYSTEM_ALERT`
watchdog messages.

`DataRequirement` is an inferred summary of what selected strategies need:
source columns, feature families, large-trade thresholds, maximum feature
window, minimum warmup sessions, and recommended source-bar count. These reports
are merged into the preflight `data_plan`.

## Source Bar Semantics

The source bar is always a 1-minute bar, even when a strategy runs on a higher
timeframe. Higher timeframe bars are built later by
`propstack.data.timeframe.aggregate_timeframe()`.

Important source fields:

- `timestamp_utc`: UTC open timestamp of the 1-minute bar.
- `timestamp`: same bar open converted to the configured market timezone when
  the bar is converted to a dataframe.
- `symbol`: root symbol, normally `ES`.
- `contract_symbol`: the actual contract used for the bar, for example `ESM6`.
- `open`, `high`, `low`, `close`, `volume`: standard OHLCV from trade prints.
- `signed_volume`: the selected delta according to `databento.delta_method`.
- `buy_volume`, `sell_volume`: buy/sell volume according to the selected delta
  method.
- `trades`: parsed trade-print count.
- `large*_signed_volume`, `large*_volume`: optional large-trade fields when
  `databento.large_trade_sizes` is configured.
- diagnostic delta fields: extra classifications used for feed comparison and
  debugging, not necessarily the fields the strategy uses.

`signed_volume` is the selected delta field. It is not a separate Databento
field. The engine computes it from each trade according to
`databento.delta_method`, then sums it into the completed minute bar.

With the default `delta_method: aggressor_side`:

```text
Databento side B -> +trade size
Databento side A -> -trade size
unknown side      -> 0
```

With `delta_method: tick_rule`, a trade is signed by whether price moved up or
down versus the previous trade price. With `delta_method: price_vs_quote`, a
trade at/above best ask is signed positive and a trade at/below best bid is
signed negative. Quote-based delta requires live `schema: mbp-1` because the
plain `trades` schema does not include top-of-book bid/ask prices.

The engine treats a minute as complete only after it is safe to do so. A
later-minute tick flushes the prior minute immediately. In live mode, the
heartbeat can also flush a minute after wall clock has passed
`minute_end + databento.live.bar_flush_delay_seconds`. This prevents quiet
periods from delaying setup alerts indefinitely.

Once a minute has been flushed, later trade prints for the same
contract/minute are ignored to avoid duplicate or revised source bars. The
engine reports this as `SYSTEM_ALERT live_late_trade_tick_ignored` and includes
`late_trade_ticks_ignored` plus `last_late_trade_tick` in `live_status`. If you
see repeated late ticks, increase `bar_flush_delay_seconds` or investigate feed
timestamp/order behavior.

The default live setting also drops the first completed bar after subscription,
because starting the script at 09:31:35 would otherwise create a partial 09:31
bar.

The engine does not currently backfill the missing first part of the live
subscription minute. If the process starts at 09:31:35, Databento live only
delivers records from that point forward. The safe behavior is to drop that
partial bar and begin evaluating from the next full minute. Historical seeding
warms up strategy state before live starts, but it is not merged into the
currently forming live minute.

## Dummy Delta Metadata

The dummy strategy writes several delta values into `signal.metadata` so a live
or replay alert can be inspected quickly.

- `current_bar_delta`: selected delta for the latest completed bar.
- `delta`: the value the dummy strategy actually used to choose direction.
- `delta_mode`: whether `delta` came from only the latest bar or from a window.
- `delta_window_bars`: number of bars in that window.
- `latest_completed_bar_signed_volume`: the same selected bar delta stored on
  the source bar.
- `latest_completed_bar_databento_aggressor_delta`: Databento side-based
  diagnostic delta.
- `latest_completed_bar_quote_delta`: quote-classified diagnostic delta when
  bid/ask data exists.
- `latest_completed_bar_tick_rule_delta`: tick-rule diagnostic delta.

For the included dummy config, `delta_mode: current_bar`, so `delta`,
`current_bar_delta`, and `latest_completed_bar_signed_volume` should match for
that alert. If you change the dummy config to `delta_mode: window_sum`, then
`current_bar_delta` remains the latest bar's delta while `delta` becomes the sum
of the last `delta_window_bars` selected deltas.

## Source-Bar Quality

The engine validates historical, replay, and live source bars before they enter
`BarStore`. Invalid source bars are not allowed to update strategy state or
produce trade signals.

Quality behavior is controlled by `engine.data_quality`:

```yaml
engine:
  data_quality:
    enabled: true
    fail_on_error: false
    allow_zero_volume: false
    warn_on_time_gaps: true
    max_bar_gap_minutes: 5
    max_reported_issues: 10
```

The quality gate treats these as errors and drops the affected bar:

- missing or invalid timestamp, symbol, or contract symbol
- non-finite or non-positive OHLC prices
- `high < low`, `high` below open/close, or `low` above open/close
- negative volume, negative buy/sell volume, or negative trade count
- zero-volume bars when `allow_zero_volume` is false
- absolute `signed_volume` greater than total `volume`
- `buy_volume + sell_volume` greater than total `volume`
- duplicate timestamp/contract bars in the same input batch

These are warnings by default and do not drop the bar:

- positive volume with zero trade count
- `signed_volume` not reconciling to `buy_volume - sell_volume`
- a same-session gap larger than `max_bar_gap_minutes`

When issues are found, the engine prints `SYSTEM_ALERT
source_bar_quality_issues` with counts, dropped-bar totals, and the first
`max_reported_issues` issue records. If `fail_on_error` is true, any quality
error raises a fatal runtime error after the alert is printed.

Before those checks run, cached, replay, and historical source bars are also
filtered by `databento.contract_symbol_regex`. Rejected source bars are not
added to the store, cannot produce setup or entry signals, and are surfaced as
`SYSTEM_ALERT source_bar_contract_symbol_filtered`. The same regex is applied
to live trade ticks before live aggregation.

For freshly fetched Databento historical trades, the engine also verifies that
the returned symbol column can match `databento.contract_symbol_regex` before
calling the 1-minute aggregator. If nothing matches, historical aggregation
fails closed with `SYSTEM_ALERT historical_symbol_regex_unmatched`. Set
`databento.historical.allow_contract_symbol_regex_relaxation: true` only for a
controlled diagnostic run where using every returned symbol is intentional.

## Strategy Runtime Errors

Strategy and feature-building errors are handled by `engine.strategy_errors`:

```yaml
engine:
  strategy_errors:
    fail_fast: false
    disable_strategy_on_error: true
    max_errors_per_strategy: 1
    fail_when_all_strategies_disabled: true
```

If a strategy raises while hydrating, processing a completed bar, or building an
entry alert, the engine prints `SYSTEM_ALERT strategy_runtime_error` with the
strategy id, phase, error type, message, error count, and disabled state.

Default behavior disables a strategy after its first runtime error. This lets a
multi-strategy engine keep running with the remaining healthy strategies. If all
strategies become disabled, the engine prints `SYSTEM_ALERT
all_strategies_disabled` and exits by default. Set
`fail_when_all_strategies_disabled: false` only when you explicitly want the
process to stay alive without active strategies.

Live `live_status` includes `active_strategy_count`, `disabled_strategy_count`,
and `strategy_health` so a supervising process can detect degraded operation.

## Strategy Contract

A strategy must provide three things by the time `StrategyRuntime` is built:

- an entry module with `on_bar_close(row, trades_today=...)`
- a stop-loss module with `stop_price(signal, direction, tick_size, entry_price)`
- a take-profit module with `target_price(entry_price, stop_price, direction,
  signal=...)`

Campaign YAML strategies already define these under `strategy.entry`,
`strategy.sl`, and `strategy.tp`. The engine wraps them with
`propstack.strategy.ModularStrategy`, which is the same strategy wrapper used by
the backtester.

Built-in strategies are defined entirely inside the execution config. The dummy
delta strategy is implemented by `DeltaIntervalStrategy` and exists to verify
live/replay plumbing without depending on campaign feature complexity.

When a strategy returns a signal, the signal must include a usable `direction`.
The engine does not place an alert immediately. It creates a `PendingSignal`
whose due timestamp is:

```text
completed strategy bar open + strategy timeframe
```

That delay is what keeps the engine from entering on information that was not
available until the bar closed.

By default, the pending setup is contract-specific. If a completed `ESM6` bar
creates a setup, only an `ESM6` tick can trigger its `ENTRY_SIGNAL`; an `ESU6`
tick or a spread tick is skipped and reported through
`SYSTEM_ALERT entry_tick_contract_mismatch_skipped`. This prevents parent
subscriptions from turning a valid setup in one contract into an entry in
another. `live_status.pending_status` includes mismatch counters and the last
mismatch while the setup remains pending.

Before `on_bar_close()` is called, `feature_quality` checks the runtime feature
row. Missing required columns fail fast by default, while non-finite required
feature values, such as rank/window columns that are still warming up, are
skipped with `SYSTEM_ALERT strategy_feature_row_not_ready`. The strategy remains
active, but that incomplete bar cannot produce a setup.

Strategy rows are tracked by `(timestamp, contract_symbol)`, not timestamp
alone. This matters during roll or parent-symbol subscriptions: `ESM6` and
`ESU6` rows for the same minute are evaluated independently, while repeated
delivery of the same timestamp/contract row is skipped and counted in strategy
health as `duplicate_strategy_row_skips`.

When `databento.active_contract_mode` is not `emit_all`, the strategy source
frame is first narrowed to one active contract per timestamp. This prevents
cached/replay parent data from creating two setups for the same minute during
roll. Use `emit_all` only when every contract in the feed is intentionally
tradable as a separate signal stream.

## Config Structure

Every engine config has four main sections.

`project_root` points from `execution_system` back to the repo root. The example
uses `..`.

`engine` controls local runtime behavior:

- `symbol`: root symbol, normally `ES`.
- `timezone`: market timezone, normally `America/New_York`.
- `max_source_bars`: in-memory source-bar retention.
- `count_historical_signals`: when true, historical warmup signals count
  against each strategy's daily trade counters.
- `max_entry_lag_seconds`: reject a queued signal if the next entry tick arrives
  too late.
- `entry_contract_match_required`: when true, a queued setup can only become an
  entry signal on a tick for the same `contract_symbol` as the completed setup
  bar. Keep this true for parent subscriptions such as `ES.FUT`.
- `entry_contract_mismatch_alert_repeat_seconds`: throttle for
  `SYSTEM_ALERT entry_tick_contract_mismatch_skipped`.
- `replay_seed_bars`: number of replay bars used only for warmup before replay
  starts emitting live-style signals.
- `alert_prefix`: prefix printed before actionable alerts.
- `process_lock`: optional single-process runtime lock.
- `alerts_path`: JSONL output path.
- `alert_file`: JSONL write durability and fail-fast behavior.
- `setup_alerts`: optional durable JSONL outbox for preparation-only setup
  notices.
- `execution_intents`: optional router-facing JSONL outbox.
- `data_quality`: source-bar sanity checks before strategy evaluation.
- `feature_quality`: strategy feature-row readiness checks before
  `on_bar_close`.
- `strategy_errors`: strategy runtime fault isolation and fail-fast behavior.
- `operator`: human-readable setup/entry readouts and optional sound alerts.
- `account`: net liquidity, sizing clamps, and default slippage assumptions.

Important `engine.feature_quality` keys:

- `enabled`: when true, required runtime feature columns are checked before a
  strategy sees a completed bar.
- `fail_on_missing_columns`: when true, missing required columns raise a
  strategy runtime error instead of silently skipping.
- `alert_repeat_seconds`: throttle for repeated
  `strategy_feature_row_not_ready` alerts from the same strategy.
- `max_reported_columns`: cap how many missing or non-finite column names are
  printed in one alert.

`databento` controls historical and live market data:

- `api_key_env`: environment variable containing the Databento key.
- `dataset`: default `GLBX.MDP3`.
- `schema`: default `trades`.
- `symbols`: default `ES.FUT`; can be overridden with a raw contract such as
  `ESM6`.
- `stype_in`: symbol type sent to Databento.
- `stype_out`: historical output symbol type. The examples use `instrument_id`
  because Databento rejects `parent -> raw_symbol` for `GLBX.MDP3`.
- `root_symbol`, `timezone`, `rth_start`, `rth_end`: symbol/session settings.
- `contract_symbol_regex`: filters returned contracts during historical seed
  building, cached/replay source-bar ingestion, and live tick aggregation. For
  ES parent subscriptions the default examples use `^ES[HMUZ]\d$` to accept
  outrights and reject spreads or unrelated symbols.
- `large_trade_sizes`: thresholds for extra large-trade signed-volume fields.
- `active_contract_mode`: active-contract selection for live aggregation and
  cached/replay strategy feature input. Defaults to `highest_session_volume`.
- `delta_method`: how live ticks become `signed_volume`.
- `historical`: historical seed behavior.
- `live`: streaming behavior.

Important `databento.historical` keys:

- `enabled`: load, cache, or fetch a historical warmup seed before replay/live.
- `allow_contract_symbol_regex_relaxation`: defaults to false. When false, a
  Databento historical fetch stops if no returned symbol matches
  `databento.contract_symbol_regex`. When true, the engine prints
  `SYSTEM_ALERT historical_symbol_regex_relaxed` and aggregates all returned
  symbols. Keep this false for production.
- `cache_path`, `cache_metadata`, `lookback_days`, `max_seed_bars`: cache and
  warmup controls.
- `cost_guard`: estimates Databento historical cost before any download.

Important `databento.live` keys:

- `metadata_preflight`: run metadata/schema/symbology/cost checks before live
  subscription.
- `symbology_stype_out`: output symbol type used by the metadata-only
  symbology check, usually `instrument_id`.
- `resolve_instrument_symbols`: build a metadata-only `instrument_id` to raw
  contract map before live starts. Keep this enabled when subscribing with
  `symbols: ES.FUT` and `stype_in: parent`.
- `fail_without_live_symbol_map`: stop live startup if that map cannot be built.
  This avoids silently rejecting all live records whose only contract identity
  is an `instrument_id`.
- `subscribe_resolved_raw_symbols`: after resolving parent symbology, subscribe
  to matching raw outright contracts instead of the broad parent symbol. This
  avoids consuming spread ticks that would be rejected by
  `contract_symbol_regex`.
- `startup_grace_seconds`: short fail-fast window after `Live.start()` for the
  client to still report connected before the engine exits.
- `shutdown_grace_seconds`: bounded wait after `client.stop()` for the live
  client to close before the engine prints its stop summary.
- `maintenance_interval_seconds`: cadence for internal live maintenance such as
  wall-clock bar finalization and stale pending-signal expiry.
- `status_interval_seconds`: cadence for printed `live_status` health reports.
- `stop_on_unmatched_contract_symbol`: stop live mode after the first trade tick
  rejected by `contract_symbol_regex`; defaults to false so the engine alerts
  and keeps running.
- `flush_completed_bars_on_heartbeat`: finalize live bars by wall clock when a
  later-minute tick has not arrived.
- `bar_flush_delay_seconds`: conservative delay after minute end before a
  wall-clock flush is allowed.

`strategies` is a list of selected strategies. A campaign strategy points at a
YAML under `configs/campaigns`. A built-in dummy strategy uses `type:
builtin_delta_interval` and defines params directly in the execution config.

Campaign strategy entry:

```yaml
strategies:
  - id: dense_rank_value_priority_ensemble_full_sierra
    enabled: true
    config: configs/campaigns/bar_orderflow_participation_state/variants/ES/1m/dense_rank_value_priority_ensemble_full_sierra.yaml
```

Built-in dummy strategy entry:

```yaml
strategies:
  - id: dummy_delta_every_5m_1r
    type: builtin_delta_interval
    enabled: true
    symbol: ES
    timeframe: 1m
    params:
      interval_bars: 5
      delta_mode: current_bar
      delta_column: signed_volume
      stop_mode: bar_extreme
      target_r_multiple: 1.0
```

For campaign strategies, the execution config selects the strategy but the
entry, stop, target, feature, timeframe, and sizing definitions come from the
campaign YAML. For built-in strategies, those definitions are synthesized into
a campaign-like shape by the engine.

CLI overrides are applied after the YAML is loaded. For example,
`--strategy-config path/to/variant.yaml` replaces the configured strategy list,
and `--databento-symbols ESM6 --databento-stype-in raw_symbol` overrides the
Databento subscription without editing the config file.

## Strategy Evaluation

For every completed source bar, the runtime builds the feature frame like this:

1. `BarStore.to_dataframe()` converts in-memory bars to a pandas frame.
2. `propstack.data.sessions.assign_sessions()` assigns RTH/ETH session fields.
3. `propstack.data.sessions.filter_trading_sessions()` removes bars outside the
   configured trading sessions.
4. `propstack.data.timeframe.aggregate_timeframe()` converts source 1-minute
   bars to the strategy timeframe.
5. `propstack.data.features.build_features()` creates the same feature columns
   used by backtests.
6. Each new completed strategy row is passed to `strategy.on_bar_close()`.

If a strategy returns no signal, nothing is printed. If it returns a signal,
the engine creates a `PendingSignal`. The pending signal is due at:

```text
signal bar timestamp + strategy timeframe
```

For a 1-minute strategy, a signal on the 09:31:00 bar is actionable at the
first tradable tick at or after 09:32:00.

## Alert Construction

When a pending signal reaches its next tick/open, `StrategyRuntime.build_alert()`
does the final trade math:

1. Determines side from signal direction.
2. Estimates market entry from the next tick price plus configured slippage.
3. Asks the strategy for stop price.
4. Asks the strategy for target price.
5. Rounds entry, basis, stop, and target to the configured tick grid.
6. Rejects the signal if rounded stop/target are missing, non-finite,
   non-positive, collapsed by tick rounding, or on the wrong side of entry.
7. Sizes the position with `propstack.backtest.sizing.size_position()` using
   the executable rounded stop distance.
8. Applies account-level `min_contracts` and `max_contracts`.
9. Prints and appends the final `ENTRY_SIGNAL`.

Sizing rules are preflighted when each strategy loads. `core.position_sizing`
may be a fixed-contract rule or one of the existing risk-percent modes used by
the backtester. Unsupported modes, non-positive contracts, invalid risk
fractions, invalid rounding modes, or missing `core.initial_balance` for
risk-percent sizing stop the engine before live data is consumed. At alert time,
the final quantity is still computed from the executable rounded stop distance
and the current `engine.account.net_liq`.

Signals that cannot produce a valid trade are printed as `SIGNAL_REJECTED`.

Important rejection cases:

- signal direction is missing or is not `long`/`short`
- stop or target is missing, non-finite, or non-positive
- stop and target are not on opposite sides of the estimated entry
- tick rounding collapses the stop or target distance to zero
- sizing returns fewer contracts than `engine.account.min_contracts`
- the next entry tick arrives later than `engine.max_entry_lag_seconds`
- no entry tick arrives before the pending entry expires

Rejections are normal guardrail behavior for alert quality. A rejected setup is
not appended to the alerts JSONL file and does not increment `entry_alerts`.

The displayed `entry_price`, `entry_basis_price`, `stop_loss_price`, and
`take_profit_price` are executable tick-grid prices. If a strategy produces an
off-grid raw stop or target, the engine rounds it to `tick_size`, recalculates
points/risk/reward from the rounded prices, and includes a `price_normalization`
audit block with raw prices and adjustment ticks.

## Operator Alerts

The engine emits three operator-facing notices:

- `TRADE_SETUP`: printed when a completed bar produced a valid strategy setup
  and the engine is waiting for the next tradable tick/open.
- `ENTRY_SIGNAL`: printed when the next tick/open arrives and the trade is
  actionable now.
- `SIGNAL_REJECTED`: printed when a setup cannot become a valid trade because
  timing, direction, stop/target, tick rounding, or sizing failed validation.

Machine-readable JSON is always printed first. When
`engine.operator.print_human_readable: true`, the engine also prints a compact
manual-entry block with symbol, direction, quantity, entry, stop, target, risk,
reward, timestamps, and useful signal metadata.

`print_setup_readable` and `print_rejection_readable` control the compact setup
and rejection blocks separately. Rejection readouts include strategy, signal
timestamp, session, direction when known, due/checked timestamps when relevant,
and the rejection reason.

Sound is controlled by `engine.operator.sound`:

```yaml
engine:
  operator:
    print_human_readable: true
    print_setup_readable: true
    print_rejection_readable: true
    sound:
      enabled: true
      bell: true
      on_setup: true
      on_entry: true
      on_system: true
      cleanup_on_exit: true
      command: null
```

`bell: true` writes the terminal bell character. `command` can be set to an
external player command, for example `afplay /path/to/sound.wav` on macOS. The
engine starts the command without blocking the data loop. Sound failures are
reported as `SYSTEM_ALERT` and do not stop the engine.
`cleanup_on_exit: true` terminates any still-running sound command when the
engine exits, which prevents a broken or long-running player process from
surviving a stopped signal engine. `preflight`, `live_status`, and
`live_stopped` include `operator_sound` health: attempts, bell writes, commands
started, failures, active command processes, cleanup counts, and the last error.

## Alert File Health

`TRADE_SETUP` is always printed to stdout first. When `engine.setup_alerts` is
enabled, the same setup notice is appended to a JSONL file. A setup notice has
`setup_contract_version`, `setup_id`, strategy/symbol/contract/timing fields,
direction, side, a stop preview when available, and signal metadata. It does not
include an entry price, quantity, bracket, or `execution_intent`; those only
exist after a same-contract entry tick arrives and an `ENTRY_SIGNAL` is valid.

Setup file behavior is controlled by:

```yaml
engine:
  setup_alerts:
    enabled: true
    path: data/alerts/trade_setups.jsonl
    fsync: false
    fail_on_write_error: false
    suppress_duplicate_setup_ids: true
```

If the setup append fails, the engine prints `SYSTEM_ALERT
setup_alert_write_failed`. Live `live_status` includes
`setup_alert_writes_succeeded`, `setup_alert_writes_failed`,
`setup_alert_duplicates_skipped`, `setup_alert_last_duplicate_setup_id`, and
last-error fields.

`ENTRY_SIGNAL` is always printed to stdout first. When `engine.alerts_path` is
configured, the same alert is also appended to a JSONL file for auditing and
future automation consumers.

Alert file behavior is controlled by `engine.alert_file`:

- `fsync`: flush and fsync every alert write before reporting success. This is
  slower but improves durability if the machine crashes immediately after an
  alert.
- `fail_on_write_error`: raise a fatal runtime error after printing a
  `SYSTEM_ALERT` if the JSONL append fails. The default is false so manual
  trading alerts keep running even if the local file path is broken.
- `suppress_duplicate_alert_ids`: load existing JSONL `alert_id`s at startup
  and skip appending a duplicate id. The `ENTRY_SIGNAL` is still printed to
  stdout, but the file is not appended again.

If the file append fails, the engine prints `SYSTEM_ALERT
alert_file_write_failed` with the path, alert id, error type, error message, and
write counters. The actionable `ENTRY_SIGNAL` has already been printed to
stdout, but file-based automation may have missed it. Live `live_status` also
includes:

- `alert_file_writes_succeeded`
- `alert_file_writes_failed`
- `alert_file_duplicates_skipped`
- `alert_file_last_success_utc`
- `alert_file_last_duplicate_utc`
- `alert_file_last_duplicate_alert_id`
- `alert_file_last_error_utc`
- `alert_file_last_error_type`
- `alert_file_last_error`

## Runtime Lock

The example configs enable a single-process runtime lock:

```yaml
engine:
  process_lock:
    enabled: true
    path: data/runtime/signal_engine.lock
    stale_after_seconds: 86400
    fail_if_locked: true
```

The lock is acquired only for mutating/running modes such as historical seed,
replay, and live streaming. `--preflight-only` and `--check-databento-metadata`
do not acquire it, so they can be used while another engine is live.

The lock prevents two engine processes from writing the same alert/outbox paths
or subscribing with the same runtime config. If an active lock is found, the
engine prints `SYSTEM_ALERT process_lock_already_held` and exits when
`fail_if_locked` is true. If the lock belongs to a dead process, it prints
`SYSTEM_ALERT stale_process_lock_replaced`, replaces the lock, and continues.
On clean exit the engine prints `process_lock_released` and removes the lock
file.

## Execution Intent Outbox

`ENTRY_SIGNAL` contains a nested `execution_intent`, but the engine can also
write a separate router-facing JSONL record for future automation:

```yaml
engine:
  execution_intents:
    enabled: true
    path: data/alerts/execution_intents.jsonl
    fsync: false
    fail_on_write_error: false
    suppress_duplicate_alert_ids: true
```

Each line in this file is an `execution_intent_ready` record. It contains the
alert id, strategy id, symbol, contract, timeframe, entry timestamp, and the
validated nested `execution_intent`. This gives a future order router a narrow
consumer contract without requiring it to parse the full human/audit alert log.

`suppress_duplicate_alert_ids: true` is important for router safety. `alert_id`
is deterministic for a strategy signal and entry tick/open. On restart or
replay, the engine indexes existing JSONL records and skips appending the same
id again, printing `SYSTEM_ALERT execution_intents_duplicate_alert_id_skipped`.
This prevents a future router from seeing the same intent as a new order. The
process is still a single-writer design; do not run multiple engine processes
against the same outbox path.

Intent outbox writes happen after the `ENTRY_SIGNAL` is printed and after the
alert JSONL append is attempted. If the outbox append fails, the engine prints
`SYSTEM_ALERT execution_intent_write_failed`. The manual trade instruction was
already printed, but file-based automation may have missed the router payload.
Set `fail_on_write_error: true` when a missing automation outbox should stop the
process instead of continuing in manual-alert mode.

Live `live_status` reports separate outbox health fields:

- `execution_intent_writes_succeeded`
- `execution_intent_writes_failed`
- `execution_intent_duplicates_skipped`
- `execution_intent_last_success_utc`
- `execution_intent_last_duplicate_utc`
- `execution_intent_last_duplicate_alert_id`
- `execution_intent_last_error_utc`
- `execution_intent_last_error_type`
- `execution_intent_last_error`

## Historical Seed

Historical seed data gives strategies enough context before live ticks arrive.
Set a Databento key, then run:

```bash
export DATABENTO_API_KEY="..."

python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --seed-only
```

Default cache path:

```text
execution_system/data/databento/es_trade_orderflow_seed_1m.csv
```

Historical loading order:

1. If `historical.cache_path` exists and refresh is false, load it.
2. Else if `historical.seed_bars_path` is configured, load that file.
3. Else fetch Databento historical ticks, aggregate to 1-minute bars, and write
   the cache.

When the engine writes a historical cache, it also writes a sidecar metadata
file next to it:

```text
data/databento/es_trade_orderflow_seed_1m.csv.metadata.json
```

The metadata records the Databento dataset/schema/symbol settings, session
settings, large-trade thresholds, selected `delta_method`, and a bar summary.
When a cache is reused, the engine validates that sidecar against the current
config before accepting the bars. Missing, unreadable, or mismatched metadata
prints a `SYSTEM_ALERT` because the cache may have been generated under
different assumptions.

Control this with:

```yaml
historical:
  cache_metadata:
    enabled: true
    fail_on_mismatch: false
```

Set `fail_on_mismatch: true` when stale or unproven historical caches should
stop the engine until the cache is refreshed.

The amount of historical data is intentional and config-driven. The engine is
not trying to download "today only"; it is trying to load enough completed
1-minute source bars for strategy warmup. The main controls are:

- `historical.lookback_days`: requested calendar lookback when explicit
  start/end values are not configured.
- `historical.max_seed_bars`: maximum number of completed source bars kept
  after fetch/cache load.
- `engine.max_source_bars`: maximum number of bars retained in memory.
- `engine.replay_seed_bars`: how many replay bars are used for warmup before
  replay starts emitting live-style signals.
- inferred strategy warmup: printed in preflight under `data_plan.warmup`.

For campaign strategies with same-clock ranks and long feature windows, the
preflight can recommend many sessions of source bars. A cache that spans several
trading days is therefore expected. If you want a smaller smoke-test dataset,
use the dummy config or lower `historical.max_seed_bars` in a temporary config.

Useful historical options:

- `historical.enabled`: disable all historical loading when false.
- `historical.lookback_days`: how far back to request when start/end are not
  explicit.
- `historical.max_seed_bars`: cap bars kept after fetching.
- `historical.clamp_end_to_available`: asks Databento for available dataset
  range and clamps the request end to avoid `data_end_after_available_end`.
- `historical.refresh`: ignore existing cache and fetch again.
- `historical.cache_metadata`: validate the cache sidecar before reusing cached
  seed bars.
- `historical.cost_guard`: estimates Databento historical cost before fetching.

Use `--refresh-historical` to force a fresh fetch from the CLI.

Historical fetches are guarded by default:

```yaml
historical:
  cost_guard:
    enabled: true
    allow_paid_downloads: false
    max_cost_usd: 0.0
    fail_if_estimate_unavailable: true
```

Before calling the paid `timeseries.get_range()` endpoint, the engine calls
Databento metadata `get_cost()` and `get_billable_size()`. If estimated cost is
above `max_cost_usd`, if cost is positive while `allow_paid_downloads` is false,
or if the estimate cannot be retrieved and `fail_if_estimate_unavailable` is
true, the engine prints `SYSTEM_ALERT`/`FATAL` and exits before downloading.

## Replay

Replay is the fastest way to test strategy timing without live data:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --skip-historical \
  --replay-bars execution_system/data/databento/es_trade_orderflow_seed_1m.csv \
  --replay-stop-after-signal
```

Replay behavior:

1. Reads the supplied bar file.
2. Seeds the first `engine.replay_seed_bars` bars.
3. Feeds each next bar as if it just completed live.
4. Uses the following bar's open as the entry tick.

This mirrors live timing closely: the signal is evaluated on a completed bar,
and the alert is emitted at the next bar open.

## Live

Enable live streaming with either `databento.live.enabled: true` or `--live`:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --live
```

Live mode stays attached until Ctrl-C, `--once`, `--max-runtime`, or a Databento
stream error. It runs internal maintenance every
`databento.live.maintenance_interval_seconds`, prints `live_status` every
`databento.live.status_interval_seconds` seconds, and prints `ENTRY_SIGNAL`
whenever a configured strategy produces an actionable entry.

If the process prints `live_subscribe` and then exits immediately, the Databento
live client returned or raised. A healthy live run continues to print
`live_status` heartbeats until you stop it. During active market periods,
`records_received`, `trade_ticks_received`, and `completed_source_bars` should
increase over time. Outside the configured stale-alert session, stale-data
warnings can be suppressed, but the status objects still show whether the feed
is connected and moving.

Live record handling:

1. The Databento callback receives raw live records.
2. `live_record_to_tick()` ignores records that are not trade prints and
   converts trade records into `TradeTick`.
3. When `subscribe_resolved_raw_symbols` is enabled, the engine resolves
   `ES.FUT` before live start and subscribes to raw symbols that match
   `contract_symbol_regex`, such as `ESM6` and `ESU6`, rather than consuming
   spread symbols and filtering them afterward.
4. If Databento only gives the record's `instrument_id`, the live metadata
   symbol map converts it to the raw contract symbol, such as `ESM6`.
5. `TradeBarBuilder.update()` applies `databento.contract_symbol_regex` before
   aggregation. Rejected symbols are reported as
   `SYSTEM_ALERT live_unmatched_contract_symbol_ignored`; they are not source
   bars and are not used as pending-entry triggers.
6. Accepted ticks are added to the current minute accumulator for their
   contract.
7. When a later-minute tick arrives, older accumulators are flushed into
   completed `SourceMinuteBar` objects.
8. The live maintenance heartbeat also calls
   `TradeBarBuilder.flush_completed_bars()` for minutes that are safely behind
   wall clock.
9. The engine evaluates strategies on completed bars, then separately checks
   the current tick as a possible same-contract entry tick for pending setups.

Heartbeat flushing is controlled by:

```yaml
databento:
  live:
    metadata_preflight: true
    symbology_stype_out: instrument_id
    startup_grace_seconds: 3
    shutdown_grace_seconds: 3
    maintenance_interval_seconds: 1
    flush_completed_bars_on_heartbeat: true
    bar_flush_delay_seconds: 2
    status_interval_seconds: 60
    stop_on_unmatched_contract_symbol: false
```

With this enabled, a 09:31:00 bar can be finalized by heartbeat shortly after
09:32:02 even if the next trade tick has not arrived, independent of the slower
status-print interval. If a late 09:31 trade arrives after that, it is ignored
and surfaced as a system alert so the engine does not emit duplicate or revised
bars.

The watchdog alerts if records, trade ticks, or completed bars stop moving
beyond configured thresholds.

Before opening the live stream, `metadata_preflight: true` runs the same
metadata-only checks available through `--check-databento-metadata`. It verifies
the configured dataset, schema list, DBN fields, symbology resolution for
`databento.symbols` and `databento.stype_in`, and the historical cost guard.
It prints `live_metadata_preflight_ok` before `live_subscribe`. The report
explicitly includes `timeseries_download_attempted: false` and
`live_subscription_attempted: false`; if the check fails, the engine exits
before subscribing.

After `Live.start()`, the engine waits up to `startup_grace_seconds` for the
Databento client to still report connected. If the client is disconnected at
startup, it prints `SYSTEM_ALERT live_startup_disconnected`, stops the client,
and exits instead of silently continuing with no live feed.

On shutdown, live mode prints `live_stopped` with the stop reason, received
record/tick/bar counts, pending count, alert count, error count, and close-wait
diagnostics. It also includes the contract-symbol filter, accepted contract
counts, and unmatched contract counts, so short smoke tests that end before the
first `live_status` still show whether ticks were accepted or rejected. This
makes `--max-runtime`, Ctrl-C, callback errors, and disconnect stops
distinguishable in logs.

Live status includes connection state, uptime, received record/tick counts,
accepted trade tick count after contract filtering, completed-bar count,
heartbeat-flushed bar count, ignored late tick count, dropped partial bars,
pending signals, entry alerts, accepted contract counts, unmatched contract
counts, and seconds since the last record/tick/completed bar. It also reports
the latest trade tick's exchange event timestamp and the difference versus local
UTC wall clock. Positive clock lag means the event timestamp is older than local
time; negative lag means the event timestamp is in the future.

The watchdog emits `SYSTEM_ALERT` when the live feed appears stale or the tick
clock is suspicious:

- `no_records_alert_seconds`: no Databento records since live start.
- `no_trade_ticks_alert_seconds`: no parsed trade ticks inside the threshold.
- `no_completed_bar_alert_seconds`: trade ticks are arriving but no completed
  source bars have been emitted recently.
- `max_trade_tick_lag_seconds`: parsed trade ticks are arriving, but their
  `ts_event` timestamps are too old versus local UTC wall clock.
- `max_trade_tick_future_seconds`: parsed trade tick timestamps are ahead of
  local UTC wall clock, usually indicating local clock skew or bad timestamp
  handling.
- `live_unmatched_contract_symbol_ignored`: a parsed trade tick did not match
  `databento.contract_symbol_regex`; it was not aggregated or used for entry.
- `alert_repeat_seconds`: throttle repeated alerts for the same condition.
- `session_aware_stale_alerts`: suppress stale-data alerts outside the
  configured stale-alert session.
- `stale_alert_session_start`, `stale_alert_session_end`,
  `stale_alert_session_timezone`, `stale_alert_weekdays`: session window used
  for stale-data alert suppression.
- `stop_on_disconnect`: stop the script if the Databento client reports
  disconnected.
- `stop_on_unmatched_contract_symbol`: stop the script if an unexpected contract
  symbol is observed.

Disconnect alerts are never suppressed by session state. Only no-record,
no-trade-tick, and no-completed-bar alerts are suppressed outside the configured
session. `live_status` includes `market_session` with local time, session
window, `is_open`, and `suppress_stale_alerts`, so a supervisor can distinguish
expected market silence from feed failure.

Tick timestamp alerts are not suppressed by session state because they mean
records are arriving with questionable event times. `live_status` includes:

- `last_trade_tick_event_timestamp_utc`
- `last_trade_tick_clock_lag_seconds`
- `max_trade_tick_clock_lag_seconds`
- `max_trade_tick_clock_future_seconds`

The live maintenance loop also expires stale pending entries. If a setup is
waiting for an entry tick and no valid tick arrives within
`engine.max_entry_lag_seconds`, the engine prints `SIGNAL_REJECTED` and
`SYSTEM_ALERT pending_signals_expired`, then removes that pending setup.
`live_status.pending_status` reports the pending count, oldest due timestamp,
seconds until/after the oldest due time, and overdue count.

The default `databento.live.drop_partial_first_live_bar: true` drops the first
completed live minute. Without this, starting the script mid-minute can produce
a partial delta that will not match a full TradingView 1-minute delta bar.

For lower bandwidth, override the configured Databento symbol with the current
front contract:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --databento-symbols ESM6 \
  --databento-stype-in raw_symbol \
  --databento-stype-out raw_symbol \
  --live
```

## Delta Matching

`databento.delta_method` controls how live tick volume becomes `signed_volume`.
The selected `signed_volume` is what strategies see when they use the
`signed_volume` feature or the dummy strategy's `delta_column: signed_volume`.

Supported methods:

- `aggressor_side`: Databento trade side, where `B` is buy-aggressor volume and
  `A` is sell-aggressor volume. This is the default for `schema: trades`.
- `price_vs_quote`: classifies trades at/above the best ask as buy volume and
  at/below the best bid as sell volume. Use live `schema: mbp-1`; if a tick has
  no top-of-book prices, the engine falls back to `aggressor_side` and prints a
  warning once.
- `tick_rule`: classifies volume by trade price change versus the previous
  trade, carrying the last non-zero sign across unchanged prices.

Live bars also carry diagnostic fields:

- `databento_aggressor_delta`
- `quote_delta`
- `tick_rule_delta`
- `databento_buy_aggressor_volume`
- `databento_sell_aggressor_volume`
- `quote_buy_volume`
- `quote_sell_volume`
- `tick_rule_buy_volume`
- `tick_rule_sell_volume`

Dummy-strategy alerts copy these fields into `signal.metadata` as
`latest_completed_bar_*` fields. When comparing to TradingView/Rithmic, check:

- `latest_completed_bar_timestamp_utc`
- `contract_symbol`
- `latest_completed_bar_volume`
- `latest_completed_bar_databento_aggressor_delta`
- `latest_completed_bar_quote_delta`
- `latest_completed_bar_tick_rule_delta`

If volume does not match, you are not comparing the same bar, session, contract,
or feed scope. If volume matches but delta does not, the difference is the
classification method. Old cached CSV bars already have `signed_volume` baked
in; live `delta_method` does not reclassify those bars. Refresh or rebuild any
historical cache if you change how historical delta is generated.

TradingView/Rithmic delta can differ from this engine even when both are
showing ES 1-minute bars. Common causes:

- Different contract: front-month continuous symbol versus a raw contract such
  as `ESM6`.
- Different bar clock: exchange time, chart timezone, RTH/ETH filter, or
  seconds included at the boundary.
- Different feed scope: Databento CME MDP3 trades versus another vendor's
  normalized feed.
- Different classification: Databento aggressor side, bid/ask quote test,
  tick-rule, or a vendor-specific delta method.
- Partial live minute: the engine started after the minute began and dropped or
  partially accumulated the first bar.
- Cached historical bars: the CSV was generated with an older delta method.

The debugging order should be:

1. Match `latest_completed_bar_timestamp_utc`.
2. Match `contract_symbol`.
3. Match total `latest_completed_bar_volume`.
4. Compare the diagnostic delta fields in the alert metadata.
5. Only then decide whether to change `databento.delta_method` or regenerate
   historical caches.

If total volume does not match first, changing delta classification will not
make the values line up. The bars are not the same input data.

## Dummy Strategy Smoke Test

`dummy_delta_signal_engine.example.yaml` uses a built-in test strategy:

- first completed 1-minute bar, then every 5 bars after that
- the example config uses the current completed bar's `signed_volume`
- positive selected delta: long
- negative selected delta: short
- long stop: low of the latest completed bar
- short stop: high of the latest completed bar
- 1:1 take profit
- 1 contract, zero configured slippage

Run it against the cached seed file:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/dummy_delta_signal_engine.example.yaml \
  --skip-historical \
  --replay-bars execution_system/data/databento/es_trade_orderflow_seed_1m.csv \
  --replay-stop-after-signal
```

The first `ENTRY_SIGNAL` should have `strategy_id:
dummy_delta_every_5m_1r`. Check `signal.metadata.delta`: positive selected
delta should produce `direction: long`, negative selected delta should produce
`direction: short`. Check `signal.metadata.latest_completed_bar_low/high` to
verify the stop price. The target is mirrored at the same distance from entry
as the stop.

## Alert Contract

Each actionable alert is printed as one JSON object prefixed with
`ENTRY_SIGNAL` and appended to `engine.alerts_path` when configured.

Important fields:

- `event`: always `entry_signal` for actionable alerts.
- `alert_contract_version`: currently `entry_signal.v1`.
- `alert_id`: deterministic hash for the strategy, signal row, direction, and
  entry tick.
- `strategy_id`, `strategy_name`, `strategy_config`
- `symbol`, `contract_symbol`, `timeframe`
- `delta_method`
- `signal_timestamp`: completed bar timestamp that produced the signal.
- `entry_timestamp`: tick/open timestamp used for entry.
- `direction`: `long` or `short`.
- `side`: `buy` or `sell`.
- `quantity`: contract size after configured sizing clamps.
- `suggested_quantity`: raw sizing result before account clamp.
- `order_type`: currently always `market`.
- `entry_price`: market-entry estimate using next tick/open plus slippage.
- `entry_basis_price`: raw next tick/open price before slippage.
- `take_profit_price`
- `stop_loss_price`
- `take_profit_points`
- `stop_loss_points`
- `tick_size`, `tick_value`
- `risk_dollars`
- `reward_dollars`
- `price_normalization`: raw prices, executable rounded prices, and tick
  adjustments used to make the order valid for the futures tick grid.
- `signal`: raw strategy signal metadata.
- `sizing`: sizing-mode details from `propstack.backtest.sizing`.
- `execution_intent`: nested, versioned automation-facing order intent.

`execution_intent` is the future order-router boundary. It intentionally
duplicates the routing-critical values from the top-level alert so automation
does not need to infer anything from human text:

- `schema_version`: currently `execution_intent.v1`.
- `intent_id`: same as `alert_id`.
- `intent_type`: currently `entry`.
- `status`: currently `ready_for_manual_or_future_router`.
- `asset_class`: currently `futures`.
- `symbol`, `contract_symbol`, `timeframe`
- `direction`, `side`, `quantity`
- `order`: order type, estimated market entry, basis price, slippage ticks.
- `bracket`: stop loss and take profit prices/distances.
- `risk`: tick values plus risk/reward dollars.
- `price_normalization`: same executable tick-grid audit as the top-level
  alert.
- `timing`: signal timestamp, entry timestamp, max allowed entry lag.
- `source`: strategy id/name/config, delta method, session date.

The engine validates every `ENTRY_SIGNAL` contract before printing or appending
it. Invalid direction/side, non-finite prices, bad stop/target ordering,
non-positive quantity, or an inconsistent `execution_intent` raises a fatal
runtime error instead of emitting a malformed automation payload.

Output events have different purposes:

- `preflight`: startup summary of config, strategies, Databento settings, alert
  paths, and inferred data requirements.
- `historical_fetch_start`, `historical_fetch_complete`,
  `historical_cache_load`: historical seed/cache progress.
- `live_subscribe`: the exact Databento live subscription request.
- `live_status`: recurring health heartbeat for live data and strategy state.
- `live_stopped`: live lifecycle summary when the stream loop exits.
- `TRADE_SETUP`: a strategy setup exists, but the engine is waiting for the next
  tradable entry tick/open.
- `ENTRY_SIGNAL`: the actionable manual/future-router instruction.
- `execution_intent_ready`: durable JSONL outbox record for future order routing
  when `engine.execution_intents.enabled` is true.
- `SIGNAL_REJECTED`: a setup was discarded because entry, stop, target, sizing,
  or timing was invalid.
- `SYSTEM_ALERT`: infrastructure or data-quality problem that should be read by
  the operator.
- `FATAL`: unrecoverable startup/runtime failure; the process exits.

For manual trading, watch `ENTRY_SIGNAL`. For operational monitoring, watch
`live_status`, `SYSTEM_ALERT`, and `FATAL`. For future automation, consume the
validated `execution_intent` nested inside each `ENTRY_SIGNAL`, not the
human-readable text block.

Example shape:

```text
ENTRY_SIGNAL {
  "event": "entry_signal",
  "alert_contract_version": "entry_signal.v1",
  "strategy_id": "dummy_delta_every_5m_1r",
  "symbol": "ES",
  "contract_symbol": "ESM6",
  "direction": "long",
  "side": "buy",
  "quantity": 1,
  "entry_price": 6652.5,
  "take_profit_price": 6653.5,
  "stop_loss_price": 6651.5,
  "price_normalization": {
    "schema_version": "price_normalization.v1",
    "normalized": false,
    "entry_price_raw": 6652.5,
    "entry_price": 6652.5,
    "stop_loss_price_raw": 6651.5,
    "stop_loss_price": 6651.5,
    "take_profit_price_raw": 6653.5,
    "take_profit_price": 6653.5
  },
  "execution_intent": {
    "schema_version": "execution_intent.v1",
    "intent_type": "entry",
    "side": "buy",
    "quantity": 1,
    "order": {
      "order_type": "market",
      "estimated_entry_price": 6652.5
    },
    "bracket": {
      "stop_loss_price": 6651.5,
      "take_profit_price": 6653.5
    }
  },
  "signal": {
    "metadata": {
      "delta": 306.0,
      "latest_completed_bar_low": 6651.5
    }
  }
}
```

## Preflight

Validate config and strategy wiring without connecting to Databento:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --preflight-only
```

Preflight validates:

- config paths
- typed runtime settings such as booleans, numeric thresholds, and account
  contract bounds
- enabled strategy list
- unique strategy ids
- campaign YAML shape
- required `entry`, `sl`, and `tp` strategy modules
- timeframe compatibility between execution config and strategy params
- inferred strategy data requirements versus Databento schema
- Databento symbol/schema/stype settings that can be checked without network
  access

The preflight JSON includes a `data_plan` section. It shows the configured
Databento schema, required live schema, source columns, derived feature
families, large-trade fields, and warmup requirements inferred from the selected
strategies. This is the main check that the engine is asking Databento only for
the data it needs:

```text
"data_plan": {
  "configured_schema": "trades",
  "required_live_schema": "trades",
  "source_columns": ["open", "high", "low", "close", "volume", "signed_volume"],
  "feature_families": ["ohlcv", "trade_orderflow", "same_clock_ranks"],
  "warmup": {
    "min_warmup_sessions": 42,
    "recommended_source_bars": 16440
  }
}
```

If `databento.delta_method: price_vs_quote` is selected, preflight requires
`databento.schema: mbp-1`, because quote-based delta needs top-of-book bid/ask
prices. Trade-side delta strategies use `schema: trades` unless you explicitly
need quote fields.

When historical or replay bars are loaded, the engine counts the number of
sessions in the seed. If the selected strategies require more warmup sessions
than the seed contains, it prints `SYSTEM_ALERT insufficient_warmup_history`.
Set `engine.fail_on_insufficient_warmup: true` to turn that warning into a hard
failure.

The same audit runs immediately before live subscription. This matters when
using `--skip-historical --live`: a campaign strategy with rank/window features
can start cold, but the engine will print `SYSTEM_ALERT
insufficient_warmup_history` with `source: live_startup`, available sessions,
required sessions, and recommended source bars. With
`fail_on_insufficient_warmup: true`, live startup stops before subscribing.

## Databento Check

Use the metadata-only Databento check before a new live or historical run:

```bash
python3 -B execution_system/databento_signal_engine.py \
  --config execution_system/signal_engine.example.yaml \
  --check-databento-metadata
```

This mode validates the configured Databento API key, dataset range, schema
availability, DBN fields, and historical cost estimate. It deliberately does not
call `timeseries.get_range()` and does not subscribe to live data:

```text
"timeseries_download_attempted": false
"live_subscription_attempted": false
```

If the configured historical request would cost money, or if the cost estimate
cannot be retrieved while `fail_if_estimate_unavailable` is true, the command
exits with `FATAL` before any historical data download can happen.

## CLI Reference

- `--config`: signal-engine YAML path.
- `--project-root`: override repo root.
- `--strategy-config`: add/override campaign strategy YAMLs from the CLI.
- `--preflight-only`: validate and exit.
- `--check-databento-metadata`: validate Databento metadata and historical cost
  estimate without downloading market data.
- `--seed-only`: load/fetch historical seed and exit.
- `--skip-historical`: skip seed loading.
- `--refresh-historical`: ignore existing historical cache.
- `--replay-bars`: replay a cached 1-minute bar file.
- `--replay-stop-after-signal`: stop replay after first actionable alert.
- `--max-replay-bars`: cap replayed bars after the replay seed.
- `--live`: start Databento live streaming.
- `--once`: stop after the first completed live source bar.
- `--max-runtime`: stop live mode after this many seconds.
- `--databento-symbols`: override `databento.symbols`.
- `--databento-stype-in`: override `databento.stype_in`.
- `--databento-stype-out`: override historical `databento.stype_out`.

## Practical Checks

When validating a live signal:

1. Confirm `live_status.connected` is true.
2. Confirm `records_received`, `trade_ticks_received`, and
   `completed_source_bars` are moving during active market periods.
3. Investigate any `SYSTEM_ALERT` stale-feed messages before trusting signals.
4. Confirm the first live partial bar was dropped if you started mid-minute.
5. Compare `latest_completed_bar_timestamp_utc`, `contract_symbol`, and volume
   against your chart.
6. Compare the diagnostic delta fields before changing `delta_method`.
7. Check that `entry_timestamp` is after the signal bar close.
8. Check that stop and target are on the correct side of entry.
9. Check that `quantity` respects the account clamps in the config.

When changing strategies:

1. Run `--preflight-only`.
2. Run replay with `--replay-stop-after-signal`.
3. Inspect the alert JSONL line.
4. Then run live with `--once` or `--max-runtime` before leaving it attached.

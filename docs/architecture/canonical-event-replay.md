# Canonical event replay

`BacktestEngine` has two deliberately separate execution lanes:

- `run(data, detail_data=None)` is the existing bar lane. Its bar-close signal,
  next-bar entry, and OHLC conflict semantics are unchanged.
- `run_event_replay(sessions, strategy)` is the trade-event lane for strategies
  whose state and orders can change inside a bar.

The event lane is appropriate only when the source can provide a stable event
identity. Every session must contain timezone-aware `timestamp`, integer
`source_ordinal`, and on-tick `price` values. Strategy-specific required columns
are declared through `required_event_columns`. The engine sorts each session by
UTC timestamp nanoseconds and then source ordinal, and rejects duplicate keys,
naive timestamps, non-finite values, negative sizes, off-tick prices, and mixed
contracts. Sessions must be unique and strictly chronological.

The complete event frame is engine-private. Session callbacks receive only a
frozen `EventReplaySessionView` containing `session_date`, `contract_symbol`,
canonical-sort status, and an explicitly supplied `event_replay_metadata`
mapping. Future events are never exposed through the broker. A source adapter
must put only facts known before replay begins in that metadata.

## Event phases

Each canonical event is processed in this order:

1. `on_event_start` updates causal feature and market state.
2. `pre_execution` applies entry blocks, order cancellation, and preemptive
   flattening; the engine then evaluates the existing position bracket.
3. The engine evaluates entry orders that became active on a prior event.
4. `after_event` recomputes strategy state and may cancel, submit, or reprice
   orders.
5. All orders and bracket changes made during the current event become
   executable on the next canonical event.

This ordering means an old pending price gets its final fill opportunity before
a same-event reprice, a new order cannot fill on its creation event, and a
position cannot close and reopen on one event. Events with the same exchange
timestamp remain causally ordered by `source_ordinal`.

Broker mutations are phase-gated. Entry orders may be submitted, repriced, or
cancelled only from `after_event`; entry annotations are accepted only from
`on_entry_filled`; dynamic brackets must be returned as `PositionDirective`
values. Validation callbacks cannot mutate the order snapshot they evaluate.
An order may also be suspended without cancellation; suspended orders remain
inert until the strategy makes them eligible again.

## Ownership boundary

The engine and `EventReplayBroker` own stop-entry activation, one-position
enforcement, brackets, fills, trade IDs, position sizing, daily risk, slippage,
commissions, P&L, MFE/MAE, net liquidation, session flattening, metrics, and the
ordered transition log.

The strategy owns feature state, setup eligibility, order revalidation, and
strategy-specific evidence. Strategies submit requests with
`broker.submit_or_replace_entry(...)` and return `PositionDirective` values for
dynamic bracket management. They must not calculate fills or P&L themselves.

The v1 contract supports one instrument and one full-size position at a time,
stop entries, and full-size bracket exits. It does not simulate partial fills,
queue priority, MBO order identity, or multi-instrument portfolios. A strategy
requiring any unsupported behavior must fail closed rather than approximate it.
Generic bar-lane `apex_rules`, `event_filters.no_trade_windows`, and
`validation_export` are therefore rejected when enabled; an event strategy must
use its causal `pre_execution` policy and export the returned event evidence
explicitly until native event-lane adapters exist.

Dynamic bracket requests are rejected when their levels are already marketable
or their OCO stop/target ordering is inverted unless the strategy explicitly
opts into those semantics. Such an opt-in is part of the strategy contract and
must be exported as audit evidence; it is not an engine default.

Every event run must explicitly declare
`core.event_stop_market_fill_policy`. `trade_event_price_on_gap` fills a stop
entry or protective stop at the worse current trade-event price when price gaps
through the requested level. `exact_requested_price` fills at the requested
trigger or stop before configured slippage and is allowed only when that
optimistic assumption is an explicit strategy contract, as it is for the frozen
Yush run. The selected policy is written into reproducibility metadata.

`core.entry_start` blocks entry execution before the configured local session
time while still allowing a strategy to update causal pre-entry features. The
flatten cutoff remains exclusive: events at or after it cannot open or manage a
position, and an open position is flattened using the last pre-cutoff event.

## Result contract

The result contains `trades`, `daily`, `metrics`, `session_audits`,
`event_transitions`, `diagnostics`, and `reproducibility`. Reproducibility records
the engine lane, event ordering contract, event contract version, engine contract
version, configuration hash, session count, event count, and stop-market fill
policy. Transition rows conform to validation schema v1.3, including serialized
engine-state and event-evidence payloads.

The Yush exact Databento strategy is the first migrated consumer. Its orderflow
and AOI state live in `ExactYushRangeEventStrategy`; execution goes through
`BacktestEngine.run_event_replay`.

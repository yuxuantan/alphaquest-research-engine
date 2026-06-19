# ES Opening-Range Failed Breakout Trend/Orderflow - Rescue Attempt 1

Date: 2026-06-19

Campaign: `es_opening_range_failed_breakout_trend_orderflow`

Decision: FAIL

## Scope

This campaign tested a bounded composite of:

- completed opening-range failed breakout and reclaim,
- frozen pre-breakout 3-bar/6-bar trend agreement,
- completed Sierra aggregate orderflow confirmation,
- next-bar entry,
- opening-range-edge stop,
- fixed-R target.

The first active source set was rejected before PnL for insufficient density. It was reformulated before staged PnL to monitor the same public opening-range levels through 15:30 ET. The reformulated raw density audit passed, but the staged runner later showed that raw signal density overestimated closed-trade viability; staged runner diagnostics are authoritative.

## Original Runs

All five reformulated original variants failed `limited_core_grid_test`.

- Profitable combinations: `0 / 54` for every original variant.
- Benchmark-passing combinations: `0` for every original variant.
- Best original: `or30_full_session_signed_trend_reclaim_1530/run1`
- Best original top net: `-1252.5`
- No original reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Rescue

Rescue 1 was applied once to each failed variant.

Allowed rescue changes only:

- changed fixed `last_entry_time` from `15:30:00` to `15:45:00`,
- widened fixed `max_opening_range_pct_of_open`,
- widened fixed/grid `max_reclaim_bars`,
- fixed `min_trend_move_ticks` at `0`,
- changed orderflow threshold grid,
- widened fixed `max_stop_points`,
- shifted fixed-R target grid smaller.

Not changed:

- entry module,
- opening-range failed-breakout reclaim mechanic,
- pre-breakout trend agreement requirement,
- completed orderflow confirmation,
- stop module,
- target module,
- data source,
- costs/slippage,
- sessions,
- stage gates.

All five rescues failed `limited_core_grid_test`.

- Profitable combinations: `0 / 54` for every rescue variant.
- Benchmark-passing combinations: `0` for every rescue variant.
- Best rescue: `or30_full_session_large10_trend_reclaim_1530/rescue1`
- Best rescue top net: `-2472.5`
- No rescue reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Artifacts

- Aggregate summary: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/campaign_results.csv`
- Trade-log manifest: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/trade_logs_manifest.csv`
- Equity-curve manifest: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/equity_curves_manifest.csv`
- WFA table: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/wfa_table.csv`
- Monte Carlo summary: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/monte_carlo_summary.json`

Final decision: FAIL.

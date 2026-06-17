# ES Trade Fragmentation Liquidity Reversion Density Audit - 2026-06-17

Decision: PROCEED TO STAGED TESTING.

This audit used only local Sierra aggregate orderflow data and signal-count
logic. No PnL, stop, target, equity, WFA, monkey, Monte Carlo, or holdout result
was inspected.

## Scope

- Campaign: `es_trade_fragmentation_liquidity_reversion`
- Dataset: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Data period after configured subset: `2011-01-03 09:30:00-05:00` to `2026-06-09 15:59:00-04:00`
- Rows after configured subset: `1,488,630`
- Timeframe: `1m`
- Feature pipeline: configured `trade_orderflow_features` with completed rolling
  trade count, average trade size, return, and prior same-clock ranks.
- Per-day cap: `max_trades_per_day = 2`

## Frozen Parameter Space Checked

The source configs freeze exactly two entry tunables, one stop tunable, and one
target tunable:

- `entry.params.trade_count_rank_threshold`: `[0.55, 0.60, 0.65]`
- `entry.params.avg_trade_size_rank_threshold`: `[0.50, 0.55, 0.60]`
- `sl.params.stop_pct`: `[0.002, 0.003, 0.004]`
- `tp.params.target_r_multiple`: `[0.75, 1.0, 1.25]`

Total combinations per variant: `81`.

## Signal Density

Counts below are signal counts after the entry module's time slots, return
direction, fragmentation ranks, and per-day cap. They are not trade results.

| Variant | Threshold set | Signals | Approx signals/year | Min yearly count | Max yearly count |
|---|---:|---:|---:|---:|---:|
| `day_60m_fragmented_two_sided_fade` | loose `0.55/0.60` | 2913 | 188.8 | 94 | 236 |
| `day_60m_fragmented_two_sided_fade` | base `0.60/0.55` | 2530 | 164.0 | 81 | 212 |
| `day_60m_fragmented_two_sided_fade` | strict `0.65/0.50` | 2172 | 140.8 | 63 | 190 |
| `midday_30m_fragmented_down_fade_long` | loose `0.55/0.60` | 1680 | 108.9 | 50 | 143 |
| `midday_30m_fragmented_down_fade_long` | base `0.60/0.55` | 1478 | 95.8 | 43 | 135 |
| `midday_30m_fragmented_down_fade_long` | strict `0.65/0.50` | 1270 | 82.3 | 38 | 115 |
| `midday_30m_fragmented_up_fade_short` | loose `0.55/0.60` | 1549 | 100.4 | 46 | 134 |
| `midday_30m_fragmented_up_fade_short` | base `0.60/0.55` | 1335 | 86.5 | 38 | 120 |
| `midday_30m_fragmented_up_fade_short` | strict `0.65/0.50` | 1132 | 73.4 | 33 | 104 |
| `morning_15m_fragmented_down_fade_long` | loose `0.55/0.60` | 1664 | 107.8 | 48 | 150 |
| `morning_15m_fragmented_down_fade_long` | base `0.60/0.55` | 1458 | 94.5 | 43 | 134 |
| `morning_15m_fragmented_down_fade_long` | strict `0.65/0.50` | 1235 | 80.0 | 38 | 108 |
| `morning_15m_fragmented_up_fade_short` | loose `0.55/0.60` | 1523 | 98.7 | 45 | 131 |
| `morning_15m_fragmented_up_fade_short` | base `0.60/0.55` | 1307 | 84.7 | 39 | 118 |
| `morning_15m_fragmented_up_fade_short` | strict `0.65/0.50` | 1096 | 71.0 | 30 | 101 |

## Conclusion

The campaign is eligible for staged testing on trade-count grounds. All five
variants have base-threshold signal density above `50` signals/year over the
configured full local ES data span. Some individual calendar years are below
`50` for the one-sided variants, so WFA may still fail the stitched OOS
trade-density gate; that risk is known before testing and is not a reason to
change mechanics after results.

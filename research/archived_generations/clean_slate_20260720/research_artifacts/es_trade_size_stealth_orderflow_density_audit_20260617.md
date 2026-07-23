# ES Trade-Size Stealth Orderflow Density Audit - 2026-06-17

## Decision

Eligible for staged testing.

This audit checked only signal frequency before performance testing. It did not
inspect PnL, drawdown, profit factor, WFA, monkey, Monte Carlo, or holdout
results.

## Data

- Source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Date range checked: 2011-01-03 through 2026-06-09
- Paid data: none
- Fields used: completed ES RTH 1-minute `signed_volume`, `volume`,
  `large10_signed_volume`, `large10_volume`, `large20_signed_volume`, and
  `large20_volume`
- Feature construction: completed rolling 15, 30, and 60 minute orderflow
  windows inside each RTH session

## Frozen Density Screen

Counts below are signal counts and approximate signals/year for the predeclared
threshold grid:

- `min_large_imbalance`: `[0.015, 0.02, 0.025]`
- `min_disagreement`: `[0.03, 0.04, 0.05]`

| Variant | Residual Mode | Lowest Density In Grid | Highest Density In Grid | Density Gate |
| --- | --- | ---: | ---: | --- |
| large20_not_aligned_long_1000 | not_aligned | 760 / 49.3 per year | 845 / 54.8 per year | acceptable, near/above 50 per year |
| large20_loose_short_1030 | loose | 1228 / 79.6 per year | 1365 / 88.5 per year | pass |
| large10_loose_long_1130 | loose | 1090 / 70.6 per year | 1330 / 86.2 per year | pass |
| large10_loose_short_1230 | loose | 1015 / 65.8 per year | 1216 / 78.8 per year | pass |
| large20_opposite_two_sided_1400 | opposite | 1017 / 65.9 per year | 1145 / 74.2 per year | pass |

## Lookahead Check

The density screen used only completed rolling windows ending at the signal bar.
For example, the 10:00 variant uses the completed bar whose close time is
10:00 ET and enters no earlier than the next 1-minute bar open under the engine.

## Conclusion

The edge is frequent enough to run through the staged methodology without
violating the instruction to avoid campaigns unlikely to reach at least 50
trades per year.

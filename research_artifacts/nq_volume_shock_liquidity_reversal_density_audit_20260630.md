# nq_volume_shock_liquidity_reversal Density Audit

- Verdict: `FAIL`
- Generated: 2026-06-30
- Method: vectorized equivalent of `VolumeConditionedLiquidityReversalEntry` for one-signal-per-session variants.
- Full window: `2011-01-03` to `2026-06-12` (3813 sessions, 15.13 years)
- Limited-core window: `2011-02-22` to `2012-09-07` (371 sessions, 1.47 years)
- Latest window: `2025-06-09` to `2026-06-12` (252 sessions)
- Declared entry rows tested: `45`
- Passing entry rows: `42`
- Failing entry rows: `3`

## Variant Summary

| variant_id                          | rows | passing_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_signals | max_latest_signals |
| ----------------------------------- | ---- | ------------ | ------------------------- | ---------------------------- | ------------------ | ------------------ |
| afternoon_symmetric_shock_reversion | 9    | 9            | 82.81                     | 91.70                        | 71                 | 238                |
| all_day_symmetric_shock_reversion   | 9    | 9            | 219.68                    | 197.66                       | 241                | 252                |
| midday_symmetric_shock_reversion    | 9    | 6            | 32.19                     | 37.36                        | 29                 | 188                |
| morning_down_shock_reversal_long    | 9    | 9            | 130.46                    | 93.06                        | 176                | 241                |
| morning_up_shock_reversal_short     | 9    | 9            | 129.54                    | 90.34                        | 159                | 246                |

## Failing Rows

| variant_id                       | min_move_ticks | min_volume_ratio | full_signals_per_year | limited_signals_per_year | latest_signals | pass_full_50_per_year | pass_limited_50_per_year | pass_latest_50_signals |
| -------------------------------- | -------------- | ---------------- | --------------------- | ------------------------ | -------------- | --------------------- | ------------------------ | ---------------------- |
| midday_symmetric_shock_reversion | 6              | 2.25             | 38.53                 | 55.02                    | 29             | False                 | True                     | False                  |
| midday_symmetric_shock_reversion | 10             | 2.25             | 35.23                 | 44.15                    | 29             | False                 | False                    | False                  |
| midday_symmetric_shock_reversion | 14             | 2.25             | 32.19                 | 37.36                    | 29             | False                 | False                    | False                  |

The campaign fails before PnL because at least one declared entry row is too sparse. Dropping rows after this audit would be post-screen narrowing and is not authorized.

# nq_opening_range_failed_breakout_orderflow Density Audit

- Verdict: `FAIL`
- Generated: 2026-06-30
- Method: actual `OpeningRangeFailedBreakoutOrderflowEntry` state machine on prepared 5-minute bars.
- Full window: `2011-01-03` to `2026-06-12` (3813 sessions, 15.13 years)
- Limited-core window: `2011-02-22` to `2012-09-07` (371 sessions, 1.47 years)
- Latest window: `2025-06-09` to `2026-06-12` (252 sessions)
- Declared entry rows tested: `29`
- Passing entry rows: `27`
- Failing entry rows: `2`

## Variant Summary

| variant_id                       | rows | passing_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_signals | max_latest_signals |
| -------------------------------- | ---- | ------------ | ------------------------- | ---------------------------- | ------------------ | ------------------ |
| or15_large10_failed_reclaim_1030 | 6    | 6            | 64.50                     | 57.06                        | 89                 | 96                 |
| or15_signed_failed_reclaim_1030  | 4    | 4            | 66.62                     | 66.57                        | 57                 | 102                |
| or30_large20_failed_reclaim_1130 | 9    | 9            | 57.43                     | 67.92                        | 58                 | 77                 |
| or30_signed_failed_reclaim_1100  | 4    | 4            | 70.91                     | 73.36                        | 56                 | 92                 |
| or60_signed_failed_reclaim_1200  | 6    | 4            | 49.70                     | 61.13                        | 24                 | 100                |

## Failing Rows

| variant_id                      | max_reclaim_bars | min_reclaim_orderflow_imbalance | full_signals_per_year | limited_signals_per_year | latest_signals | pass_full_50_per_year | pass_limited_50_per_year | pass_latest_50_signals |
| ------------------------------- | ---------------- | ------------------------------- | --------------------- | ------------------------ | -------------- | --------------------- | ------------------------ | ---------------------- |
| or60_signed_failed_reclaim_1200 | 3                | 0.10                            | 49.70                 | 61.13                    | 24             | False                 | True                     | False                  |
| or60_signed_failed_reclaim_1200 | 4                | 0.10                            | 52.81                 | 63.17                    | 25             | True                  | True                     | False                  |

The campaign fails before PnL if any declared entry row is too sparse. Dropping rows after this audit would be post-screen narrowing and is not authorized.

# ES Intraday Periodicity Orderflow Confirmation Rescue 1 Density Audit - 2026-06-18

Purpose: pre-PnL signal-density check for the single allowed per-variant rescue attempt. Counts replay the actual class-based entry logic using prior-session-only periodicity features plus completed local Sierra ES orderflow bars. No stops, targets, PnL, WFA, monkey, Monte Carlo, or holdout outcomes were inspected.

Rescue parameter-space changes declared before PnL: fixed `entry.params.min_mean_return_bps = 0.75`, stop grid `[0.0015, 0.0025, 0.0035]`, and target grid `[1.0, 1.25, 1.5]`. Entry module, slot/source window, flow mode, data, costs, fills, sessions, and validation gates are unchanged.

| variant | window | period | entry combos | source sessions | min signals/year | median signals/year | max signals/year | density pass |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `afternoon_1330_large20_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 77.96 | 92.80 | 104.79 | TRUE |
| `afternoon_1330_large20_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 67.59 | 90.99 | 105.29 | TRUE |
| `afternoon_1330_large20_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 77.99 | 91.74 | 103.84 | TRUE |
| `afternoon_1330_large20_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 72.05 | 105.07 | 119.08 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 84.31 | 96.50 | 107.71 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 79.29 | 92.29 | 97.49 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 83.97 | 96.28 | 107.80 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 80.05 | 88.06 | 110.08 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 74.66 | 91.51 | 110.30 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 82.54 | 102.04 | 113.08 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 77.27 | 92.18 | 109.75 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 50.03 | 81.06 | 114.08 | TRUE |
| `morning_1000_signed_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 68.95 | 91.18 | 107.25 | TRUE |
| `morning_1000_signed_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 81.89 | 93.59 | 107.24 | TRUE |
| `morning_1000_signed_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 69.85 | 92.03 | 106.58 | TRUE |
| `morning_1000_signed_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 64.04 | 91.06 | 119.08 | TRUE |
| `morning_1030_large10_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 77.70 | 92.54 | 110.82 | TRUE |
| `morning_1030_large10_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 77.34 | 87.09 | 102.69 | TRUE |
| `morning_1030_large10_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 75.47 | 91.10 | 110.11 | TRUE |
| `morning_1030_large10_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 96.07 | 103.07 | 113.08 | TRUE |

Decision: PASS density screen. Every declared rescue entry-grid corner must clear at least 50 expected signals/year in the full history, limited-core random window, WFA first-90% window, and latest-year validation slice before rescue PnL testing.

CSV detail: `research_artifacts/es_intraday_periodicity_orderflow_confirmation_rescue_attempt_1_density_audit_20260618.csv`.

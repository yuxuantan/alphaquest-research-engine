# ES Intraday Periodicity Orderflow Confirmation Density Audit - 2026-06-18

Purpose: pre-PnL signal-density check before staged testing. Counts use the prior-session-only periodicity feature CSV plus completed local Sierra ES orderflow bars. No stops, targets, PnL, WFA, monkey, Monte Carlo, or holdout outcomes were inspected.

| variant | window | period | entry combos | source sessions | min signals/year | median signals/year | max signals/year | density pass |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `afternoon_1330_large20_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 88.32 | 100.95 | 110.67 | TRUE |
| `afternoon_1330_large20_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 77.20 | 97.96 | 112.88 | TRUE |
| `afternoon_1330_large20_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 87.77 | 99.79 | 109.73 | TRUE |
| `afternoon_1330_large20_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 89.82 | 114.76 | 124.74 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 93.24 | 103.22 | 114.04 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 90.83 | 97.31 | 103.15 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 93.17 | 102.96 | 113.90 | TRUE |
| `late_afternoon_1430_large20_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 88.82 | 97.80 | 118.76 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 83.59 | 99.59 | 115.40 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 93.42 | 106.40 | 117.42 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 85.46 | 100.87 | 115.13 | TRUE |
| `late_morning_1130_signed_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 69.86 | 92.81 | 115.76 | TRUE |
| `morning_1000_signed_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 76.00 | 95.25 | 110.93 | TRUE |
| `morning_1000_signed_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 90.18 | 97.31 | 108.99 | TRUE |
| `morning_1000_signed_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 77.18 | 96.19 | 110.45 | TRUE |
| `morning_1000_signed_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 68.86 | 94.81 | 121.75 | TRUE |
| `morning_1030_large10_confirmed_slot` | `full` | `2011-01-03 to 2026-06-09` | 9 | 3817 | 84.88 | 98.16 | 115.14 | TRUE |
| `morning_1030_large10_confirmed_slot` | `limited_core_random_10pct` | `2011-02-22 to 2012-09-06` | 9 | 374 | 83.69 | 93.42 | 107.04 | TRUE |
| `morning_1030_large10_confirmed_slot` | `wfa_first_90pct` | `2011-01-03 to 2024-11-22` | 9 | 3438 | 83.01 | 97.27 | 114.26 | TRUE |
| `morning_1030_large10_confirmed_slot` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 249 | 97.80 | 105.78 | 120.75 | TRUE |

Decision: PASS density screen. Every declared variant and entry-grid corner clears at least 50 expected signals/year in the full history, limited-core random window, WFA first-90% window, and latest-year validation slice before any PnL testing.

CSV detail: `research_artifacts/es_intraday_periodicity_orderflow_confirmation_density_audit_20260618.csv`.

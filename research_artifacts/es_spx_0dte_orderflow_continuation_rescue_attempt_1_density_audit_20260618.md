# ES SPX 0DTE orderflow continuation rescue attempt 1 density audit - 2026-06-18

Purpose: pre-PnL signal-density check for the single allowed per-variant rescue attempt. Counts use only local SPX 0DTE calendar rows, local Sierra ES completed bars, and declared rescue entry grids; no PnL, drawdown, WFA, monkey, Monte Carlo, or holdout outcomes were inspected.

| variant | window | period | entry combos | calendar sessions | min signals/year | median signals/year | max signals/year | density pass |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `early_large10_flow_continuation_1000` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 93.77 | 98.14 | 104.07 | TRUE |
| `early_large10_flow_continuation_1000` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 55.52 | 59.41 | 68.18 | TRUE |
| `early_large10_flow_continuation_1000` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 88.64 | 92.85 | 99.22 | TRUE |
| `early_large10_flow_continuation_1000` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 140.71 | 146.70 | 148.69 | TRUE |
| `early_signed_flow_continuation_1000` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 85.80 | 100.96 | 115.73 | TRUE |
| `early_signed_flow_continuation_1000` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 50.65 | 57.47 | 64.28 | TRUE |
| `early_signed_flow_continuation_1000` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 81.84 | 96.31 | 109.91 | TRUE |
| `early_signed_flow_continuation_1000` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 120.75 | 141.71 | 167.66 | TRUE |
| `late_day_large20_flow_continuation_1430` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 96.39 | 104.94 | 114.66 | TRUE |
| `late_day_large20_flow_continuation_1430` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 50.65 | 59.41 | 69.15 | TRUE |
| `late_day_large20_flow_continuation_1430` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 91.12 | 99.76 | 109.69 | TRUE |
| `late_day_large20_flow_continuation_1430` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 144.70 | 150.69 | 158.67 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 103.48 | 108.92 | 114.56 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 64.28 | 73.05 | 75.97 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 98.25 | 103.76 | 109.48 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 148.69 | 153.68 | 158.67 | TRUE |
| `midday_large20_flow_continuation_1330` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 98.24 | 108.15 | 118.74 | TRUE |
| `midday_large20_flow_continuation_1330` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 50.65 | 65.26 | 77.92 | TRUE |
| `midday_large20_flow_continuation_1330` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 93.17 | 103.32 | 113.90 | TRUE |
| `midday_large20_flow_continuation_1330` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 145.70 | 152.69 | 163.66 | TRUE |

Decision: PASS density screen. Every rescue entry-grid corner clears at least 50 expected signals/year in the full history, limited-core random window, WFA first-90% window, and latest-year validation slice before rescue PnL testing.

CSV detail: `research_artifacts/es_spx_0dte_orderflow_continuation_rescue_attempt_1_density_audit_20260618.csv`.

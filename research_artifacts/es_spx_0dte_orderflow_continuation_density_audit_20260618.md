# ES SPX 0DTE orderflow continuation density audit - 2026-06-18

Purpose: pre-PnL signal-density and mechanics check before staged testing. Counts use only the local SPX 0DTE calendar, local Sierra ES completed bars, and the declared entry grids. No stops, targets, PnL, drawdown, WFA, monkey, Monte Carlo, or holdout outcomes were inspected.

This audit supersedes the initial 2011-start draft. The configured data-validity start is `2016-02-24`, the first regular M/W/F SPX weekly-expiration regime date used by this campaign; pre-2016 sessions are excluded because they are too sparse for the 50-trades/year rule.

Resolved windows: limited_core_random_10pct: `2016-04-14` to `2017-04-23`; wfa_first_90pct: `2016-02-24` to `2025-05-29`; latest_1y: `2025-06-09` to `2026-06-09`.
Standard monthly OPEX sessions are excluded by config to avoid overlap with active monthly/quarterly OPEX families. Only non-standard-monthly `is_spx_0dte` sessions are counted.

| variant | window | period | entry combos | calendar sessions | min signals/year | median signals/year | max signals/year | density pass |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `early_large10_flow_continuation_1000` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 92.11 | 98.14 | 106.01 | TRUE |
| `early_large10_flow_continuation_1000` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 53.57 | 59.41 | 72.08 | TRUE |
| `early_large10_flow_continuation_1000` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 87.13 | 92.85 | 101.16 | TRUE |
| `early_large10_flow_continuation_1000` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 137.72 | 146.70 | 150.69 | TRUE |
| `early_signed_flow_continuation_1000` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 89.68 | 103.87 | 120.88 | TRUE |
| `early_signed_flow_continuation_1000` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 56.49 | 61.36 | 75.00 | TRUE |
| `early_signed_flow_continuation_1000` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 86.05 | 99.22 | 115.31 | TRUE |
| `early_signed_flow_continuation_1000` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 121.75 | 144.70 | 170.65 | TRUE |
| `late_day_large20_flow_continuation_1430` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 96.39 | 104.94 | 114.66 | TRUE |
| `late_day_large20_flow_continuation_1430` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 50.65 | 59.41 | 69.15 | TRUE |
| `late_day_large20_flow_continuation_1430` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 91.12 | 99.76 | 109.69 | TRUE |
| `late_day_large20_flow_continuation_1430` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 144.70 | 150.69 | 158.67 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 92.70 | 97.94 | 104.36 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 51.62 | 54.54 | 65.26 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 87.02 | 92.42 | 99.01 | TRUE |
| `late_morning_large20_flow_continuation_1030` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 142.71 | 145.70 | 150.69 | TRUE |
| `midday_large20_flow_continuation_1330` | `full` | `2016-02-24 to 2026-06-09` | 9 | 1787 | 98.24 | 108.15 | 118.74 | TRUE |
| `midday_large20_flow_continuation_1330` | `limited_core_random_10pct` | `2016-04-14 to 2017-04-23` | 9 | 122 | 50.65 | 65.26 | 77.92 | TRUE |
| `midday_large20_flow_continuation_1330` | `wfa_first_90pct` | `2016-02-24 to 2025-05-29` | 9 | 1544 | 93.17 | 103.32 | 113.90 | TRUE |
| `midday_large20_flow_continuation_1330` | `latest_1y` | `2025-06-09 to 2026-06-09` | 9 | 237 | 145.70 | 152.69 | 163.66 | TRUE |

Decision: PASS density screen. Every declared variant and entry-grid corner clears at least 50 expected signals/year in the full history, limited-core random window, WFA first-90% window, and latest-year validation slice before any PnL testing.

CSV detail: `research_artifacts/es_spx_0dte_orderflow_continuation_density_audit_20260618.csv`.

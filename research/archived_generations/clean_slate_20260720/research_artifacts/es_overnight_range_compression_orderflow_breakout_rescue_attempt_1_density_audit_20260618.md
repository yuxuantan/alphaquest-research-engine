# es_overnight_range_compression_orderflow_breakout Rescue Attempt 1 Density Audit

Date: 2026-06-18

Scope: pre-PnL rescue signal-density audit across declared entry parameter corners only. No rescue PnL, stops, targets, fills, WFA, monkey, or Monte Carlo results were computed before this audit.

Full configured window: `2011-01-03` through `2026-05-29`.
Limited-core window: `2011-02-22` through `2012-09-05` using seeded random 10 percent period, excluding latest 10 percent and the configured Covid avoid range.

Result: PASS. Minimum required density is 50 signals/year.
Weakest full-window density: 71.154284 signals/year.
Weakest limited-core density: 74.089858 signals/year.

| variant_id | window | start_date | end_date | entry_combinations | worst_signals | worst_signals_per_year | median_signals_per_year | best_signals_per_year | density_gate_pass | worst_params | best_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| afternoon_large20_two_sided_breakout_1500 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1339 | 86.930279 | 106.341895 | 124.000622 | True | rank=0.5, imbalance=0.15 | rank=0.7, imbalance=0.0 |
| afternoon_large20_two_sided_breakout_1500 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 122 | 79.289146 | 90.337633 | 110.484875 | True | rank=0.5, imbalance=0.15 | rank=0.7, imbalance=0.0 |
| late_morning_large10_two_sided_breakout_1130 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1240 | 80.503022 | 100.369090 | 117.768130 | True | rank=0.5, imbalance=0.1 | rank=0.7, imbalance=0.0 |
| late_morning_large10_two_sided_breakout_1130 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 126 | 81.888790 | 92.937278 | 112.434609 | True | rank=0.5, imbalance=0.1 | rank=0.7, imbalance=0.0 |
| midday_signed_two_sided_breakout_1300 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1233 | 80.048569 | 98.746045 | 115.366024 | True | rank=0.5, imbalance=0.03 | rank=0.7, imbalance=0.0 |
| midday_signed_two_sided_breakout_1300 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 114 | 74.089858 | 83.188612 | 98.786477 | True | rank=0.5, imbalance=0.0 | rank=0.7, imbalance=0.0 |
| morning_large10_two_sided_breakout_1100 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1183 | 76.802480 | 96.343939 | 112.963918 | True | rank=0.5, imbalance=0.1 | rank=0.7, imbalance=0.0 |
| morning_large10_two_sided_breakout_1100 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 121 | 78.639235 | 89.687722 | 109.834964 | True | rank=0.5, imbalance=0.04 | rank=0.7, imbalance=0.0 |
| morning_signed_two_sided_breakout_1030 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1096 | 71.154284 | 88.163793 | 101.537682 | True | rank=0.5, imbalance=0.03 | rank=0.7, imbalance=0.0 |
| morning_signed_two_sided_breakout_1030 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 116 | 75.389680 | 86.438167 | 104.635676 | True | rank=0.5, imbalance=0.03 | rank=0.7, imbalance=0.0 |

Detail CSV: `research_artifacts/es_overnight_range_compression_orderflow_breakout_rescue_attempt_1_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_overnight_range_compression_orderflow_breakout_rescue_attempt_1_density_summary_20260618.csv`

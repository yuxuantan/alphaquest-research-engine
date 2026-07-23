# es_overnight_range_compression_orderflow_breakout Reformulated Density Audit

Date: 2026-06-18

Scope: pre-PnL signal-density audit after mechanics reformulation and before any staged PnL. Counts declared entry parameter corners only; no stops, targets, fills, net profit, WFA, monkey, or Monte Carlo results were computed.

Full configured window: `2011-01-03` through `2026-05-29`.
Limited-core window: `2011-02-22` through `2012-09-05` using seeded random 10 percent period, excluding latest 10 percent and the configured Covid avoid range.

Result: PASS. Minimum required density is 50 signals/year.
Weakest full-window density: 57.196098 signals/year.
Weakest limited-core density: 59.791815 signals/year.

| variant_id | window | start_date | end_date | entry_combinations | worst_signals | worst_signals_per_year | median_signals_per_year | best_signals_per_year | density_gate_pass | worst_params | best_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| afternoon_large20_two_sided_breakout_1500 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1101 | 71.478893 | 88.553324 | 106.731426 | True | rank=0.4, imbalance=0.1 | rank=0.6, imbalance=0.0 |
| afternoon_large20_two_sided_breakout_1500 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 98 | 63.691281 | 80.588968 | 90.987544 | True | rank=0.4, imbalance=0.1 | rank=0.6, imbalance=0.0 |
| late_morning_large10_two_sided_breakout_1130 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1029 | 66.804524 | 83.294659 | 101.277995 | True | rank=0.4, imbalance=0.08 | rank=0.6, imbalance=0.0 |
| late_morning_large10_two_sided_breakout_1130 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 104 | 67.590747 | 82.538701 | 92.937278 | True | rank=0.4, imbalance=0.0 | rank=0.6, imbalance=0.0 |
| midday_signed_two_sided_breakout_1300 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 1011 | 65.635931 | 80.438100 | 99.200498 | True | rank=0.4, imbalance=0.04 | rank=0.6, imbalance=0.0 |
| midday_signed_two_sided_breakout_1300 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 93 | 60.441726 | 74.089858 | 83.188612 | True | rank=0.4, imbalance=0.0 | rank=0.6, imbalance=0.0 |
| morning_large10_two_sided_breakout_1100 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 991 | 64.337496 | 80.048569 | 97.772218 | True | rank=0.4, imbalance=0.08 | rank=0.6, imbalance=0.0 |
| morning_large10_two_sided_breakout_1100 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 97 | 63.041370 | 78.639235 | 90.337633 | True | rank=0.4, imbalance=0.04 | rank=0.6, imbalance=0.0 |
| morning_signed_two_sided_breakout_1030 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 881 | 57.196098 | 72.517641 | 88.683167 | True | rank=0.4, imbalance=0.04 | rank=0.6, imbalance=0.0 |
| morning_signed_two_sided_breakout_1030 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 92 | 59.791815 | 76.039591 | 86.438167 | True | rank=0.4, imbalance=0.04 | rank=0.6, imbalance=0.0 |

Detail CSV: `research_artifacts/es_overnight_range_compression_orderflow_breakout_reformulated_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_overnight_range_compression_orderflow_breakout_reformulated_density_summary_20260618.csv`

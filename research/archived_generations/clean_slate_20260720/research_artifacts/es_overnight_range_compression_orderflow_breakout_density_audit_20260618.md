# es_overnight_range_compression_orderflow_breakout Density Audit

Date: 2026-06-18

Scope: pre-PnL signal-density audit across declared entry parameter corners only. No stops, targets, fills, net profit, WFA, monkey, or Monte Carlo results were computed.

Full configured window: `2011-01-03` through `2026-05-29`.
Limited-core window: `2011-02-22` through `2012-09-05` using seeded random 10 percent period, excluding latest 10 percent and the configured Covid avoid range.

Result: FAIL. Minimum required density is 50 signals/year.
Weakest full-window density: 13.698498 signals/year.
Weakest limited-core density: 12.348310 signals/year.

| variant_id | window | start_date | end_date | entry_combinations | worst_signals | worst_signals_per_year | median_signals_per_year | best_signals_per_year | density_gate_pass | worst_params | best_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| afternoon_large20_two_sided_breakout_1500 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 545 | 35.382376 | 54.079852 | 71.478893 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| afternoon_large20_two_sided_breakout_1500 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 47 | 30.545819 | 50.043149 | 63.691281 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| late_morning_large10_two_sided_breakout_1130 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 501 | 32.525818 | 50.249467 | 66.804524 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| late_morning_large10_two_sided_breakout_1130 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 47 | 30.545819 | 47.443505 | 67.590747 | False | rank=0.2, buffer=1 | rank=0.4, buffer=0 |
| midday_signed_two_sided_breakout_1300 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 499 | 32.395974 | 49.859936 | 65.635931 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| midday_signed_two_sided_breakout_1300 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 42 | 27.296263 | 44.843861 | 60.441726 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| morning_signed_high_breakout_long_1030 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 224 | 14.542481 | 22.398018 | 30.318477 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| morning_signed_high_breakout_long_1030 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 19 | 12.348310 | 18.197509 | 25.346530 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| morning_signed_low_breakout_short_1030 | full_configured_period | 2011-01-03 | 2026-05-29 | 9 | 211 | 13.698498 | 21.554035 | 28.500667 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |
| morning_signed_low_breakout_short_1030 | limited_core_random_10pct | 2011-02-22 | 2012-09-05 | 9 | 20 | 12.998221 | 24.046708 | 34.445285 | False | rank=0.2, buffer=2 | rank=0.4, buffer=0 |

Detail CSV: `research_artifacts/es_overnight_range_compression_orderflow_breakout_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_overnight_range_compression_orderflow_breakout_density_summary_20260618.csv`

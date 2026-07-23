# ES Opening-Range Retest Orderflow Density Audit

Pre-performance density check only. Counts use the proposed completed-bar entry
rules over prepared 5-minute RTH bars and do not inspect PnL.

Prepared data period: 2011-01-03 09:30:00 to 2026-06-09 15:55:00 America/New_York;
session days=3817; approximate years=15.147.

Directional OR15 retest variants were rejected before PnL because every tested
corner was below 50 signals/year. The final campaign uses two-sided variants
only.

| variant | max_retest_bars | min_orderflow_imbalance | approx_trades_per_year |
|---|---:|---:|---:|
| or15_two_sided_signed_absorption_retest_1030 | 2 | 0.005 | 89.9 |
| or15_two_sided_signed_absorption_retest_1030 | 2 | 0.02 | 80.3 |
| or15_two_sided_signed_absorption_retest_1030 | 2 | 0.04 | 65.8 |
| or15_two_sided_signed_absorption_retest_1030 | 3 | 0.005 | 94.3 |
| or15_two_sided_signed_absorption_retest_1030 | 3 | 0.02 | 84.7 |
| or15_two_sided_signed_absorption_retest_1030 | 3 | 0.04 | 70.2 |
| or15_two_sided_signed_absorption_retest_1030 | 4 | 0.005 | 95.5 |
| or15_two_sided_signed_absorption_retest_1030 | 4 | 0.02 | 86.0 |
| or15_two_sided_signed_absorption_retest_1030 | 4 | 0.04 | 71.6 |
| or15_two_sided_signed_aligned_retest_1030 | 2 | 0.005 | 99.4 |
| or15_two_sided_signed_aligned_retest_1030 | 2 | 0.02 | 88.6 |
| or15_two_sided_signed_aligned_retest_1030 | 2 | 0.04 | 71.3 |
| or15_two_sided_signed_aligned_retest_1030 | 3 | 0.005 | 102.3 |
| or15_two_sided_signed_aligned_retest_1030 | 3 | 0.02 | 91.6 |
| or15_two_sided_signed_aligned_retest_1030 | 3 | 0.04 | 75.0 |
| or15_two_sided_signed_aligned_retest_1030 | 4 | 0.005 | 103.9 |
| or15_two_sided_signed_aligned_retest_1030 | 4 | 0.02 | 93.1 |
| or15_two_sided_signed_aligned_retest_1030 | 4 | 0.04 | 76.7 |
| or30_two_sided_signed_absorption_retest_1100 | 2 | 0.005 | 92.8 |
| or30_two_sided_signed_absorption_retest_1100 | 2 | 0.02 | 83.4 |
| or30_two_sided_signed_absorption_retest_1100 | 2 | 0.04 | 69.9 |
| or30_two_sided_signed_absorption_retest_1100 | 3 | 0.005 | 96.7 |
| or30_two_sided_signed_absorption_retest_1100 | 3 | 0.02 | 87.2 |
| or30_two_sided_signed_absorption_retest_1100 | 3 | 0.04 | 74.7 |
| or30_two_sided_signed_absorption_retest_1100 | 4 | 0.005 | 97.5 |
| or30_two_sided_signed_absorption_retest_1100 | 4 | 0.02 | 88.6 |
| or30_two_sided_signed_absorption_retest_1100 | 4 | 0.04 | 76.3 |
| or30_two_sided_large10_absorption_retest_1130 | 2 | 0.02 | 112.4 |
| or30_two_sided_large10_absorption_retest_1130 | 2 | 0.05 | 103.8 |
| or30_two_sided_large10_absorption_retest_1130 | 2 | 0.08 | 93.2 |
| or30_two_sided_large10_absorption_retest_1130 | 3 | 0.02 | 116.2 |
| or30_two_sided_large10_absorption_retest_1130 | 3 | 0.05 | 108.4 |
| or30_two_sided_large10_absorption_retest_1130 | 3 | 0.08 | 98.0 |
| or30_two_sided_large10_absorption_retest_1130 | 4 | 0.02 | 118.4 |
| or30_two_sided_large10_absorption_retest_1130 | 4 | 0.05 | 111.4 |
| or30_two_sided_large10_absorption_retest_1130 | 4 | 0.08 | 100.9 |
| or60_two_sided_large20_aligned_retest_1230 | 2 | 0.02 | 109.1 |
| or60_two_sided_large20_aligned_retest_1230 | 2 | 0.05 | 104.9 |
| or60_two_sided_large20_aligned_retest_1230 | 2 | 0.08 | 100.3 |
| or60_two_sided_large20_aligned_retest_1230 | 3 | 0.02 | 113.2 |
| or60_two_sided_large20_aligned_retest_1230 | 3 | 0.05 | 109.2 |
| or60_two_sided_large20_aligned_retest_1230 | 3 | 0.08 | 105.0 |
| or60_two_sided_large20_aligned_retest_1230 | 4 | 0.02 | 114.1 |
| or60_two_sided_large20_aligned_retest_1230 | 4 | 0.05 | 110.4 |
| or60_two_sided_large20_aligned_retest_1230 | 4 | 0.08 | 106.6 |

Conclusion: every declared entry corner for the final five variants is above
50 signals/year before PnL testing.

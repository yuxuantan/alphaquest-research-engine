# NQ Fiscal Deficit Treasury Supply State Methodology Audit

Date: 2026-07-01

Final verdict: FAIL

## Density Audit

The final pre-PnL density audit passed 45/45 declared rows. No PnL was inspected before freezing the five variants.

## Staged Validation

All five variants failed limited_core_grid_test. high_deficit_12m_short_1030 had only 3/27 profitable combinations and 0/27 benchmark-passing combinations; the other four variants had 0/27 profitable combinations. No branch reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Profitable Rate | Benchmark Passing | Top Net | Top PF | Top Trades |
|---|---|---:|---:|---:|---:|---:|
| high_deficit_3m_short_1000 | limited_core_grid_test | 0.000000 | 0/27 | -3625.0 | 0.8954125793421812 | 349 |
| high_deficit_12m_short_1030 | limited_core_grid_test | 0.111111 | 0/27 | 115.0 | 1.002691317575474 | 371 |
| strong_receipts_yoy_long_1130 | limited_core_grid_test | 0.000000 | 0/27 | -2335.0 | 0.8103168155970756 | 129 |
| low_outlays_yoy_long_1200 | limited_core_grid_test | 0.000000 | 0/27 | -230.0 | 0.9888457807953444 | 234 |
| high_fiscal_impulse_short_1330 | limited_core_grid_test | 0.000000 | 0/27 | -495.0 | 0.9586638830897704 | 130 |

## Downstream Gates

Not reached because all five variants failed limited_core_grid_test. No rescue was authorized.

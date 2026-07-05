# NQ Trade Balance Quantity State Methodology Audit

Date: 2026-07-01

Final verdict: FAIL

## Density Audit

The final pre-PnL density audit passed 45/45 declared rows. No PnL was inspected before freezing the five variants.

## Frozen Mechanics

Each variant reads only the latest FRED/Census/BEA monthly BOP trade observation available on or before `session_date - 60 calendar days`. Each signal uses the completed one-minute RTH bar immediately before the configured decision time and is intended for next-bar-open execution.

## Staged Validation

All five variants failed limited_core_grid_test. `deteriorating_balance_short_1330` had only 1/27 profitable combinations and 0/27 benchmark-passing combinations; the other four variants had 0/27 profitable combinations.

| Variant | Terminal Stage | Profitable Rate | Benchmark Passing | Top Net | Top PF | Top Trades |
|---|---|---:|---:|---:|---:|---:|
| strong_trade_balance_share_long_1000 | limited_core_grid_test | 0.000000 | 0/27 | -2875.0 | 0.9150162577593851 | 371 |
| high_export_import_ratio_long_1030 | limited_core_grid_test | 0.000000 | 0/27 | -3900.0 | 0.8926950061906728 | 371 |
| export_growth_strength_long_1130 | limited_core_grid_test | 0.000000 | 0/27 | -1390.0 | 0.8489951113525258 | 105 |
| weak_import_growth_short_1200 | limited_core_grid_test | 0.000000 | 0/27 | -182.5 | 0.9863398203592815 | 166 |
| deteriorating_balance_short_1330 | limited_core_grid_test | 0.037037 | 0/27 | 50.0 | 1.0045187528242205 | 141 |

## Downstream Gates

Not reached because all five variants failed limited_core_grid_test. No rescue was authorized.

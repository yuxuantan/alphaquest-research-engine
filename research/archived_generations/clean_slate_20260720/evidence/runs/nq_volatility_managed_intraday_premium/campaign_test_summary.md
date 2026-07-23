# NQ Volatility Managed Intraday Premium - Campaign Summary

Verdict: FAIL

All five predeclared NQ variants failed the `limited_core_grid_test` stability gate. No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Stage | Profitable combos | Top net | Top PF | Top trades/year |
|---|---:|---:|---:|---:|---:|
| low_10d_range_midmorning_long_1030 | limited_core_grid_test | 13/27 | 4415.0 | 1.3665421336654213 | 98.57300524068995 |
| low_20d_vol_open_long_1000 | limited_core_grid_test | 9/27 | 2430.0 | 1.3993426458504519 | 52.68971241708467 |
| low_5d_abs_move_lunch_long_1200 | limited_core_grid_test | 0/27 | -30.0 | 0.9966024915062288 | 82.42583873473231 |
| low_downside20_afternoon_long_1330 | limited_core_grid_test | 1/27 | 122.5 | 1.0243781094527362 | 62.36516496782074 |
| vol_downshift_late_morning_long_1100 | limited_core_grid_test | 5/27 | 2655.0 | 1.207584050039093 | 93.42388061568482 |

No rescue was authorized or used.

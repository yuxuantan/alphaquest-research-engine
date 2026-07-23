# NQ Cboe VXN/VIX Dispersion Intraday - Campaign Summary

Verdict: FAIL

All five variants failed the limited core grid. No variant reached monkey robustness, WFA, downstream Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR |
|---|---:|---:|---:|---:|---:|---:|
| high_vxn_vix_ratio_short_1000 | limited_core_grid_test | 2/27 | 645.0 | 1.0988505747126436 | 123 | 0.3553882371790671 |
| rising_vxn_vix_ratio_short_1030 | limited_core_grid_test | 0/27 | -1210.0 | 0.9168670559945036 | 96 | -0.1481573766542553 |
| low_vxn_vix_ratio_long_1130 | limited_core_grid_test | 5/18 | 1061.25 | 1.1050742574257426 | 110 | 0.870624124800208 |
| falling_vxn_vix_ratio_long_1200 | limited_core_grid_test | 4/27 | 615.0 | 1.074726609963548 | 84 | 0.18338133041675958 |
| high_vxn_minus_vix_short_1330 | limited_core_grid_test | 7/18 | 407.5 | 1.0491852745926373 | 102 | 0.19577137277823228 |

No rescue was authorized or used.

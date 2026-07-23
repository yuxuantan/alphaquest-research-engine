# NQ Credit ETF Orderflow Risk-Appetite - Campaign Summary

Verdict: FAIL

All five variants failed the limited core grid. No variant reached monkey robustness, WFA, downstream Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR |
|---|---:|---:|---:|---:|---:|---:|
| hyg_1d_strength_signed_long_1230 | limited_core_grid_test | 21/81 | 580.0 | 1.3109919571045576 | 21 | 0.5408613804870601 |
| hyg_1d_weakness_signed_short_1230 | limited_core_grid_test | 22/81 | 690.0 | 1.0977337110481586 | 79 | 0.3875606284858875 |
| hyg_1d_two_sided_signed_1230 | limited_core_grid_test | 7/81 | 730.0 | 1.0761606677099635 | 111 | 0.38898613333040466 |
| hyg_3d_two_sided_signed_1230 | limited_core_grid_test | 27/81 | 2320.0 | 1.2479957242116515 | 96 | 1.355412441287462 |
| hyg_5d_two_sided_signed_1230 | limited_core_grid_test | 35/81 | 2705.0 | 1.233390854184642 | 145 | 1.4061338075199026 |

No rescue was authorized or used.

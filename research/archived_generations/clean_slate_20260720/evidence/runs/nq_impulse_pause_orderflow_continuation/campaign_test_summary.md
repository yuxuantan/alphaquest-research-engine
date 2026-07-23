# NQ impulse-pause breakout continuation with aggregate orderflow confirmation

Verdict: FAIL.

The campaign passed pre-PnL density. Four variants failed `limited_core_grid_test`; one variant passed limited core and monkey, then failed `walk_forward_analysis`.

Density: PASS, 45/45 declared entry rows. Minimum full-history density 142.43/year; minimum limited-core density 129.33/year; minimum latest-window count 142.

Core-grid aggregate: 183/405 profitable combinations, 69 benchmark-passing combinations, 0 Apex-rule-violating iterations.

WFA rejection: `late_morning_large10_two_sided_impulse_pause_breakout_1230` stitched OOS PF 1.0911 < 1.2 and MAR 0.2492 < 0.4; 5/10 OOS windows were profitable.

| Variant | Terminal | Profitable combos | Benchmark pass | Top net | Top PF | WFA PF | WFA MAR |
|---|---|---:|---:|---:|---:|---:|---:|
| morning_signed_two_sided_impulse_pause_breakout_1130 | limited_core_grid_test | 43/81 | 24 | 3050.00 | 1.2201 |  |  |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | walk_forward_analysis | 61/81 | 24 | 6550.00 | 1.2890 | 1.0911 | 0.2492 |
| midday_signed_two_sided_impulse_pause_breakout_1400 | limited_core_grid_test | 35/81 | 12 | 1570.00 | 1.0529 |  |  |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | limited_core_grid_test | 0/81 | 0 | -2695.00 | 0.8974 |  |  |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | limited_core_grid_test | 44/81 | 9 | 2300.00 | 1.1070 |  |  |

No rescue attempt is authorized for this NQ transfer.

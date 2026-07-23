# NQ wide-range bar continuation with aggregate orderflow confirmation

Verdict: FAIL.

The campaign passed pre-PnL density but failed the first staged PnL gate. All five variants halted at `limited_core_grid_test`; no monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was reached.

Density: PASS, 45/45 declared entry rows. Minimum full-history density 140.62/year; minimum limited-core density 134.29/year; minimum latest-window count 118.

Core-grid aggregate: 38/270 profitable combinations, 25 benchmark-passing combinations, 0 Apex-rule-violating iterations.

Best top row: `morning_signed_range_expansion_long` net 5825.00, PF 1.1885, trades 308. This remains a rejection because the variant profitable rate was below the required 70% and later stages were not reached.

| Variant | Profitable combos | Benchmark pass | Top net | Top PF | Top trades | Terminal |
|---|---:|---:|---:|---:|---:|---|
| morning_signed_range_expansion_long | 29/54 | 23 | 5825.00 | 1.1885 | 308 | limited_core_grid_test |
| morning_signed_range_expansion_short | 0/54 | 0 | -4875.00 | 0.6479 | 297 | limited_core_grid_test |
| midday_large10_range_expansion_twosided | 9/54 | 2 | 925.00 | 1.0370 | 301 | limited_core_grid_test |
| afternoon_large20_range_expansion_long | 0/54 | 0 | -2620.00 | 0.7439 | 207 | limited_core_grid_test |
| afternoon_large20_range_expansion_short | 0/54 | 0 | -2390.00 | 0.8556 | 213 | limited_core_grid_test |

No rescue attempt is authorized for this NQ transfer.

# ES Prior-Session Level Breakout Continuation Rescue Attempt 1

Decision: FAIL.

Scope: one rescue per failed variant. Rescues changed only parameter space or fixed parameter values inside the same `pdh_pdl_breakout_continuation`, `percent_from_entry`, and `fixed_r` modules. Timeframe, data window, costs, fill assumptions, and forced-flatten rules were unchanged.

| Variant | Terminal stage | Profitable/monkey pct | Median net | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `gap_hold_two_sided_continuation` | `limited_core_grid_test` | 0.654320987654321 |  | 3212.5 | 1.2634276342763429 | 115 |
| `midday_two_sided_close_break` | `limited_monkey_test` | 0.2866666666666667 | -381.25 | 611.25 | 2.096412556053812 | 9 |
| `morning_prior_high_breakout_long` | `limited_monkey_test` | 0.3466666666666667 | -461.25 | 2463.75 | 3.074736842105263 | 21 |
| `morning_prior_low_breakout_short` | `limited_monkey_test` | 0.2 | -958.75 | 2920.0 | 1.5060658578856152 | 36 |
| `retest_hold_two_sided_breakout` | `limited_monkey_test` | 0.25 | -1643.75 | 3697.5 | 1.6561668145519077 | 38 |

No rescue reached WFA, Monte Carlo, or frozen validation. No second rescue is permitted for these variants.

# ES Prior-Session Level Breakout Continuation Campaign Summary

Decision: FAIL.

All five original variants and all five one-time parameter-space-only rescues failed before WFA. No run reached Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Core profitable pct | Monkey profitable pct | Median net | Top net | Top PF | Top trades |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gap_hold_two_sided_continuation` | `run1` | `limited_core_grid_test` | 0.4444444444444444 |  |  | 3076.25 | 1.2983753637245392 | 116 |
| `midday_two_sided_close_break` | `run1` | `limited_core_grid_test` | 0.5185185185185185 |  |  | 442.5 | 1.7937219730941705 | 9 |
| `morning_prior_high_breakout_long` | `run1` | `limited_core_grid_test` | 0.691358024691358 |  |  | 2231.25 | 2.5494791666666665 | 25 |
| `morning_prior_low_breakout_short` | `run1` | `limited_core_grid_test` | 0.38271604938271603 |  |  | 1957.5 | 1.4264705882352942 | 36 |
| `retest_hold_two_sided_breakout` | `run1` | `limited_core_grid_test` | 0.14814814814814814 |  |  | 1176.25 | 1.307516339869281 | 31 |
| `gap_hold_two_sided_continuation` | `rescue1` | `limited_core_grid_test` | 0.654320987654321 |  |  | 3212.5 | 1.2634276342763429 | 115 |
| `midday_two_sided_close_break` | `rescue1` | `limited_monkey_test` | 0.7037037037037037 | 0.2866666666666667 | -381.25 | 611.25 | 2.096412556053812 | 9 |
| `morning_prior_high_breakout_long` | `rescue1` | `limited_monkey_test` | 1.0 | 0.3466666666666667 | -461.25 | 2463.75 | 3.074736842105263 | 21 |
| `morning_prior_low_breakout_short` | `rescue1` | `limited_monkey_test` | 0.8888888888888888 | 0.2 | -958.75 | 2920.0 | 1.5060658578856152 | 36 |
| `retest_hold_two_sided_breakout` | `rescue1` | `limited_monkey_test` | 0.7530864197530864 | 0.25 | -1643.75 | 3697.5 | 1.6561668145519077 | 38 |

No candidate_strategy_report.md was created because no variant passed.

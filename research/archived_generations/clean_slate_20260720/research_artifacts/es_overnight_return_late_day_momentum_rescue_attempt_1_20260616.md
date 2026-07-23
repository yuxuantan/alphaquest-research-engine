# ES Overnight Return Late-Day Momentum Rescue Attempt 1

Decision: FAIL.

Scope: one rescue per failed variant. Rescues changed only parameter space or fixed parameter values inside the same `overnight_return_late_day_momentum`, `percent_from_entry`, and `fixed_r` modules. Signal clock, timeframe, data window, costs, fill assumptions, and forced-flatten rules were unchanged.

| Variant | Terminal stage | Core profitable pct | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: |
| `negative_overnight_short_1530` | `limited_core_grid_test` | 0.0 | -2312.5 | 0.7207125603864735 | 100 |
| `opening_reversal_confirmed_1530` | `limited_core_grid_test` | 0.0 | -630.0 | 0.8258465791292329 | 61 |
| `penultimate_alignment_1530` | `limited_core_grid_test` | 0.0 | -80.0 | 0.9789196310935442 | 36 |
| `positive_overnight_long_1530` | `limited_core_grid_test` | 0.0 | -1865.0 | 0.6122661122661123 | 98 |
| `two_sided_overnight_sign_continuation_1530` | `limited_core_grid_test` | 0.0 | -4370.0 | 0.5378106821787414 | 174 |

No rescue reached monkey, WFA, Monte Carlo, or frozen validation. No second rescue is permitted for these variants.

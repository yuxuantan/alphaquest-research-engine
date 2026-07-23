# ES VPIN Toxicity Continuation Rescue Attempt 1

Decision: FAIL.

Scope: one rescue per failed variant. Rescues changed only parameter space or fixed parameter values inside the same `vpin_toxicity_continuation`, `percent_from_entry`, and `fixed_r` modules. Signal clock, timeframe, data window, costs, fill assumptions, and forced-flatten rules were unchanged.

| Variant | Terminal stage | Profitable/monkey pct | Median net | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `baseline_high_toxicity_positive_ret_long_1330` | `limited_core_grid_test` | 0.4567901234567901 |  | 1355.0 | 1.2669950738916256 | 64 |
| `drawdown_rank_confirmed_long_1330` | `limited_core_grid_test` | 0.5308641975308642 |  | 1935.0 | 1.4211099020674647 | 68 |
| `extreme_toxicity_positive_ret_long_1330` | `limited_core_grid_test` | 0.5925925925925926 |  | 1707.5 | 1.4164634146341464 | 56 |
| `fast_bucket_toxicity_long_1330` | `limited_core_grid_test` | 0.012345679012345678 |  | 17.5 | 1.0027777777777778 | 74 |
| `slow_bucket_toxicity_long_1330` | `limited_monkey_test` | 0.17666666666666667 | -1856.25 | 3212.5 | 3.089430894308943 | 35 |

No rescue reached WFA, Monte Carlo, or frozen validation. No second rescue is permitted for these variants.

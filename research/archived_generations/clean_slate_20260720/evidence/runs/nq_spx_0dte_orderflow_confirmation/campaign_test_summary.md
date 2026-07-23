# Campaign Test Summary: nq_spx_0dte_orderflow_confirmation

Decision: FAIL

All five frozen SPX 0DTE/orderflow-confirmation variants failed limited_core_grid_test. None reached monkey, WFA, Monte Carlo, or simulated incubation.

| Variant | Terminal stage | Profitable combos | Benchmark-pass combos | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|---:|---:|
| `all_available_1400_signed60_continue` | limited_core_grid_test | 0/81 | 0/81 | -100.0 | 0.7701149425287356 | 7 |
| `all_available_1430_signed60_continue` | limited_core_grid_test | 15/81 | 0/81 | 227.5 | 1.4595959595959596 | 8 |
| `all_available_1430_signed120_continue` | limited_core_grid_test | 30/81 | 0/81 | 205.0 |  | 1 |
| `all_available_1500_signed60_continue` | limited_core_grid_test | 0/81 | 0/81 | 0.0 | 0.0 | 0 |
| `all_available_1515_signed120_continue` | limited_core_grid_test | 3/81 | 0/81 | 165.0 |  | 1 |

Failure reason: zero benchmark-pass combinations across every predeclared variant; best latest-slice profits were too sparse and small to justify robustness testing.

No `candidate_strategy_report.md` was created.

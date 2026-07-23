# ES Cboe SKEW Tail Risk Rescue Attempt 1 - 2026-06-17

Decision: FAIL

All five original Cboe SKEW tail-risk variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue preserving the same Cboe prior-close feature construction, setup mode, direction, entry time, modules, data, costs, session rules, prop rules, and validation gates. All five rescues also failed limited_core_grid_test. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `high_skew_short_1000` | `run1` | 0.07407407407407407 | 0 | 565.0 | 1.0800283286118981 | 87 |
| `low_skew_long_1030` | `run1` | 0.0 | 0 | -4150.0 | 0.5860349127182045 | 155 |
| `rising_skew_short_1130` | `run1` | 0.0 | 0 | -3627.5 | 0.5927589110300309 | 103 |
| `falling_skew_long_1200` | `run1` | 0.0 | 0 | -1272.5 | 0.8865611767327836 | 107 |
| `persistent_high_skew_short_1330` | `run1` | 0.0 | 0 | -1311.25 | 0.7474723158401541 | 56 |
| `high_skew_short_1000` | `rescue1` | 0.14814814814814814 | 0 | 565.0 | 1.0800283286118981 | 87 |
| `low_skew_long_1030` | `rescue1` | 0.0 | 0 | -3617.5 | 0.6019257221458046 | 171 |
| `rising_skew_short_1130` | `rescue1` | 0.0 | 0 | -4541.25 | 0.42841409691629956 | 122 |
| `falling_skew_long_1200` | `rescue1` | 0.0 | 0 | -1518.125 | 0.8705499893412918 | 138 |
| `persistent_high_skew_short_1330` | `rescue1` | 0.0 | 0 | -1598.75 | 0.7128423888639426 | 66 |

Rescue governance: the rescue changed only adjacent SKEW threshold parameter space and stop/target parameter space. It did not change Cboe prior-close availability, setup mode, direction, entry time, modules, data, costs, fill assumptions, session rules, prop rules, or stage gates.

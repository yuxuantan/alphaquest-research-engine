# ES Cboe VIX Term Structure Rescue Attempt 1 - 2026-06-17

Decision: FAIL

All five original Cboe VIX term-structure variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue preserving the same Cboe prior-close feature construction, setup mode, direction, entry time, modules, data, costs, session rules, prop rules, and validation gates. All five rescues also failed limited_core_grid_test. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `backwardation_short_1000` | `run1` | 0.0 | 0 | -2111.25 | 0.8693533415841584 | 101 |
| `contango_long_1030` | `run1` | 0.07407407407407407 | 0 | 180.0 | 1.012591815320042 | 119 |
| `front_stress_short_1130` | `run1` | 0.0 | 0 | -2387.5 | 0.8306437311580067 | 95 |
| `curve_flattening_short_1200` | `run1` | 0.037037037037037035 | 0 | 95.0 | 1.004823559279005 | 131 |
| `backwardation_surge_short_1330` | `run1` | 0.0 | 0 | -1630.0 | 0.8751436231328993 | 111 |
| `backwardation_short_1000` | `rescue1` | 0.0 | 0 | -990.0 | 0.9164380671027643 | 78 |
| `contango_long_1030` | `rescue1` | 0.8888888888888888 | 0 | 2338.75 | 1.1840448554003542 | 111 |
| `front_stress_short_1130` | `rescue1` | 0.0 | 0 | -311.875 | 0.9751246261216351 | 83 |
| `curve_flattening_short_1200` | `rescue1` | 0.7037037037037037 | 0 | 2997.5 | 1.1856899488926746 | 123 |
| `backwardation_surge_short_1330` | `rescue1` | 0.0 | 0 | -1090.0 | 0.8827641839204087 | 78 |

Rescue governance: each rescue changed only adjacent VIX term-structure rank threshold parameter space and stop/target parameter space. It did not change Cboe prior-close availability, setup mode, direction, entry time, modules, data, costs, fill assumptions, session rules, prop rules, or stage gates.

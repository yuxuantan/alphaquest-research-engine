# ES Cboe VIX Level State Rescue Attempt 1 - 2026-06-17

Decision: FAIL

All five original Cboe VIX level/change variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue preserving the same Cboe prior-close feature construction, setup mode, direction, entry time, modules, data, costs, session rules, prop rules, and validation gates. All five rescues also failed limited_core_grid_test. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `high_vix_rebound_long_1000` | `run1` | 0.0 | 0 | -3672.5 | 0.6185406387951181 | 117 |
| `low_vix_complacency_short_1030` | `run1` | 0.0 | 0 | -5365.0 | 0.6535356796900226 | 148 |
| `vix_spike_riskoff_short_1130` | `run1` | 0.14814814814814814 | 0 | 1212.5 | 1.0590383444917832 | 165 |
| `vix_crush_rebound_long_1200` | `run1` | 0.0 | 0 | -2375.0 | 0.8348687641230662 | 165 |
| `persistent_high_vix_long_1330` | `run1` | 0.0 | 0 | -1662.5 | 0.8963851667186039 | 115 |
| `high_vix_rebound_long_1000` | `rescue1` | 0.0 | 0 | -3006.25 | 0.6432809255413824 | 90 |
| `low_vix_complacency_short_1030` | `rescue1` | 0.0 | 0 | -3090.0 | 0.7349914236706689 | 118 |
| `vix_spike_riskoff_short_1130` | `rescue1` | 0.5555555555555556 | 0 | 2618.75 | 1.1243766326288294 | 165 |
| `vix_crush_rebound_long_1200` | `rescue1` | 0.0 | 0 | -962.5 | 0.9518810148731408 | 165 |
| `persistent_high_vix_long_1330` | `rescue1` | 0.0 | 0 | -160.0 | 0.9899323580305175 | 127 |

Rescue governance: each rescue changed only adjacent VIX rank/change threshold parameter space and stop/target parameter space. It did not change Cboe prior-close availability, setup mode, direction, entry time, modules, data, costs, fill assumptions, session rules, prop rules, or stage gates.

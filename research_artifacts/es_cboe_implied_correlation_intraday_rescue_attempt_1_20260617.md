# ES Cboe Implied Correlation Rescue Attempt 1 - 2026-06-17

Decision: FAIL

All five original Cboe implied-correlation variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue preserving the same Cboe prior-close feature construction, setup mode, direction, entry time, modules, data, costs, session rules, prop rules, and validation gates. All five rescues also failed limited_core_grid_test. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `high_cor3m_short_1000` | `run1` | 0.0 | 0 | -1697.5 | 0.9257274119448698 | 147 |
| `low_cor3m_long_1030` | `run1` | 0.037037037037037035 | 0 | 185.0 | 1.0284396617986165 | 58 |
| `rising_cor3m_short_1130` | `run1` | 0.0 | 0 | -3055.0 | 0.8416072585871679 | 126 |
| `falling_cor3m_long_1200` | `run1` | 0.07407407407407407 | 0 | 813.75 | 1.0636737089201878 | 116 |
| `high_short_term_correlation_short_1330` | `run1` | 0.2222222222222222 | 0 | 1980.0 | 1.1112984822934233 | 144 |
| `high_cor3m_short_1000` | `rescue1` | 0.0 | 0 | -4347.5 | 0.7240120615775274 | 162 |
| `low_cor3m_long_1030` | `rescue1` | 0.07407407407407407 | 0 | 438.125 | 1.0688334642576591 | 58 |
| `rising_cor3m_short_1130` | `rescue1` | 0.0 | 0 | -4142.5 | 0.6298860844315389 | 136 |
| `falling_cor3m_long_1200` | `rescue1` | 0.2962962962962963 | 0 | 1432.5 | 1.1154078549848943 | 116 |
| `high_short_term_correlation_short_1330` | `rescue1` | 0.9259259259259259 | 0 | 2656.25 | 1.1317747736574475 | 150 |

Rescue governance: the rescue changed only adjacent implied-correlation threshold parameter space and stop/target parameter space. It did not change Cboe prior-close availability, setup mode, direction, entry time, modules, data, costs, fill assumptions, session rules, prop rules, or stage gates.

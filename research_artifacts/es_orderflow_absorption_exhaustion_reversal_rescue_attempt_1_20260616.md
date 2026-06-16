# ES Orderflow Absorption Exhaustion Reversal Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL.

Scope: one rescue for each failed variant. Rescue changed only fixed parameters and declared parameter space inside the same modules; it did not alter the edge thesis, timeframe, data window, costs, fills, or validation gates.

| Variant | Run | Terminal stage | Core profitable rate | Monkey profitable rate | Median net | Top net | Top trades |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `early_5m_absorption_fade_1000` | `run1` | `limited_core_grid_test` | 0.6666666666666666 |  |  | 1932.5 | 16 |
| `early_5m_absorption_fade_1000` | `rescue1` | `limited_core_grid_test` | 0.3950617283950617 |  |  | 917.5 | 14 |
| `late_morning_15m_absorption_fade_1130` | `run1` | `limited_monkey_test` | 0.9382716049382716 | 0.25 | -190.0 | 931.25 | 10 |
| `late_morning_15m_absorption_fade_1130` | `rescue1` | `limited_core_grid_test` | 0.6296296296296297 |  |  | 772.5 | 13 |
| `midday_30m_absorption_fade_1230` | `run1` | `limited_core_grid_test` | 0.0 |  |  | -98.75 | 6 |
| `midday_30m_absorption_fade_1230` | `rescue1` | `limited_core_grid_test` | 0.0 |  |  | -192.5 | 6 |
| `afternoon_60m_absorption_fade_1400` | `run1` | `limited_core_grid_test` | 0.0 |  |  | -2.5 | 3 |
| `afternoon_60m_absorption_fade_1400` | `rescue1` | `limited_core_grid_test` | 0.012345679012345678 |  |  | 15.0 | 2 |
| `late_30m_absorption_fade_1500` | `run1` | `limited_core_grid_test` | 0.0 |  |  | -60.0 | 2 |
| `late_30m_absorption_fade_1500` | `rescue1` | `limited_core_grid_test` | 0.25925925925925924 |  |  | 117.5 | 4 |

No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.

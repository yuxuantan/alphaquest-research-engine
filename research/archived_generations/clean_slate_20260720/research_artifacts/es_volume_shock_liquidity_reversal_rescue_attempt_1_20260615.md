# ES Volume-Shock Liquidity Reversal Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

Rescue scope: per failed variant. The rescue changed only fixed parameter defaults and declared parameter grids inside the existing `volume_conditioned_liquidity_reversal`, `percent_from_entry`, and `fixed_r` modules. It did not change timeframe, data window, source edge, stage gates, or execution assumptions.

| Variant | Run1 profitable combos | Rescue1 profitable combos | Rescue1 top net | Rescue1 top PF | Rescue1 top trades | Rescue1 best-day concentration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `all_day_symmetric_shock_reversion` | 0.0 | 0.024691358024691357 | 397.5 | 1.1079429735234216 | 33 | 0.6477987421383647 |
| `morning_down_shock_reversal_long` | 0.06172839506172839 | 0.1728395061728395 | 1257.5 | 2.3933518005540164 | 11 | 0.3240556660039761 |
| `morning_up_shock_reversal_short` | 0.04938271604938271 | 0.08641975308641975 | 2167.5 | 1.3681528662420381 | 29 | 0.510957324106113 |
| `midday_symmetric_shock_reversion` | 0.024691358024691357 | 0.20987654320987653 | 1866.25 | 3.2759146341463414 | 13 | 0.2116543871399866 |
| `afternoon_symmetric_shock_reversion` | 0.037037037037037035 | 0.06172839506172839 | 1770.0 | 1.386252045826514 | 36 | 0.2725988700564972 |

Conclusion: no candidate reached monkey, WFA, Monte Carlo, or frozen validation. The best rescue rate was `0.20987654320987653`, far below the `0.70` core-grid gate and with only `13` top-row trades.

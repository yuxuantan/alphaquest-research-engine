# NQ Sector-Rotation Risk-Appetite Intraday - Campaign Summary

Verdict: FAIL

Four NQ sector-rotation risk-appetite variants failed the limited core grid. `growth_lead_long_1030` passed core but failed the limited monkey/randomized schedule gate, with only 28.6125% profitable randomized schedules and negative median randomized net. No variant reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Core rate | Top net | Top PF | Top trades | Top MAR | Monkey profitable |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| cyclical_lead_long_1000 | limited_core_grid_test | 0/27 | 0.0 | -30.0 | 0.997156 | 133 | -0.008303 |  |
| defensive_lead_short_1000 | limited_core_grid_test | 0/27 | 0.0 | -1710.0 | 0.808081 | 157 | -0.502629 |  |
| defensive_rotation_short_1130 | limited_core_grid_test | 6/27 | 0.222222 | 3715.0 | 1.24958 | 144 | 1.724353 |  |
| growth_acceleration_long_1330 | limited_core_grid_test | 0/27 | 0.0 | -835.0 | 0.884028 | 110 | -0.289516 |  |
| growth_lead_long_1030 | limited_monkey_test | 23/27 | 0.851852 | 1875.0 | 1.177221 | 129 | 0.792253 | 0.286125 |

No rescue was authorized or used.

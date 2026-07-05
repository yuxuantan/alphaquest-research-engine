# NQ Productivity Unit Labor Cost State Methodology Audit

Date: 2026-07-01

Final verdict: FAIL

## Density Repair

The initial productivity 4Q strength/weakness variants failed pre-PnL density. Before any NQ PnL was inspected, the final variant set was repaired to one-quarter productivity weakness plus productivity-minus-unit-labor-cost and unit-labor-cost expressions. The final audit passed 45/45 declared density rows.

## Staged Validation

All five variants failed limited_core_grid_test with 0/27 profitable combinations each. No branch reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Profitable Rate | Benchmark Passing | Top Net | Top PF | Top Trades |
|---|---|---:|---:|---:|---:|---:|
| productivity_minus_ulc_4q_pressure_short_1000 | limited_core_grid_test | 0.000000 | 0/27 | -2397.5 | 0.8922955974842768 | 242 |
| productivity_1q_weakness_short_1030 | limited_core_grid_test | 0.000000 | 0/27 | -312.5 | 0.9883893739550437 | 241 |
| unit_labor_cost_4q_pressure_short_1130 | limited_core_grid_test | 0.000000 | 0/27 | -1730.0 | 0.9206785878037598 | 180 |
| unit_labor_cost_1q_relief_long_1200 | limited_core_grid_test | 0.000000 | 0/27 | -3305.0 | 0.8220247711362413 | 203 |
| productivity_minus_ulc_4q_margin_long_1330 | limited_core_grid_test | 0.000000 | 0/27 | -1125.0 | 0.8198558847077662 | 83 |

## Downstream Gates

Not reached because all five variants failed limited_core_grid_test. No rescue was authorized.

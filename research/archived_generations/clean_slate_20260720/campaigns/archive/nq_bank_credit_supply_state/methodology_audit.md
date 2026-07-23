# NQ Bank Credit Supply State Methodology Audit

Date: 2026-07-01

Final verdict: FAIL

## Density Audit

The final pre-PnL density audit passed 45/45 declared rows. No PnL was inspected before freezing the five variants.

## Frozen Mechanics

Each variant reads only the latest Federal Reserve/FRED H.8 observation available on or before `session_date - 14 calendar days`. Each signal uses the completed one-minute RTH bar immediately before the configured decision time and is intended for next-bar-open execution.

## Staged Validation

Four variants failed limited_core_grid_test. `high_loans_leases_growth_long_1030` passed limited core with 22/27 profitable combinations and 10/27 benchmark-passing combinations but failed limited_monkey_test because both the net-profit and max-drawdown beat rates were below the 0.90 gate.

| Variant | Terminal Stage | Profitable Rate | Benchmark Passing | Top Net | Top PF | Top Trades | Monkey Net Beat | Monkey DD Beat |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| high_bank_credit_growth_long_1000 | limited_core_grid_test | 0.000000 | 0/27 | -2465.0 | 0.8324838600067958 | 137 |  |  |
| high_loans_leases_growth_long_1030 | limited_monkey_test | 0.814815 | 10/27 | 2545.0 | 1.1696666666666666 | 145 | 0.800625 | 0.800125 |
| high_ci_loans_growth_long_1130 | limited_core_grid_test | 0.518519 | 9/27 | 3287.5 | 1.1571838393497489 | 201 |  |  |
| high_deposits_growth_long_1200 | limited_core_grid_test | 0.000000 | 0/27 | -1550.0 | 0.8620382732532266 | 130 |  |  |
| high_total_assets_growth_long_1330 | limited_core_grid_test | 0.000000 | 0/27 | -1217.5 | 0.875 | 125 |  |  |

## Downstream Gates

Not reached. No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized.

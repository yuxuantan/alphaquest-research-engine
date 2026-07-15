# Methodology Audit: NQ/ES Relative-Value Orderflow Absorption Reversion

Decision: FAIL

## Pre-Test Controls

- Campaign has exactly five variants.
- Each variant uses the same declared grid: `entry.params.min_spread_bps` [4, 6, 8], `entry.params.min_absorption_imbalance` [0.0, 0.005, 0.01], `sl.params.stop_pct` [0.0025, 0.004, 0.006], and `tp.params.target_r_multiple` [1.0, 1.5, 2.0].
- Parameter count is within policy: 2 entry parameters, 1 stop parameter, 1 target parameter, 81 combinations per variant.
- Pre-PnL density counted only entry-condition sessions. No PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected before freezing the grid.
- Signals use completed one-minute bars and enter no earlier than the next bar open.
- Dataset: `data/cache/orderflow/nq_es_lead_lag_1m_20110103_20260609_full_rth_ny.parquet`.

## Results

All variants failed `limited_core_grid_test`.

| Variant | Terminal stage | Profitable combos | Benchmark combos | Best net | Best PF | Best MAR |
|---|---|---:|---:|---:|---:|---:|
| late_morning30_two_sided_absorption_1130 | limited_core_grid_test | 0/81 | 0 | -4010.00 | 0.814 | -0.401 |
| midday60_two_sided_absorption_1400 | limited_core_grid_test | 1/81 | 0 | 167.50 | 1.010 | 0.029 |
| morning15_two_sided_absorption_1000 | limited_core_grid_test | 0/81 | 0 | -1437.50 | 0.940 | -0.368 |
| morning30_outperform_absorption_short_1030 | limited_core_grid_test | 0/81 | 0 | -1165.00 | 0.932 | -0.275 |
| morning30_underperform_absorption_long_1030 | limited_core_grid_test | 6/81 | 0 | 612.50 | 1.085 | 0.230 |

## Verdict

FAIL. The NQ execution-leg mirror of the ES/NQ absorption edge did not show enough robust core profitability to justify monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No rescue was run because no rescue was explicitly authorized.

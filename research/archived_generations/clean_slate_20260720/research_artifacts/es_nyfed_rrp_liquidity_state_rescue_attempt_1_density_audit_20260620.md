# es_nyfed_rrp_liquidity_state rescue attempt 1 density audit - 2026-06-20

Scope: PnL-free signal-density check for the one allowed parameter-space rescue after all five original variants failed `limited_core_grid_test`.

Data: `data/external/nyfed_rrp_liquidity_state_lag1_features_20140811_20260529.csv`.

Feature: `reverserepo_total_bil_diff5_z504`, shifted one listed `trade_date` before strategy use.

Full valid feature window: 2014-08-11 through 2026-05-29.

Seeded limited-core window used for density screening: 2014-09-30 through 2015-12-04.

Rescue rule:
- Short RRP-drain variants keep the same prior-day RRP-drain mechanic and use stricter thresholds `[0.125, 0.25, 0.375]`.
- Long RRP-release variants keep the same prior-day RRP-release mechanic and use stricter thresholds `[-0.25, -0.375, -0.5]`.
- Stop and target modules are unchanged.
- TP grid is unchanged at `[1.0, 1.5, 2.0]`; sub-1.0R targets are forbidden.

PnL-free density result:
- Drain grid minimum: `>= 0.375` produced `708` full-window sessions, `60.0` annualized signals/year, and `89` limited-core sessions, `75.6` annualized signals/year.
- Release grid minimum: `<= -0.5` produced `628` full-window sessions, `53.2` annualized signals/year, and `111` limited-core sessions, `94.3` annualized signals/year.

Decision: density acceptable for rescue testing. No PnL, trade log, equity curve, or outcome statistic was used to choose the rescue density cutoffs beyond the already-authorized same-mechanic rescue rationale from the failed original core grids.

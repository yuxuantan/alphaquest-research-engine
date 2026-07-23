# NQ Variance-Ratio Orderflow Regime Methodology Audit

Verdict: FAIL.

## Scope

Five predeclared NQ variants tested rolling completed-bar variance-ratio serial dependence with aggregate orderflow confirmation. The campaign used local NQ Sierra RTH 1-minute orderflow bars prepared to 5-minute strategy bars, next-bar-open execution, one-tick slippage, commissions, and forced same-day flattening.

## No-Lookahead Controls

- Variance ratio uses only completed in-session 5-minute closes through the signal bar.
- Orderflow confirmation uses only completed aggregate signed-volume fields through the signal bar.
- Entry occurs at the next bar open through the existing engine.
- No future high/low, final VWAP, final range, or post-entry orderflow is used.

## Density

Initial pre-PnL density failed for sparse flow-threshold corners. Before inspecting NQ PnL, only the affected `entry.params.min_orderflow_imbalance` grids were lowered; VR thresholds, directions, sessions, stops, targets, costs, and gates were unchanged. The final density audit passed for all 45 entry-grid combinations.

## Stage Result

All five variants failed limited_core_grid_test. Best profitable-rate was morning_high_vr_signed_continuation_1130 at 26/81 (0.32098765432098764), below the 0.70 gate. Across all official variants, 46/405 combinations were profitable, 9 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

No candidate strategy report was created.

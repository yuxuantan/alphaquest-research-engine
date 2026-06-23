# NQ SPX 0DTE Orderflow Confirmation Density Audit

Signal-count only; no PnL, stops, targets, WFA, or trade outcomes inspected. Signals require deterministic SPX 0DTE calendar membership, completed NQ open-to-signal move, and completed NQ rolling signed-flow alignment at the signal close. Final pre-PnL grid: `min_abs_move_ticks=[100, 140, 180]`, `min_orderflow_imbalance=[0.0, 0.0025, 0.005]`.

## Variant Density

- `all_available_1430_signed120_continue`: PASS; min/median/max density = 38.15/46.05/56.16 per year.
- `all_available_1430_signed60_continue`: PASS; min/median/max density = 37.63/44.63/53.96 per year.
- `all_available_1500_signed60_continue`: PASS; min/median/max density = 38.60/45.60/55.25 per year.
- `full_week_1430_signed60_continue`: FAIL_DENSITY; min/median/max density = 25.00/28.43/32.32 per year.
- `mwf_1430_signed60_continue`: FAIL_DENSITY; min/median/max density = 26.17/31.67/39.38 per year.

CSV: `research_artifacts/nq_spx_0dte_orderflow_confirmation_density_audit_20260623.csv`

# ES Intraday Periodicity Orderflow Confirmation - Rescue Attempt 1

Scope: one parameter-space/fixed-parameter rescue for each failed variant. No entry, stop, target, slot, source-window, flow-mode, data, cost, fill, session, or benchmark mechanics were changed.

Declared changes before rescue PnL:
- `entry.params.min_mean_return_bps`: `0.5` -> `0.75`.
- `sl.params.stop_pct`: `[0.001, 0.0015, 0.0025]` -> `[0.0015, 0.0025, 0.0035]`.
- `tp.params.target_r_multiple`: `[0.75, 1.0, 1.25]` -> `[1.0, 1.25, 1.5]`.

Pre-PnL density artifact: `research_artifacts/es_intraday_periodicity_orderflow_confirmation_rescue_attempt_1_density_audit_20260618.md`.

Result: FAIL. Best rescue was `morning_1030_large10_confirmed_slot` with 29/81 profitable combinations, below the 70% profitable-combination gate.

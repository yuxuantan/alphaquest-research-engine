# ES Opening-Range NQ Orderflow Breakout Rescue Attempt 1

Date: 2026-06-19

Scope: one allowed rescue for each of the five failed original variants.

Allowed change used: fixed-parameter narrowing to long-only continuation (`allow_long: true`, `allow_short: false`).

Forbidden changes avoided: entry module unchanged, stop module unchanged, target module unchanged, data unchanged, costs/fills/sessions unchanged, validation gates unchanged, no reversal mechanic added.

Pre-PnL rescue density audit: `research_artifacts/es_opening_range_nq_orderflow_breakout_rescue1_density_audit_20260619.md` (PASS).

Outcome: FAIL.

All five rescues failed `limited_core_grid_test` with `0/81` profitable combinations. No rescue reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best rescue: `or30_nq15_signed_breakout_1030/rescue1`, top net `-33.75`, PF `0.9974446337308348`, trades/year `66.94298699790177`.

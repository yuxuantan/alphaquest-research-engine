# es_credit_etf_orderflow_risk_appetite Campaign Test Summary

Decision: FAIL

All five original variants failed limited core. All five failed variants received exactly one parameter-space-only rescue. TP was not adjusted because every `target_r_multiple` was already at least `1.0R`; no sub-1R target exists in the original or rescue grids.

Best original: `hyg_5d_two_sided_signed_1230/run1` with profitable-combo rate `0.38271604938271603`, benchmark-passing combinations `20/81`, top net `5110.0`, PF `1.3108272506082725`, MAR `2.0618137299161363`, trades/year `95.82478051356526`.

Best rescue: `hyg_5d_two_sided_signed_1230/rescue1` with profitable-combo rate `0.8765432098765432`, benchmark-passing combinations `54/81`, top net `6447.5`, PF `1.369696100917431`, MAR `2.7739748230950885`, trades/year `95.8216178751774`.

The strongest rescue by progression was `hyg_3d_two_sided_signed_1230/rescue1`: it passed limited core and limited monkey, then failed WFA with stitched OOS PF `1.077365644773513`, MAR `0.08981641818942494`, trades/year `68.54306003101846`, and net profit `16170.0`. The `hyg_5d_two_sided_signed_1230/rescue1` run passed limited core but failed limited monkey/stress because max-drawdown robustness was `0.8766666666666667` against the `0.90` threshold and one-tick-worse net profit was `-405.0`.

Artifacts:

- `campaign_results.csv`
- `trade_logs_manifest.csv`
- `equity_curves_manifest.csv`
- `wfa_table.csv`
- `monte_carlo_summary.csv`

No run reached Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

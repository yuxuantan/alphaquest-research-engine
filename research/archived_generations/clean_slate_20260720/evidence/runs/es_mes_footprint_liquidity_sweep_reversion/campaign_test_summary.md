# es_mes_footprint_liquidity_sweep_reversion campaign summary

Decision: FAIL

All five original variants and all five one-time parameter-space-only rescues failed `limited_core_grid_test`. No run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original: `rolling45_full_session_trade_large10_two_sided/run1` top net `1735.0`, PF `1.188586956521739`, MAR `1.062499316736399`, trades/year `104.12902805877536`, profitable-combo rate `0.3611111111111111`.
Best rescue: `rolling45_full_session_trade_large10_two_sided/rescue1` top net `1872.5`, PF `1.1918053777208706`, MAR `1.1075348899720623`, trades/year `104.12761606699735`, profitable-combo rate `0.5555555555555556`.

TP rule: no tested `target_r_multiple` was below `1.0R`; rescue TP grids were left unchanged because the originals already satisfied the floor.

Artifacts written:
- `campaign_results.csv`
- `trade_logs_manifest.csv`
- `equity_curves_manifest.csv`
- `wfa_table.csv`
- `monte_carlo_summary.csv`
- `monte_carlo_summary.json`

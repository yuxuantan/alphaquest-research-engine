# es_overnight_drift_european_open campaign summary

Decision: FAIL

All five original variants and all five one-time parameter-space-only rescues failed `limited_core_grid_test`. No run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original: `eu_open_down_no_recovery_long_0200/run1` top net `-966.25`, PF `0.6558325912733749`, trades/year `38.06078610603291`, profitable-combo rate `0.0`.
Best rescue: `london_open_prior_down_long_0300/rescue1` top net `-652.5`, PF `0.9037610619469026`, trades/year `58.54904019480725`, profitable-combo rate `0.0`.

Artifacts written:
- `campaign_results.csv`
- `trade_logs_manifest.csv`
- `equity_curves_manifest.csv`
- `wfa_table.csv`
- `monte_carlo_summary.csv`
- `monte_carlo_summary.json`

# es_pivot_filtered_prior_value_area_acceptance Campaign Test Summary

Decision: FAIL

All five original variants and all five allowed stop-widen rescues failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original: `morning_signed_vah_pivot_acceptance_long/run1` with profitable-combo rate `0.5185185185185185`, benchmark-passing combinations `18/54`, top net `2500.0`, PF `1.277623542476402`, MAR `0.7504405175421055`, and trades/year `53.420681774900025`.
Best rescue: `morning_signed_vah_pivot_acceptance_long/stop_widen_rescue1` with profitable-combo rate `0.6111111111111112`, benchmark-passing combinations `18/54`, top net `2500.0`, PF `1.277623542476402`, MAR `0.7504405175421055`, and trades/year `53.420681774900025`.

Fixed-config core trade logs and equity curves were written for all ten runs.

Artifacts:
- `campaign_results.csv`
- `trade_logs_manifest.csv`
- `equity_curves_manifest.csv`
- `wfa_table.csv`
- `monte_carlo_summary.csv`

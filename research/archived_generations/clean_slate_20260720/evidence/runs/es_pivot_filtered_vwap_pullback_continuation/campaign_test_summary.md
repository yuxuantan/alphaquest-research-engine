# es_pivot_filtered_vwap_pullback_continuation Campaign Test Summary

Decision: FAIL

All five original variants and all five allowed stop-widen rescues failed `limited_core_grid_test`; no run reached WFA, monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original: `failed_vwap_break_two_sided_1500/run1` with profitable-combo rate `0.05555555555555555`, benchmark-passing combinations `0/54`, top net `456.25`, PF `1.3732106339468302`, MAR `1.1274897977432308`, and trades/year `19.02619013167414`.
Best rescue: `failed_vwap_break_two_sided_1500/stop_widen_rescue1` with profitable-combo rate `0.16666666666666666`, benchmark-passing combinations `0/54`, top net `1951.25`, PF `1.7476053639846743`, MAR `2.238986671489144`, and trades/year `20.277487289462904`.

Fixed-config core trade logs and equity curves were written for all ten runs.

Artifacts:
- `campaign_results.csv`
- `trade_logs_manifest.csv`
- `equity_curves_manifest.csv`
- `wfa_table.csv`
- `monte_carlo_summary.csv`

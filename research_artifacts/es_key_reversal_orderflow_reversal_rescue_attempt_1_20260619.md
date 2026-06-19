# ES Key Reversal Orderflow Reversal Rescue Attempt 1

Decision: FAIL

Scope: one parameter-space/fixed-parameter rescue per failed original variant.

Preserved mechanics: `key_reversal_orderflow_reversal` entry, `sweep_extreme` stop, `fixed_r` target, local Sierra 1-minute trade-orderflow cache, costs, sessions, next-bar execution, and validation gates.

Changed before rescue PnL: fixed `min_close_location` from 0.6 to 0.7, fixed `min_volume_ratio` from 0.6 to 0.9, fixed stop offset from 2 to 3 ticks, fixed target from 0.75R to 1.0R, stop grid from `[1,2,3]` to `[2,3,4]`, target grid from `[0.5,0.75,1.0]` to `[0.75,1.0,1.25]`.

Pre-PnL rescue density passed for all five variants. Artifact: `research_artifacts/es_key_reversal_orderflow_reversal_rescue1_density_audit_20260619.md`.

All five rescues failed `limited_core_grid_test`; no rescue reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best rescue: `midday_signed_two_sided_key_reversal_1400/rescue1`, top net `-1720.0`, PF `0.7959667852906287`, trades/year `80.48603404398688`, profitable combo rate `0.0`.

Aggregate summary: `backtest-campaigns/es_key_reversal_orderflow_reversal/campaign_test_summary.json`
Results table: `backtest-campaigns/es_key_reversal_orderflow_reversal/campaign_results.csv`

# ES opening-drive VWAP orderflow pullback rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space/fixed-parameter rescue for each failed variant. No entry module, stop module, target module, timeframe, data source, cost model, fill model, stage criteria, or edge thesis was changed.

Original campaign:
- Edge: completed 30- or 60-minute opening-drive direction plus later session-VWAP pullback/reclaim with aligned completed-bar aggregate orderflow.
- Variants: `drive30_signed_pullback_1230`, `drive30_large10_pullback_1230`, `drive30_large20_pullback_1230`, `drive60_signed_pullback_1430`, `drive60_large20_pullback_1430`.
- Pre-PnL density artifact: `research_artifacts/es_opening_drive_vwap_orderflow_pullback_density_audit_20260618.md`.

Original result:
- All five variants failed `limited_core_grid_test`.
- Profitable-combo rate was `0.0` for every original variant.
- No original run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Rescue change:
- Kept the same opening-drive VWAP pullback/reclaim plus aggregate-orderflow mechanic.
- Changed only declared parameter values and the fixed VWAP pullback tolerance inside the same entry module.
- 30-minute variants used `entry.params.min_drive_points = [2.0, 3.0, 4.0]`, `entry.params.min_orderflow_imbalance = [0.0, 0.01, 0.02]`, `sl.params.stop_offset_ticks = [1, 2, 3]`, and `tp.params.target_r_multiple = [0.25, 0.5, 0.75]`.
- 60-minute variants used `entry.params.min_drive_points = [3.0, 4.0, 5.0]`, `entry.params.min_orderflow_imbalance = [0.0, 0.02, 0.04]`, `sl.params.stop_offset_ticks = [1, 2, 3]`, and `tp.params.target_r_multiple = [0.75, 1.0, 1.5]`.
- Each rescue still had `81` combinations.

Rescue result:
- All five rescues failed `limited_core_grid_test`.
- Profitable-combo rate was `0.0` for every rescue.
- Best rescue: `drive30_large20_pullback_1230/rescue1`, top net `-747.5`, PF `0.8987127371273713`, and `60.11494167194664` trades/year.

Decision: FAIL. The edge expression produced enough trades but did not survive costs and pessimistic execution assumptions even before monkey testing or WFA.

Primary artifacts:
- `backtest-campaigns/es_opening_drive_vwap_orderflow_pullback/campaign_test_summary.json`
- `backtest-campaigns/es_opening_drive_vwap_orderflow_pullback/campaign_results.csv`
- `backtest-campaigns/es_opening_drive_vwap_orderflow_pullback/wfa_table.csv`
- `backtest-campaigns/es_opening_drive_vwap_orderflow_pullback/monte_carlo_summary.json`

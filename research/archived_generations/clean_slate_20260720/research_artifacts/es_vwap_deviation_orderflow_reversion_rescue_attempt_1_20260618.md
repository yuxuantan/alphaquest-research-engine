# ES VWAP deviation orderflow reversion rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space/fixed-parameter rescue for each failed variant. No entry module, stop module, target module, timeframe, data source, cost model, fill model, stage criteria, or edge thesis was changed.

Original campaign:
- Edge: two-sided completed VWAP-deviation reversion with counter-direction aggregate orderflow confirmation.
- Variants: `morning_signed_counterflow_1200`, `morning_large10_counterflow_1200`, `midday_signed_counterflow_1400`, `midday_large20_counterflow_1400`, `afternoon_signed_counterflow_1530`.
- Pre-PnL density artifact: `research_artifacts/es_vwap_deviation_orderflow_reversion_density_audit_20260618.md`.

Original result:
- All five variants failed `limited_core_grid_test`.
- Profitable-combo rate was `0.0` for every original variant.
- No original run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Rescue change:
- Kept the same VWAP-deviation counterflow reversion mechanic.
- Changed only declared threshold, stop, and target parameter values.
- Morning variants used `entry.params.min_vwap_deviation_ticks = [14, 16, 18]`.
- Midday/afternoon variants used `entry.params.min_vwap_deviation_ticks = [16, 20, 24]`.
- All rescue variants used `entry.params.min_counterflow_imbalance = [0.04, 0.06, 0.08]`, `sl.params.stop_offset_ticks = [1, 2, 3]`, and `tp.params.target_r_multiple = [0.25, 0.5, 0.75]`.
- Each rescue still had `81` combinations.

Rescue result:
- All five rescues failed `limited_core_grid_test`.
- Profitable-combo rate was `0.0` for every rescue.
- Best rescue: `midday_signed_counterflow_1400/rescue1`, top net `-1858.75`, PF `0.39882757226601984`, and `60.450316066562436` trades/year.

Decision: FAIL. The edge expression produced enough trades but did not survive costs and pessimistic execution assumptions even before monkey testing or WFA.

Primary artifacts:
- `backtest-campaigns/es_vwap_deviation_orderflow_reversion/campaign_test_summary.json`
- `backtest-campaigns/es_vwap_deviation_orderflow_reversion/campaign_results.csv`
- `backtest-campaigns/es_vwap_deviation_orderflow_reversion/wfa_table.csv`
- `backtest-campaigns/es_vwap_deviation_orderflow_reversion/monte_carlo_summary.json`

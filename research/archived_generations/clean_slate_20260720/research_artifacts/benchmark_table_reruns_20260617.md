# Benchmark-Table Reruns - 2026-06-17

Reason: after aligning staged validation to the benchmark table, rerun active non-archived variants that were plausible false negatives under the prior limited monkey / screening gates. These reruns did not change mechanics, parameter spaces, data, costs, fill assumptions, sessions, or rescue status. Temporary configs changed only `test_run_id`.

## Reruns

| Campaign | Variant | Corrected result | Decision |
|---|---|---|---|
| `es_cboe_implied_correlation_intraday` | `high_short_term_correlation_short_1330` | Limited core passed `25/27` profitable combos; limited monkey passed net/drawdown beat rates `0.9933 / 0.9733`; WFA failed with early exit on window 2, stitched OOS PF `0.7661`, MAR `-0.7309`, expectancy R `-0.0718`. | FAIL |
| `es_cboe_vix_term_structure_intraday` | `curve_flattening_short_1200` | Limited core passed `19/27` profitable combos; limited monkey failed max-drawdown beat rate `0.8733 < 0.90`. | FAIL |
| `es_vwap_pullback_continuation` | `midday_trend_reclaim_two_sided` | Limited core passed `60/81` profitable combos; limited monkey passed net/drawdown beat rates `0.93 / 0.9067`; WFA failed with early exit on window 4, stitched OOS PF `0.8267`, MAR `-0.2015`, expectancy R `-0.0503`. | FAIL |

## Artifacts

- `backtest-campaigns/es_cboe_implied_correlation_intraday/high_short_term_correlation_short_1330/ES/benchmark_table_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_cboe_vix_term_structure_intraday/curve_flattening_short_1200/ES/benchmark_table_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_vwap_pullback_continuation/midday_trend_reclaim_two_sided/ES/benchmark_table_rerun1/campaign_test_summary.json`
- `research_artifacts/benchmark_table_rerun_configs/es_cboe_implied_correlation_high_short_term_correlation_short_1330_benchmark_table_rerun1.yaml`
- `research_artifacts/benchmark_table_rerun_configs/es_cboe_vix_term_structure_curve_flattening_short_1200_benchmark_table_rerun1.yaml`
- `research_artifacts/benchmark_table_rerun_configs/es_vwap_pullback_midday_trend_reclaim_two_sided_benchmark_table_rerun1.yaml`

## Conclusion

The benchmark-table correction did allow some formerly stopped variants to reach WFA, but none produced a candidate strategy. The rerun set remains rejected and should not be promoted to manual review.

# NQ Chart Fanatics Daily Bollinger Environment Density Audit - 2026-06-30

Purpose: count raw entry signals before any PnL inspection.

Method:
- Uses authored configs under `campaigns/nq_chartfanatics_daily_bollinger_environment/variants/*/config.yaml`.
- Expands entry grid only: `width_rank_threshold` x `min_breakout_ticks`.
- Computes daily 20/3 Bollinger state from completed prior RTH sessions and counts deterministic intraday trigger signals; no fills, stops, targets, PnL, WFA, monkey, or Monte Carlo are inspected.

Full window: `2011-01-03` to `2026-06-12`. Limited-core window: `2011-02-22` to `2012-09-07`. Latest window: `2025-06-09` to `2026-06-12`.

| variant_id | entry_combos | combos_passing_all_windows | min_full/y | min_limited/y | min_latest252/y | decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| late_morning_consolidation_prior_edge_fade | 9 | 0 | 28.95 | 25.13 | 28.00 | FAIL |
| morning_expansion_long_or15_breakout | 9 | 0 | 0.00 | 0.00 | 0.00 | FAIL |
| morning_expansion_short_or15_breakdown | 9 | 0 | 0.73 | 2.04 | 0.00 | FAIL |
| morning_lower_band_mean_reversion_long | 9 | 0 | 2.51 | 3.40 | 1.00 | FAIL |
| morning_upper_band_mean_reversion_short | 9 | 0 | 0.13 | 0.00 | 0.00 | FAIL |

CSV detail: `research_artifacts/nq_chartfanatics_daily_bollinger_environment_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_chartfanatics_daily_bollinger_environment_density_summary_20260630.csv`

Final density decision: FAIL. Reject before staged PnL.

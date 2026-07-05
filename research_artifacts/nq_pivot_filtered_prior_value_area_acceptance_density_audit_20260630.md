# NQ Pivot-Filtered Prior Value-Area Acceptance Density Audit - 2026-06-30

Purpose: count raw entry signals before any PnL inspection so sparse parameter spaces are rejected before staged testing rather than interpreted as expectancy evidence.

Method:
- Uses authored configs under `campaigns/nq_pivot_filtered_prior_value_area_acceptance/variants/*/config.yaml`.
- Expands the declared entry grid only: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance`.
- Prepares the same 5-minute NQ RTH orderflow bars as the staged runner with `prepare_data`.
- Counts signals through `MarketStructureFilteredEntry` wrapping `PriorValueAreaOrderflowAcceptanceEntry`; no vectorized shortcut is used for pivot state.
- Does not inspect fills, stops, targets, trade PnL, equity curves, future bars, WFA, monkey tests, or Monte Carlo output.

Full window: `2011-01-03` to `2026-06-12`. Limited-core window: `2011-02-22` to `2012-09-07`. Latest window: latest 252 RTH sessions ending `2026-06-12`.

Density guideline: each variant should have at least one predeclared entry-grid corner above 50 signals/year on the full configured history and limited-core shortlist window before staged testing. Here every retained entry corner is also reported.

| variant_id | entry_combos | combos_passing_all_windows | min_full/y | min_limited/y | min_latest252/y | decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| afternoon_large20_two_sided_pivot_acceptance | 9 | 9 | 109.92 | 106.40 | 102.23 | PASS |
| late_morning_large10_two_sided_pivot_acceptance | 9 | 9 | 128.18 | 120.02 | 118.11 | PASS |
| midday_signed_two_sided_pivot_acceptance | 9 | 9 | 121.45 | 121.97 | 116.13 | PASS |
| morning_signed_two_sided_pivot_acceptance_1230 | 9 | 9 | 106.94 | 103.80 | 93.30 | PASS |
| morning_signed_vah_pivot_acceptance_long | 9 | 9 | 66.46 | 57.74 | 57.57 | PASS |

CSV detail: `research_artifacts/nq_pivot_filtered_prior_value_area_acceptance_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_pivot_filtered_prior_value_area_acceptance_density_summary_20260630.csv`

Final density decision: PASS. Proceed to preflight and staged testing without changing mechanics or parameter space.

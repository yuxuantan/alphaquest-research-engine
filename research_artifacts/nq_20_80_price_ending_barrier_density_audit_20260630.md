# NQ 20/80 Price-Ending Barrier Density Audit - 2026-06-30

Purpose: count raw entry signals before any PnL inspection so sparse parameter spaces are rejected before staged testing rather than interpreted as expectancy evidence.

Method:
- Uses authored configs under `campaigns/nq_20_80_price_ending_barrier/variants/*/config.yaml`.
- Expands the declared entry grid only: `entry.params.base_params.buffer_ticks` x `entry.params.base_params.max_close_distance_ticks`.
- Prepares 5-minute NQ RTH orderflow bars with `prepare_data` for each audit window.
- Precomputes completed 5/15-minute pivot bias once per audit window, then counts signals from `PriceEndingBarrierEntry` and applies the same-direction pivot filter. This is equivalent to `MarketStructureFilteredEntry` for signal counts and avoids repeated pivot recomputation.
- Does not inspect fills, stops, targets, trade PnL, equity curves, future bars, WFA, monkey tests, or Monte Carlo output.

Full window: `2011-01-03` to `2026-06-12`. Limited-core window: `2011-02-22` to `2012-09-07`. Latest window: latest 252 RTH sessions from `2025-06-09` to `2026-06-12`.

Density guideline: each retained entry-grid corner should exceed 50 signals/year on the full configured history, limited-core shortlist window, and latest 252-session window before staged PnL testing.

| variant_id | entry_combos | combos_passing_all_windows | min_full/y | min_limited/y | min_latest252/y | decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| late_morning_20_80_two_sided_reclaim_pivot | 9 | 0 | 57.45 | 28.53 | 88.27 | FAIL |
| morning_20_80_downside_breakout_pivot_short | 9 | 0 | 23.71 | 14.27 | 25.79 | FAIL |
| morning_20_80_resistance_reject_pivot_short | 9 | 0 | 34.46 | 16.21 | 34.71 | FAIL |
| morning_20_80_support_reclaim_pivot_long | 9 | 0 | 43.40 | 24.64 | 56.53 | FAIL |
| morning_20_80_upside_breakout_pivot_long | 9 | 0 | 30.96 | 16.21 | 48.60 | FAIL |

CSV detail: `research_artifacts/nq_20_80_price_ending_barrier_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_20_80_price_ending_barrier_density_summary_20260630.csv`

Final density decision: FAIL. Reject or reformulate before any PnL test; do not run staged testing on sparse grid.

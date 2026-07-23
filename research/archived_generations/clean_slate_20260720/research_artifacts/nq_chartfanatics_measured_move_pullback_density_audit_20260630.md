# NQ Chart Fanatics Measured-Move Pullback Density Audit - 2026-06-30

Purpose: count raw entry signals before any PnL inspection.

Method:
- Uses authored configs under `campaigns/nq_chartfanatics_measured_move_pullback/variants/*/config.yaml`.
- Expands entry grid only: `breakout_buffer_ticks` x `min_measured_move_ticks`.
- Precomputes completed pivot states per configured timeframe set and counts deterministic measured-break signals; no fills, stops, targets, PnL, WFA, monkey, or Monte Carlo are inspected.

Full window: `2011-01-03` to `2026-06-12`. Limited-core window: `2011-02-22` to `2012-09-07`. Latest window: `2025-06-09` to `2026-06-12`.

| variant_id | entry_combos | combos_passing_all_windows | min_full/y | min_limited/y | min_latest252/y | decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| late_morning_15_30_two_sided_measured_continuation | 9 | 6 | 89.77 | 41.50 | 126.95 | FAIL |
| late_morning_5_15_two_sided_measured_continuation | 9 | 6 | 95.21 | 27.89 | 147.78 | FAIL |
| midday_5_15_two_sided_measured_continuation | 9 | 6 | 97.87 | 19.45 | 182.49 | FAIL |
| morning_5_15_long_measured_breakout | 9 | 3 | 47.15 | 14.92 | 78.35 | FAIL |
| morning_5_15_short_measured_breakdown | 9 | 0 | 35.75 | 8.43 | 49.59 | FAIL |

CSV detail: `research_artifacts/nq_chartfanatics_measured_move_pullback_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_chartfanatics_measured_move_pullback_density_summary_20260630.csv`

Final density decision: FAIL. Reject before staged PnL.

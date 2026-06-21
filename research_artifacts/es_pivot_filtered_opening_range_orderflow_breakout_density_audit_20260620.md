# es_pivot_filtered_opening_range_orderflow_breakout Density Audit

Local-only pre-PnL density screen for adding completed 5m/15m swing-pivot market-structure direction filter to the existing opening-range/orderflow breakout edge. No external or paid data was downloaded.

## Windows
- full: `{'start_date': '2011-01-03', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`; years=15.4333
- limited_core: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`; years=1.5414
- wfa90: `{'start_date': '2011-01-03', 'end_date': '2024-11-22', 'session_labels': ['RTH']}`; years=13.8891
- latest1y: `{'start_date': '2025-06-10', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`; years=0.9993

## Pivot Filter
- Strict: 5m and 15m both aligned, no opposing checked timeframe.
- Loose: at least one of 5m/15m aligned and no opposing checked timeframe.
- Pivots use one left and one right completed bucket, zero minimum pivot move, and carry confirmed pivots across sessions.
- The filter is applied to the closed breakout confirmation bar; the staged engine would still enter on the next bar.

## Decision
REJECT_PRE_PNL_DENSITY using `loose` filter: only 1/5 variants keep all entry parameter corners above 50 signals/year. Do not author or PnL-test this composite.

## Strict Summary

| variant_id | passing_entry_combos | entry_combo_count | full_min_signals_per_year | limited_core_min_signals_per_year | wfa90_min_signals_per_year | latest1y_min_signals_per_year | pass |
|---|---:|---:|---:|---:|---:|---:|---|
| or15_signed_flow_breakout_1030 | 0 | 9 | 15.10 | 24.00 | 16.06 | 8.01 | false |
| or30_signed_flow_breakout_1100 | 0 | 9 | 17.82 | 20.76 | 18.36 | 15.01 | false |
| or15_large10_flow_breakout_1030 | 0 | 9 | 20.28 | 24.00 | 20.45 | 23.02 | false |
| or30_large20_flow_breakout_1100 | 0 | 9 | 23.00 | 21.41 | 22.68 | 28.02 | false |
| or60_signed_flow_breakout_1200 | 0 | 9 | 21.06 | 13.62 | 21.74 | 15.01 | false |

## Loose Summary

| variant_id | passing_entry_combos | entry_combo_count | full_min_signals_per_year | limited_core_min_signals_per_year | wfa90_min_signals_per_year | latest1y_min_signals_per_year | pass |
|---|---:|---:|---:|---:|---:|---:|---|
| or15_signed_flow_breakout_1030 | 4 | 9 | 36.74 | 52.55 | 38.52 | 20.01 | false |
| or30_signed_flow_breakout_1100 | 6 | 9 | 40.37 | 49.95 | 42.48 | 24.02 | false |
| or15_large10_flow_breakout_1030 | 9 | 9 | 52.87 | 51.25 | 51.62 | 67.05 | true |
| or30_large20_flow_breakout_1100 | 6 | 9 | 55.72 | 48.66 | 54.29 | 72.05 | false |
| or60_signed_flow_breakout_1200 | 0 | 9 | 43.74 | 25.95 | 45.36 | 33.02 | false |

## Artifacts

- Strict detail: `research_artifacts/es_pivot_filtered_opening_range_orderflow_breakout_density_screen_strict_20260620.csv`
- Strict summary: `research_artifacts/es_pivot_filtered_opening_range_orderflow_breakout_density_summary_strict_20260620.csv`
- Loose detail: `research_artifacts/es_pivot_filtered_opening_range_orderflow_breakout_density_screen_loose_20260620.csv`
- Loose summary: `research_artifacts/es_pivot_filtered_opening_range_orderflow_breakout_density_summary_loose_20260620.csv`

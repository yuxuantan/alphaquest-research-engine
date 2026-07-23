# ES Footprint Absorption Initiation Density Audit

Generated: 2026-06-18

Purpose: pre-PnL check that each final variant can plausibly reach the methodology trade-count gate before any optimization or PnL testing.

Initial reformulation note: isolated one-sided prior-low and prior-high variants were rejected before PnL because they stayed below 50 raw signals/year. The final source set uses two-sided prior-session-extreme and session-open AOI variants instead.

Full data period: 2011-01-03 09:30:00-05:00 to 2026-06-09 15:59:00-04:00 (15.43 years).
Limited-core period resolved by current staged benchmark: 2011-02-22 to 2012-09-06 (1.54 years).

Pass rule for density only: at least one declared entry-parameter combination must produce >= 50 raw one-signal-per-session signals/year on full data and on the current limited-core period. This is not a PnL pass.

| variant_id                                       | tested_entry_combos | max_full_signals_per_year | median_full_signals_per_year | min_full_signals_per_year | max_limited_core_signals_per_year | median_limited_core_signals_per_year | min_limited_core_signals_per_year | combos_full_ge_50 | combos_limited_ge_50 | density_pass |
| ------------------------------------------------ | ------------------- | ------------------------- | ---------------------------- | ------------------------- | --------------------------------- | ------------------------------------ | --------------------------------- | ----------------- | -------------------- | ------------ |
| opening_range_footprint_absorption_retest_1100   | 9                   | 75.81027142096859         | 62.073709419904205           | 42.11681745609366         | 104.44982238010657                | 86.93339253996447                    | 59.685612788632326                | 6                 | 9                    | True         |
| prior_extreme_footprint_absorption_reversal_1500 | 9                   | 78.1428951569984          | 64.14715274081958            | 39.26583288983502         | 71.36323268206039                 | 59.036856127886324                   | 28.545293072824155                | 6                 | 6                    | True         |
| rolling_range_footprint_absorption_sweep_1500    | 9                   | 130.04377328366152        | 118.76942522618414           | 99.33089409260245         | 124.56127886323267                | 122.61500888099467                   | 88.87966252220248                 | 9                 | 9                    | True         |
| round_number_footprint_absorption_rejection_1500 | 9                   | 130.950904736562          | 117.2791378392762            | 93.17535923363491         | 76.55328596802842                 | 69.41696269982238                    | 51.90053285968028                 | 9                 | 9                    | True         |
| session_open_footprint_absorption_reclaim_1500   | 9                   | 116.89036721660457        | 102.95941990420435           | 72.4409260244811          | 120.66873889875666                | 101.85479573712256                   | 66.17317939609237                 | 9                 | 9                    | True         |

Detail CSV: `research_artifacts/es_footprint_absorption_initiation_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_footprint_absorption_initiation_density_summary_20260618.csv`

# ES/NQ Relative-Value Orderflow Absorption Density Audit

Generated: 2026-06-18

Purpose: pre-PnL strict-corner signal-density check for the windowed first-signal formulation.

Limited-core density pass count: 5/5 variants at >= 50 signals/year.

| Variant | Limited start | Limited end | Lookback | Window | Signals | Signals/year | Pass |
|---|---:|---:|---:|---|---:|---:|---|
| late_morning30_two_sided_absorption_1130 | 2011-02-22 | 2012-09-06 | 30 | 11:30:00-12:30:00 | 89 | 57.739343 | True |
| midday60_two_sided_absorption_1400 | 2011-02-22 | 2012-09-06 | 60 | 13:00:00-14:30:00 | 122 | 79.148313 | True |
| morning15_two_sided_absorption_1000 | 2011-02-22 | 2012-09-06 | 15 | 10:00:00-11:00:00 | 137 | 88.879663 | True |
| morning30_outperform_absorption_short_1030 | 2011-02-22 | 2012-09-06 | 30 | 10:30:00-11:30:00 | 88 | 57.090586 | True |
| morning30_underperform_absorption_long_1030 | 2011-02-22 | 2012-09-06 | 30 | 10:30:00-11:30:00 | 83 | 53.846803 | True |

Note: exact-minute draft was rejected before PnL because strict-corner density was below 50/year for all variants.
CSV detail: `research_artifacts/es_nq_relative_value_orderflow_absorption_reversion_density_audit_20260618.csv`
Limited-core summary CSV: `research_artifacts/es_nq_relative_value_orderflow_absorption_reversion_density_summary_20260618.csv`

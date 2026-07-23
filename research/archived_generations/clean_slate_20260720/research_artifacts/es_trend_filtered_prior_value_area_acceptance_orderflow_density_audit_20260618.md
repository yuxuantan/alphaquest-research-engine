# ES Trend-Filtered Prior Value-Area Acceptance Density Audit

Generated: 2026-06-18

Purpose: pre-PnL signal-density check for the strict entry corner of each variant before staged testing.

Strict corner uses the widest breakout buffer and highest orderflow threshold from each declared grid. Stop/target parameters are irrelevant for this signal-only audit.

Limited-core density pass count: 5/5 variants at >= 50 signals/year.

Limited core period is resolved by the staged default random_fraction window: 10% of configured data, avoiding the latest 10% and avoiding 2020-02-01 through 2021-06-30.

| Variant | Limited start | Limited end | Strict flow | Signals | Signals/year | Pass |
|---|---:|---:|---|---:|---:|---|
| afternoon_large20_two_sided_trend_acceptance | 2011-02-22 | 2012-09-06 | large20 | 324 | 210.197158 | True |
| late_morning_large10_two_sided_trend_acceptance | 2011-02-22 | 2012-09-06 | large10 | 312 | 202.412078 | True |
| midday_signed_two_sided_trend_acceptance | 2011-02-22 | 2012-09-06 | signed_volume | 310 | 201.114565 | True |
| morning_signed_vah_trend_acceptance_long | 2011-02-22 | 2012-09-06 | signed_volume | 136 | 88.230906 | True |
| morning_signed_val_trend_acceptance_short | 2011-02-22 | 2012-09-06 | signed_volume | 124 | 80.445826 | True |

CSV detail: `research_artifacts/es_trend_filtered_prior_value_area_acceptance_orderflow_density_audit_20260618.csv`
Limited-core summary CSV: `research_artifacts/es_trend_filtered_prior_value_area_acceptance_orderflow_density_summary_20260618.csv`

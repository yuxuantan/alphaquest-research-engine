# nq_term_structure_lead_lag_feedback Density Audit

Date: 2026-06-30

Decision: FAIL

This is a pre-PnL density audit. It counts only signal availability from completed front-vs-next-contract NQ feature rows. It does not inspect stops, targets, trade outcomes, or equity.

## Gate

- Minimum total signals: 80
- Minimum full-period signals/year: 10.0
- Minimum limited-period signals/year: 10.0
- Limited period: 2011-02-22 to 2012-09-07

## Data

- Feature cache: `data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.parquet`
- Validation: `data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.validation.json`
- Eligible sessions: 164
- Full period: 2010-06-10 to 2026-03-16
- Cache validation: `{'deferred_contracts': 40, 'duplicate_timestamps': 0, 'front_contracts': 40, 'invalid_ohlc_rows': 0, 'missing_session_segments': 0}`

## Best Row Per Variant

| campaign_id | source_campaign_id | variant_id | setup_mode | entry_time | flatten_time | lookback_minutes | allow_long | allow_short | min_front_return_bps | min_spread_gap_bps | full_start_date | full_end_date | eligible_sessions | full_signals | full_signals_per_year | limited_start_date | limited_end_date | limited_signals | limited_signals_per_year | latest_40_eligible_start_date | latest_40_eligible_end_date | latest_40_eligible_signals | density_gate_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nq_term_structure_lead_lag_feedback | es_term_structure_lead_lag_feedback | late_morning_two_sided_spread_feedback_1130 | two_sided_spread_feedback | 11:30:00 | 13:00:00 | 15 | True | True | 4.0 | 0.5 | 2010-06-10 | 2026-03-16 | 164 | 47 | 2.9813737408822507 | 2011-02-22 | 2012-09-07 | 5 | 3.2437833037300177 | 2022-06-10 | 2026-03-16 | 10 | False |
| nq_term_structure_lead_lag_feedback | es_term_structure_lead_lag_feedback | late_day_two_sided_spread_feedback_1530 | two_sided_spread_feedback | 15:30:00 | 15:55:00 | 30 | True | True | 4.0 | 0.5 | 2010-06-10 | 2026-03-16 | 164 | 36 | 2.283605418548107 | 2011-02-22 | 2012-09-07 | 4 | 2.5950266429840143 | 2022-06-10 | 2026-03-16 | 5 | False |
| nq_term_structure_lead_lag_feedback | es_term_structure_lead_lag_feedback | afternoon_confirmed_spread_feedback_1400 | two_sided_confirmed_feedback | 14:00:00 | 15:30:00 | 30 | True | True | 4.0 | 0.5 | 2010-06-10 | 2026-03-16 | 164 | 29 | 1.8395710316081975 | 2011-02-22 | 2012-09-07 | 2 | 1.2975133214920072 | 2022-06-10 | 2026-03-16 | 9 | False |
| nq_term_structure_lead_lag_feedback | es_term_structure_lead_lag_feedback | front_premium_reversion_short_1000 | front_premium_reversion_short | 10:00:00 | 11:30:00 | 30 | False | True | 4.0 | 0.5 | 2010-06-10 | 2026-03-16 | 164 | 19 | 1.205236193122612 | 2011-02-22 | 2012-09-07 | 1 | 0.6487566607460036 | 2022-06-10 | 2026-03-16 | 7 | False |
| nq_term_structure_lead_lag_feedback | es_term_structure_lead_lag_feedback | front_discount_reversion_long_1000 | front_discount_reversion_long | 10:00:00 | 11:30:00 | 30 | True | False | 4.0 | 0.5 | 2010-06-10 | 2026-03-16 | 164 | 16 | 1.0149357415769364 | 2011-02-22 | 2012-09-07 | 3 | 1.9462699822380105 | 2022-06-10 | 2026-03-16 | 2 | False |

## Artifacts

- Detail CSV: `research_artifacts/nq_term_structure_lead_lag_feedback_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_term_structure_lead_lag_feedback_density_summary_20260630.csv`

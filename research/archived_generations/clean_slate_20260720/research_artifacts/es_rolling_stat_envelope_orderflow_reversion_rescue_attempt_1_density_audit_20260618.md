# ES Rolling Statistical Envelope Orderflow Reversion Rescue 1 Pre-PnL Density Audit

Date: 2026-06-18

Result: PASS

This revised rescue density audit replaced the first rescue draft before any rescue PnL was run because several original strict rescue corners were below 50 signals/year.

Detail CSV: `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_rescue_attempt_1_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_rescue_attempt_1_density_summary_20260618.csv`

| variant | scope | timeframe | period | combos | min sig/yr | median sig/yr | max sig/yr | pass | weakest combo | strongest combo |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| afternoon_5m_large20_24bar_reversion_1500 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 66.173179 | 168.027975 | 229.659858 | True | band_z=2.75, imbalance=0.4 | band_z=1.75, imbalance=0.1 |
| afternoon_5m_large20_24bar_reversion_1500 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 78.33728 | 180.90793 | 235.076637 | True | band_z=2.75, imbalance=0.4 | band_z=1.75, imbalance=0.1 |
| all_day_1m_signed_30bar_reversion_1530 | limited_core_grid_test | 1m | 2011-02-22 to 2012-09-06 | 9 | 236.147425 | 241.986234 | 241.986234 | True | band_z=3.0, imbalance=0.3 | band_z=2.0, imbalance=0.1 |
| all_day_1m_signed_30bar_reversion_1530 | full_configured_data | 1m | 2011-01-03 to 2026-06-09 | 9 | 175.011575 | 242.528073 | 246.998936 | True | band_z=3.0, imbalance=0.3 | band_z=2.0, imbalance=0.1 |
| late_morning_5m_large10_12bar_reversion_1230 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 106.396092 | 179.705595 | 230.308615 | True | band_z=2.75, imbalance=0.25 | band_z=1.75, imbalance=0.1 |
| late_morning_5m_large10_12bar_reversion_1230 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 86.955029 | 162.311735 | 230.346594 | True | band_z=2.75, imbalance=0.25 | band_z=1.75, imbalance=0.1 |
| midday_5m_signed_18bar_reversion_1400 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 139.482682 | 205.007105 | 229.011101 | True | band_z=2.75, imbalance=0.2 | band_z=1.75, imbalance=0.1 |
| midday_5m_signed_18bar_reversion_1400 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 70.561868 | 135.356972 | 215.31413 | True | band_z=2.75, imbalance=0.2 | band_z=1.75, imbalance=0.1 |
| morning_5m_signed_6bar_reversion_1130 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 126.507549 | 198.519538 | 236.796181 | True | band_z=2.75, imbalance=0.2 | band_z=1.75, imbalance=0.1 |
| morning_5m_signed_6bar_reversion_1130 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 59.741086 | 124.471394 | 202.225519 | True | band_z=2.75, imbalance=0.2 | band_z=1.75, imbalance=0.1 |

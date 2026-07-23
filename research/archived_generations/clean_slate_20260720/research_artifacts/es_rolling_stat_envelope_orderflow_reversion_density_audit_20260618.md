# ES Rolling Statistical Envelope Orderflow Reversion Pre-PnL Density Audit

Date: 2026-06-18

Purpose: count raw entry-module signals before any backtest PnL is inspected.

Result: PASS

Rules used:
- Same canonicalized limited-core random 10% contiguous period as the staged runner.
- Same full configured RTH range as each variant config.
- Entry-module state machine only; stop/target and PnL were not evaluated.
- Every entry parameter corner must produce at least 50 signals/year in both scopes.

Detail CSV: `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_density_summary_20260618.csv`

| variant | scope | timeframe | period | combos | min sig/yr | median sig/yr | max sig/yr | pass | weakest combo | strongest combo |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| afternoon_5m_large20_24bar_reversion_1500 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 242.634991 | 242.634991 | 242.634991 | True | band_z=1.0, imbalance=0.0 | band_z=1.0, imbalance=0.0 |
| afternoon_5m_large20_24bar_reversion_1500 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 246.67496 | 247.193321 | 247.322911 | True | band_z=1.5, imbalance=0.1 | band_z=1.0, imbalance=0.0 |
| all_day_1m_signed_30bar_reversion_1530 | limited_core_grid_test | 1m | 2011-02-22 to 2012-09-06 | 9 | 242.634991 | 242.634991 | 242.634991 | True | band_z=1.5, imbalance=0.0 | band_z=1.5, imbalance=0.0 |
| all_day_1m_signed_30bar_reversion_1530 | full_configured_data | 1m | 2011-01-03 to 2026-06-09 | 9 | 247.322911 | 247.322911 | 247.322911 | True | band_z=1.5, imbalance=0.0 | band_z=1.5, imbalance=0.0 |
| late_morning_5m_large10_12bar_reversion_1230 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 242.634991 | 242.634991 | 242.634991 | True | band_z=1.0, imbalance=0.0 | band_z=1.0, imbalance=0.0 |
| late_morning_5m_large10_12bar_reversion_1230 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 243.888771 | 246.739755 | 247.193321 | True | band_z=1.5, imbalance=0.1 | band_z=1.0, imbalance=0.0 |
| midday_5m_signed_18bar_reversion_1400 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 241.986234 | 242.634991 | 242.634991 | True | band_z=1.5, imbalance=0.0 | band_z=1.0, imbalance=0.0 |
| midday_5m_signed_18bar_reversion_1400 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 246.80455 | 247.258116 | 247.322911 | True | band_z=1.5, imbalance=0.05 | band_z=1.0, imbalance=0.0 |
| morning_5m_signed_6bar_reversion_1130 | limited_core_grid_test | 5m | 2011-02-22 to 2012-09-06 | 9 | 242.634991 | 242.634991 | 242.634991 | True | band_z=1.0, imbalance=0.0 | band_z=1.0, imbalance=0.0 |
| morning_5m_signed_6bar_reversion_1130 | full_configured_data | 5m | 2011-01-03 to 2026-06-09 | 9 | 245.897419 | 247.258116 | 247.322911 | True | band_z=1.5, imbalance=0.05 | band_z=1.0, imbalance=0.0 |

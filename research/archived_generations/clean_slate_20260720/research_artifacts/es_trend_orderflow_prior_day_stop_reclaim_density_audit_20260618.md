# ES Trend-Orderflow Prior-Day Stop-Reclaim Pre-PnL Density Audit

Date: 2026-06-18

Purpose: count raw entry-module signals before any backtest PnL is inspected. This checks whether the predeclared mechanics can plausibly satisfy the 50 trades/year methodology gate.

Result: FAIL

Rules used:
- Same canonicalized limited-core random 10% contiguous window as the staged runner.
- Same full configured RTH range as each variant config.
- Entry-module state machine only; stop/target and PnL were not evaluated.
- Every entry parameter corner must produce at least 50 signals/year in both scopes.

Detail CSV: `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_density_summary_20260618.csv`

| variant | scope | period | combos | min sig/yr | median sig/yr | max sig/yr | pass | weakest combo | strongest combo |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| afternoon_large20_two_sided_trend_absorption_1500 | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 1.297513 | 9.082593 | 18.165187 | False | sweep=4, imbalance=0.1 | sweep=1, imbalance=0.0 |
| afternoon_large20_two_sided_trend_absorption_1500 | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 9.65447 | 17.365088 | 25.01091 | False | sweep=4, imbalance=0.1 | sweep=1, imbalance=0.0 |
| late_morning_signed_two_sided_trend_absorption_1230 | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 3.89254 | 9.73135 | 17.51643 | False | sweep=3, imbalance=0.05 | sweep=1, imbalance=0.0 |
| late_morning_signed_two_sided_trend_absorption_1230 | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 4.470862 | 10.820782 | 19.827302 | False | sweep=3, imbalance=0.05 | sweep=1, imbalance=0.0 |
| midday_large10_two_sided_trend_absorption_1400 | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 1.94627 | 8.433837 | 19.4627 | False | sweep=4, imbalance=0.1 | sweep=1, imbalance=0.0 |
| midday_large10_two_sided_trend_absorption_1400 | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 7.321847 | 16.717137 | 26.630788 | False | sweep=4, imbalance=0.1 | sweep=1, imbalance=0.0 |
| morning_pdh_signed_trend_absorption_short_1130 | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 1.94627 | 3.89254 | 9.082593 | False | sweep=3, imbalance=0.02 | sweep=1, imbalance=0.0 |
| morning_pdh_signed_trend_absorption_short_1130 | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 2.527009 | 6.22033 | 11.857504 | False | sweep=3, imbalance=0.05 | sweep=1, imbalance=0.0 |
| morning_pdl_signed_trend_absorption_long_1130 | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 1.94627 | 6.487567 | 11.028863 | False | sweep=3, imbalance=0.05 | sweep=1, imbalance=0.0 |
| morning_pdl_signed_trend_absorption_long_1130 | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 2.203034 | 5.248403 | 8.164183 | False | sweep=3, imbalance=0.05 | sweep=1, imbalance=0.0 |

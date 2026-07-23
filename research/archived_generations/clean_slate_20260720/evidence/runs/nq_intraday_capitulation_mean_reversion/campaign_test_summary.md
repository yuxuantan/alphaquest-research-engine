# Campaign Test Summary: nq_intraday_capitulation_mean_reversion

Date: 2026-06-23

Verdict: FAIL.

All five valid `run3` variants failed `limited_core_grid_test`. `run1` and `run2` were pre-PnL methodology/config errors and are not treated as strategy results. No variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

- Density audit: `research_artifacts/nq_intraday_capitulation_mean_reversion_density_audit_20260623.md`
- Initial density reject: `research_artifacts/nq_intraday_capitulation_mean_reversion_initial_density_rejected_20260623.md`
- Candidate strategy report created: false

## Variant Results

| variant | core profitable | benchmark pass | top net | top PF | top trades | top MAR |
|---|---:|---:|---:|---:|---:|---:|
| full_session_15m_structural_flush_reclaim_long_1530 | 33/81 | 16 | 1945.0 | 1.1977630910015251 | 127 | 0.710399867640174 |
| afternoon_15m_liquidation_snapback_long_1530 | 18/81 | 7 | 1017.5 | 1.1962391513982642 | 102 | 0.676572131909925 |
| opening_5m_volume_flush_reclaim_long_1100 | 8/81 | 0 | 805.0 | 1.1074766355140186 | 111 | 0.3491747036292574 |
| midday_15m_vwap_flush_reclaim_long_1430 | 7/81 | 0 | 260.0 | 1.0503388189738625 | 87 | 0.19299691699131533 |
| morning_10m_volume_flush_reclaim_long_1230 | 1/81 | 0 | 100.0 | 1.0129533678756477 | 99 | 0.04383263369181437 |

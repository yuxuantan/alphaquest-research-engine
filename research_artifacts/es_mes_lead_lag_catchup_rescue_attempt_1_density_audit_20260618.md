# ES/MES lead-lag catch-up rescue attempt 1 pre-PnL density audit

Date: 2026-06-18

This audit counts only rescue entry signals and does not inspect PnL or staged result metrics.

## Summary

- afternoon60_signed_two_sided_1400 / full: min 195.1 signals/year, max 247.8, sessions 1757
- afternoon60_signed_two_sided_1400 / limited_core: min 175.6 signals/year, max 243.5, sessions 178
- late_day30_large20_two_sided_1500 / full: min 184.2 signals/year, max 251.1, sessions 1757
- late_day30_large20_two_sided_1500 / limited_core: min 160.0 signals/year, max 250.6, sessions 178
- late_morning30_signed_two_sided_1130 / full: min 193.6 signals/year, max 251.4, sessions 1757
- late_morning30_signed_two_sided_1130 / limited_core: min 155.7 signals/year, max 250.6, sessions 178
- midday30_large10_two_sided_1230 / full: min 205.2 signals/year, max 252.0, sessions 1757
- midday30_large10_two_sided_1230 / limited_core: min 203.9 signals/year, max 252.0, sessions 178
- morning15_signed_two_sided_1030 / full: min 206.8 signals/year, max 252.0, sessions 1757
- morning15_signed_two_sided_1030 / limited_core: min 177.0 signals/year, max 252.0, sessions 178

## Decision

All rescue entry-threshold combinations clear the 50 signals/year density screen. Approved for the one allowed rescue run per failed variant.

Detail CSV: `research_artifacts/es_mes_lead_lag_catchup_rescue_attempt_1_density_audit_20260618.csv`

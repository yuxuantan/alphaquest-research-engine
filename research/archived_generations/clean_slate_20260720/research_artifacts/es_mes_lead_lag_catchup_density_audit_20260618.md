# ES/MES lead-lag catch-up pre-PnL density audit

Date: 2026-06-18

This audit counts only predeclared entry signals after the fixed signal-window reformulation. It does not inspect PnL, stops, targets, equity curves, WFA output, monkey output, or Monte Carlo output.

Input cache: `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`

Counting rule: at most one signal per session, matching `max_trades_per_day: 1`.

Stage-window policy: limited core uses the canonical random 10 percent window, avoids the latest 10 percent of available data, and excludes the configured Covid range.

## Summary

- afternoon60_signed_two_sided_1400 / full: min 222.7 signals/year, max 251.9, available sessions 1757
- afternoon60_signed_two_sided_1400 / limited_core: min 210.9 signals/year, max 252.0, available sessions 178
- late_day30_large20_two_sided_1500 / full: min 184.2 signals/year, max 251.6, available sessions 1757
- late_day30_large20_two_sided_1500 / limited_core: min 160.0 signals/year, max 252.0, available sessions 178
- late_morning30_signed_two_sided_1130 / full: min 210.4 signals/year, max 252.0, available sessions 1757
- late_morning30_signed_two_sided_1130 / limited_core: min 189.7 signals/year, max 252.0, available sessions 178
- midday30_large10_two_sided_1230 / full: min 207.5 signals/year, max 252.0, available sessions 1757
- midday30_large10_two_sided_1230 / limited_core: min 205.3 signals/year, max 252.0, available sessions 178
- morning15_signed_two_sided_1030 / full: min 216.6 signals/year, max 252.0, available sessions 1757
- morning15_signed_two_sided_1030 / limited_core: min 199.6 signals/year, max 252.0, available sessions 178

## Decision

All declared entry-threshold combinations clear the 50 signals/year density screen in both full and limited-core periods. Approved for preflight and staged PnL validation without changing mechanics after results.

Detail CSV: `research_artifacts/es_mes_lead_lag_catchup_density_audit_20260618.csv`

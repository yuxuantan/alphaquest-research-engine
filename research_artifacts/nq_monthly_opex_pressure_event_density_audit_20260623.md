# Event-Density Audit: nq_monthly_opex_pressure

Date: 2026-06-23

Verdict: PASS FOR STAGING.

This is a pre-PnL calendar-event audit. Monthly OPEX variants are intentionally low-frequency, so the generic 50-signals/year screen is not used as a rejection rule here. The staged runner will evaluate trade count, benchmark adjustments, WFA stability, and robustness.

- Calendar: `data/external/nyse_monthly_opex_sessions_20110103_20260612.csv`
- Full window: 2011-01-03 through 2026-06-12

| variant | signal type | full events | events/year | latest 365d events |
|---|---|---:|---:|---:|
| nonquarterly_opex_thursday_positioning_short_1330 | previous_regular_session | 124 | 8.0317 | 8 |
| nonquarterly_post_opex_monday_reversal_long_1000 | next_regular_session | 124 | 8.0317 | 8 |
| nonquarterly_opex_late_short_1500 | opex_session | 124 | 8.0317 | 8 |
| nonquarterly_opex_midday_long_1200 | opex_session | 124 | 8.0317 | 8 |
| nonquarterly_opex_open_short_1000 | opex_session | 124 | 8.0317 | 8 |

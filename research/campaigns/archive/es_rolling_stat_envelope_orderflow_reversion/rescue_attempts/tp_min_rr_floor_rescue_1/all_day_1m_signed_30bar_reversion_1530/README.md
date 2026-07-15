# all_day_1m_signed_30bar_reversion_1530

Campaign: `es_rolling_stat_envelope_orderflow_reversion`

## Mechanics

All-day 1-minute two-sided reversion after a completed close outside a 30-bar rolling close envelope with signed aggregate flow pressing into the extreme.

- Entry: `rolling_stat_envelope_orderflow_reversion`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `1m`
- Orderflow mode: `signed`

## Pre-Test Rationale

A 30-minute 1-minute envelope tests the same rolling statistical-extreme mechanism at higher resolution while the one-trade-per-day rule prevents hyperactive churn. The setup is accepted for density audit because it expresses a completed-bar rolling statistical extension plus same-side aggregate orderflow pressure without using future session levels, final VWAP, or post-signal data.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_rolling_stat_envelope_orderflow_reversion/all_day_1m_signed_30bar_reversion_1530/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

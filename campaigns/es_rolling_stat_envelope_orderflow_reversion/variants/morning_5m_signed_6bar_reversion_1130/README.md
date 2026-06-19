# morning_5m_signed_6bar_reversion_1130

Campaign: `es_rolling_stat_envelope_orderflow_reversion`

## Mechanics

Morning 5-minute two-sided reversion after a completed close outside a 6-bar rolling close envelope with same-bar signed aggregate flow pressing into the extreme.

- Entry: `rolling_stat_envelope_orderflow_reversion`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `signed`

## Pre-Test Rationale

Six completed 5-minute bars define a 30-minute local envelope after the open, keeping the signal dense enough while avoiding raw one-minute noise. The setup is accepted for density audit because it expresses a completed-bar rolling statistical extension plus same-side aggregate orderflow pressure without using future session levels, final VWAP, or post-signal data.

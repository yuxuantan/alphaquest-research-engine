# midday_5m_signed_18bar_reversion_1400

Campaign: `nq_rolling_stat_envelope_orderflow_reversion`

## Mechanics

Midday 5-minute two-sided reversion after a completed close outside an 18-bar rolling close envelope with signed aggregate flow pressing into the statistical extreme.

- Entry: `rolling_stat_envelope_orderflow_reversion`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `signed`

## Pre-Test Rationale

The 90-minute envelope is meant to adapt to the quieter midday distribution without anchoring to VWAP, prior levels, or final session information. The setup is accepted for density audit because it expresses a completed-bar rolling statistical extension plus same-side aggregate orderflow pressure without using future session levels, final VWAP, or post-signal data.

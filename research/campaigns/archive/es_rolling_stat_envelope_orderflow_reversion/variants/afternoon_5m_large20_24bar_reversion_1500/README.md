# afternoon_5m_large20_24bar_reversion_1500

Campaign: `es_rolling_stat_envelope_orderflow_reversion`

## Mechanics

Afternoon 5-minute two-sided reversion after a completed close outside a 24-bar rolling close envelope with large-20 trade flow pressing into the extreme.

- Entry: `rolling_stat_envelope_orderflow_reversion`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `large20`

## Pre-Test Rationale

The two-hour 5-minute envelope gives a slower afternoon reference while testing whether larger-trade urgency at local statistical extremes is temporary. The setup is accepted for density audit because it expresses a completed-bar rolling statistical extension plus same-side aggregate orderflow pressure without using future session levels, final VWAP, or post-signal data.

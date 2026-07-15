# late_morning_5m_large10_12bar_reversion_1230

Campaign: `nq_rolling_stat_envelope_orderflow_reversion`

## Mechanics

Late-morning 5-minute two-sided reversion after a completed close outside a 12-bar rolling close envelope with large-10 trade flow pressing into the extension.

- Entry: `rolling_stat_envelope_orderflow_reversion`
- Stop: `sweep_extreme`
- Target: `fixed_r`
- Timeframe: `5m`
- Orderflow mode: `large10`

## Pre-Test Rationale

A 12-bar 5-minute envelope covers the first hour of RTH and tests whether larger trade pressure into a statistical extension exhausts after the opening impulse settles. The setup is accepted for density audit because it expresses a completed-bar rolling statistical extension plus same-side aggregate orderflow pressure without using future session levels, final VWAP, or post-signal data.

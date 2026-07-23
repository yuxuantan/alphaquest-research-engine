# ES orderflow impulse reversal density audit - 2026-06-18

Scope: pre-PnL signal-density check only. No net profit, trade outcomes, stops, targets, staged results, or equity curves were inspected.

A first pre-PnL density pass failed four variants at the strictest entry-threshold corners. Because no PnL or outcome data had been inspected, the entry-threshold grids were reformulated before testing while preserving the same entry module, stop module, target module, times, data, costs, and core orderflow-plus-return impulse reversal mechanic.

Full data subset: 2011-01-03 to 2026-06-09, sessions=['RTH'].
Limited-core benchmark subset: 2011-02-22 to 2012-09-06, sessions=['RTH'].
Limited-core window uses the canonical seeded random 10 percent period, avoids the latest 10 percent, and excludes the configured COVID range.

| variant | min full signals/year | min limited signals/year | strictest full signals | strictest limited signals | result |
|---|---:|---:|---:|---:|---|
| afternoon_60m_impulse_reversal_1400 | 70.89 | 62.93 | 1094 | 97 | PASS |
| early_5m_impulse_reversal_1000 | 64.92 | 60.98 | 1002 | 94 | PASS |
| late_day_30m_impulse_reversal_1500 | 61.49 | 59.04 | 949 | 91 | PASS |
| late_morning_15m_impulse_reversal_1130 | 65.31 | 55.14 | 1008 | 85 | PASS |
| midday_30m_impulse_reversal_1230 | 65.38 | 51.25 | 1009 | 79 | PASS |

Conclusion: PASS. Every declared entry-threshold pair remains above 50 signals/year in both full and limited-core windows before PnL testing.

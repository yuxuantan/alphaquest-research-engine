# NQ VWAP Deviation Orderflow Reversion Campaign Summary

Decision: FAIL.

Rejected before staged NQ PnL: 6/45 declared VWAP-deviation entry-grid rows failed the pre-PnL density gate. The sparse rows were in morning_large10_counterflow_1200 and morning_signed_counterflow_1200; the weakest limited-core proxy density was 29.79 signals/year. Dropping morning variants or strict deviation/counterflow corners after this screen would change the declared five-variant edge after observing signal availability. No NQ PnL was inspected.

| Variant | Entry rows | Rows passing | Min full/year | Min limited/year | Min latest252 | Density pass |
|---|---:|---:|---:|---:|---:|---|
| afternoon_signed_counterflow_1530 | 9 | 9 | 175.76 | 85.48 | 248 | PASS |
| midday_large20_counterflow_1400 | 9 | 9 | 159.05 | 68.00 | 240 | PASS |
| midday_signed_counterflow_1400 | 9 | 9 | 169.35 | 62.17 | 248 | PASS |
| morning_large10_counterflow_1200 | 9 | 6 | 147.85 | 33.68 | 248 | FAIL |
| morning_signed_counterflow_1200 | 9 | 6 | 142.80 | 29.79 | 235 | FAIL |

No staged PnL, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was produced.

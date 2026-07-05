# NQ China Tech Risk Sentiment Density Audit

Date: 2026-07-01

Verdict: PASS

This is a pre-PnL opportunity-count audit for prior-day China technology and broad-China ETF relative states.
The feature CSV maps each NQ RTH session to CQQQ, FXI, and QQQ daily observations available no later than the prior business day.
No NQ PnL, stops, targets, or trade outcomes were inspected for this audit.

Rows passing density: 45/45
Minimum required signals per year in each window: 50.0

## Variant Summary

| Variant | Rows Passing | Min Signals/Year | Full Min Signals | Limited-Core Min Signals | Latest-252 Min Signals |
|---|---:|---:|---:|---:|---:|
| cqqq_1d_relative_strength_long_1000 | 9/9 | 79.00 | 1342 | 121 | 79 |
| cqqq_1d_volatility_short_1330 | 9/9 | 83.00 | 1347 | 136 | 83 |
| cqqq_3d_relative_weakness_short_1030 | 9/9 | 84.00 | 1334 | 136 | 84 |
| fxi_1d_relative_strength_long_1130 | 9/9 | 73.00 | 1336 | 131 | 73 |
| fxi_3d_relative_weakness_short_1200 | 9/9 | 88.30 | 1346 | 130 | 103 |

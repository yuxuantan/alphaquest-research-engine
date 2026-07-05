# NQ Nikkei 225 Close Spillover Density Audit

Date: 2026-07-01

Verdict: PASS

This is a pre-PnL opportunity-count audit for the same-date Nikkei 225 close state.
The feature CSV maps each NQ RTH session to the latest Nikkei 225 close observation on or before the session date.
No NQ PnL, stops, targets, or trade outcomes were inspected for this audit.

Rows passing density: 45/45
Minimum required signals per year in each window: 50.0

## Variant Summary

| Variant | Rows Passing | Min Signals/Year | Full Min Signals | Limited-Core Min Signals | Latest-252 Min Signals |
|---|---:|---:|---:|---:|---:|
| nikkei_1d_strength_long_1000 | 9/9 | 75.61 | 1144 | 114 | 92 |
| nikkei_1d_volatility_short_1130 | 9/9 | 76.86 | 1163 | 114 | 98 |
| nikkei_1d_weakness_short_1000 | 9/9 | 75.01 | 1135 | 112 | 78 |
| nikkei_5d_strength_long_1030 | 9/9 | 76.75 | 1173 | 113 | 95 |
| nikkei_5d_weakness_short_1030 | 9/9 | 65.00 | 1139 | 120 | 65 |

# NQ Taiwan Semiconductor Spillover Density Audit

Date: 2026-07-01

Verdict: PASS

This is a pre-PnL opportunity-count audit for same-date Taiwan cash-market and TSMC local-share state.
The feature CSV maps each NQ RTH session to the latest TAIEX and 2330.TW observation on or before the session date.
No NQ PnL, stops, targets, or trade outcomes were inspected for this audit.

Rows passing density: 45/45
Minimum required signals per year in each window: 50.0
Maximum observation lag allowed for signals: 3 calendar days

## Variant Summary

| Variant | Rows Passing | Min Signals/Year | Full Min Signals | Limited-Core Min Signals | Latest-252 Min Signals |
|---|---:|---:|---:|---:|---:|
| taiwan_1d_volatility_short_1130 | 9/9 | 92.28 | 1364 | 139 | 109 |
| tsmc_1d_relative_strength_long_1030 | 9/9 | 88.76 | 1312 | 132 | 93 |
| tsmc_3d_relative_weakness_short_1030 | 9/9 | 87.88 | 1299 | 134 | 93 |
| twii_1d_strength_long_1000 | 9/9 | 85.85 | 1325 | 124 | 108 |
| twii_1d_weakness_short_1000 | 9/9 | 82.00 | 1316 | 129 | 82 |

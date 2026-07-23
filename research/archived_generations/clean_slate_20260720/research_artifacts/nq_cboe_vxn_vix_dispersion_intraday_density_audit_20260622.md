# NQ Cboe VXN/VIX Dispersion Density Audit

Decision: PASS

This is a pre-PnL density audit. It counts only the strictly lagged Cboe VXN/VIX rank condition for each declared threshold. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Features: `data/external/nq_cboe_vxn_vix_dispersion_features_20110103_20260612.csv`
- Availability: latest Cboe VIX and VXN daily closes strictly before NQ session_date.

| Variant | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|
| falling_vxn_vix_ratio_long_1200 | 923 | 1203 | 59.78 | 77.92 |
| high_vxn_minus_vix_short_1330 | 919 | 1255 | 59.53 | 81.29 |
| high_vxn_vix_ratio_short_1000 | 960 | 1329 | 62.18 | 86.08 |
| low_vxn_vix_ratio_long_1130 | 947 | 1183 | 61.34 | 76.63 |
| rising_vxn_vix_ratio_short_1030 | 920 | 1238 | 59.59 | 80.19 |

All variants have enough pre-PnL signal density to justify staged testing.

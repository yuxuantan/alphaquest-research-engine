# ES Oil Price Shock Spillover Density Audit - 2026-06-17

Decision: PASS density precheck.

Scope: pre-performance signal-density audit only. This audit uses the lagged
feature file `data/external/es_oil_price_shock_features_20110103_20260609.csv`
and does not inspect ES returns, PnL, stops, targets, or later stage results.

Feature construction:
- EIA WTI source: `https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls`
- EIA Brent source: `https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls`
- Builder: `tools/build_es_oil_price_shock_features.py`
- Availability rule: latest EIA WTI/Brent observation on or before ES
  `session_date - 2` business days.
- Feature rows: `3817`
- Valid ranked rows: `3760`
- ES session range: `2011-01-03` through `2026-06-09`
- Oil observation range used by ES sessions: `2010-12-30` through `2026-06-05`
- Lookahead violations found: `0` observations after their availability cutoff.

Declared original density:

| Variant | Driver | Threshold | Signals | Approx trades/year |
| --- | --- | ---: | ---: | ---: |
| `wti_down_relief_long_1000` | WTI 1-day return rank <= | 0.50 | 1863 | 120.73 |
| `wti_down_relief_long_1000` | WTI 1-day return rank <= | 0.45 | 1669 | 108.16 |
| `wti_down_relief_long_1000` | WTI 1-day return rank <= | 0.40 | 1483 | 96.11 |
| `wti_up_risk_off_short_1030` | WTI 1-day return rank >= | 0.55 | 1701 | 110.24 |
| `wti_up_risk_off_short_1030` | WTI 1-day return rank >= | 0.60 | 1520 | 98.51 |
| `wti_up_risk_off_short_1030` | WTI 1-day return rank >= | 0.65 | 1318 | 85.42 |
| `brent_up_global_shock_short_1130` | Brent 1-day return rank >= | 0.55 | 1694 | 109.78 |
| `brent_up_global_shock_short_1130` | Brent 1-day return rank >= | 0.60 | 1512 | 97.99 |
| `brent_up_global_shock_short_1130` | Brent 1-day return rank >= | 0.65 | 1336 | 86.58 |
| `oil_volatility_stress_short_1200` | Average absolute WTI/Brent return rank >= | 0.55 | 1715 | 111.14 |
| `oil_volatility_stress_short_1200` | Average absolute WTI/Brent return rank >= | 0.60 | 1535 | 99.48 |
| `oil_volatility_stress_short_1200` | Average absolute WTI/Brent return rank >= | 0.65 | 1355 | 87.81 |
| `brent_wti_spread_widen_short_1330` | Brent-WTI spread change rank >= | 0.55 | 1707 | 110.62 |
| `brent_wti_spread_widen_short_1330` | Brent-WTI spread change rank >= | 0.60 | 1516 | 98.25 |
| `brent_wti_spread_widen_short_1330` | Brent-WTI spread change rank >= | 0.65 | 1316 | 85.29 |

Conclusion: all declared original entry thresholds exceed the 50 trades/year
screen before any backtest performance is evaluated.

Rescue density precheck:

The one allowed per-failed-variant rescue keeps the same mechanics and changes
only declared threshold, stop, and target parameter space. These rescue
thresholds were also checked before running rescue performance tests.

| Variant | Driver | Threshold | Signals | Approx trades/year |
| --- | --- | ---: | ---: | ---: |
| `wti_down_relief_long_1000` | WTI 1-day return rank <= | 0.35 | 1315 | 85.22 |
| `wti_down_relief_long_1000` | WTI 1-day return rank <= | 0.30 | 1126 | 72.97 |
| `wti_down_relief_long_1000` | WTI 1-day return rank <= | 0.25 | 937 | 60.72 |
| `wti_up_risk_off_short_1030` | WTI 1-day return rank >= | 0.65 | 1318 | 85.42 |
| `wti_up_risk_off_short_1030` | WTI 1-day return rank >= | 0.70 | 1134 | 73.49 |
| `wti_up_risk_off_short_1030` | WTI 1-day return rank >= | 0.75 | 956 | 61.96 |
| `brent_up_global_shock_short_1130` | Brent 1-day return rank >= | 0.65 | 1336 | 86.58 |
| `brent_up_global_shock_short_1130` | Brent 1-day return rank >= | 0.70 | 1151 | 74.59 |
| `brent_up_global_shock_short_1130` | Brent 1-day return rank >= | 0.75 | 957 | 62.02 |
| `oil_volatility_stress_short_1200` | Average absolute WTI/Brent return rank >= | 0.65 | 1355 | 87.81 |
| `oil_volatility_stress_short_1200` | Average absolute WTI/Brent return rank >= | 0.70 | 1145 | 74.20 |
| `oil_volatility_stress_short_1200` | Average absolute WTI/Brent return rank >= | 0.75 | 981 | 63.58 |
| `brent_wti_spread_widen_short_1330` | Brent-WTI spread change rank >= | 0.65 | 1316 | 85.29 |
| `brent_wti_spread_widen_short_1330` | Brent-WTI spread change rank >= | 0.70 | 1109 | 71.87 |
| `brent_wti_spread_widen_short_1330` | Brent-WTI spread change rank >= | 0.75 | 925 | 59.95 |

Conclusion: all declared rescue entry thresholds also exceed the 50 trades/year
screen before rescue performance is evaluated.

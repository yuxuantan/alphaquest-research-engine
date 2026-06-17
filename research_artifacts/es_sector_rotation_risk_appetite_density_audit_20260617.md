# ES Sector Rotation Risk Appetite Density Audit - 2026-06-17

Feature file: `data/external/es_sector_rotation_features_20110103_20260609.csv`
Rows: 3817
Period: 2011-01-03 to 2026-06-09 (15.43 years)

Density is computed before PnL testing. Each row is one possible same-day ES signal after the one-business-day sector ETF availability lag.

| Variant | Driver | Thresholds | Min signals/year | Max signals/year | Pass density? |
|---|---|---:|---:|---:|---|
| `cyclical_lead_long_1000` | `cyclical_minus_defensive_1d_rank_252 >=` | [0.55, 0.6, 0.65] | 88.3 | 112.6 | PASS |
| `defensive_lead_short_1000` | `cyclical_minus_defensive_1d_rank_252 <=` | [0.45, 0.4, 0.35] | 86.9 | 110.8 | PASS |
| `growth_lead_long_1030` | `growth_minus_defensive_5d_rank_252 >=` | [0.55, 0.6, 0.65] | 87.7 | 111.8 | PASS |
| `defensive_rotation_short_1130` | `cyclical_minus_defensive_5d_rank_252 <=` | [0.45, 0.4, 0.35] | 87.9 | 112.5 | PASS |
| `financial_industrial_lead_long_1330` | `financial_industrial_minus_spy_1d_rank_252 >=` | [0.55, 0.6, 0.65] | 85.9 | 112.0 | PASS |

Conclusion: PASS. All declared threshold cells must clear the 50 signals/year pre-PnL screen.

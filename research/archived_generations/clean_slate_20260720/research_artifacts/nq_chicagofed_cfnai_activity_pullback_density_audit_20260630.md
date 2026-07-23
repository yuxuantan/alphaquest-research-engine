# NQ Chicago Fed CFNAI Activity Pullback Density Audit

Date: 2026-06-30

Scope: pre-PnL signal-density audit only. Counts use completed NQ RTH 1-minute bars and the latest CFNAI observation whose conservative eligible date is on or before the session date. No trade PnL, stop, target, or post-entry returns are inspected.

Bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
Features: `data/external/nq_chicagofed_cfnai_activity_features_20110103_20260612.csv`
Date range: 2011-01-03 through 2026-06-12

## Minimum Density By Variant

| Variant | Minimum signals/year across declared entry grid |
| --- | ---: |
| `diffusion_weak_pullback_long_1200` | 60.17 |
| `employment_hours_weak_pullback_long_1330` | 73.26 |
| `headline_activity_weak_pullback_long_1100` | 59.72 |
| `ma3_activity_weak_pullback_long_1130` | 62.25 |
| `production_income_weak_pullback_long_1100` | 54.15 |

Result: all five variants exceed the 50 signals/year pre-PnL density floor across the declared entry grid corners. This is not a performance result and does not justify promotion.

Full grid table: `research_artifacts/nq_chicagofed_cfnai_activity_pullback_density_audit_20260630.csv`

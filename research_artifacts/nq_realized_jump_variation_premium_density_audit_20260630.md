# NQ Realized Jump Variation Premium Density Audit

Date: 2026-06-30

Scope: pre-PnL signal-density audit only. Counts use lagged NQ realized-jump features shifted by one completed RTH session and the presence of the completed signal-time bar. No trade PnL, stop, target, or post-entry returns are inspected.

Bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
Features: `data/external/nq_realized_jump_variation_features_20110103_20260612.csv`
Date range: 2011-01-03 through 2026-06-12

## Minimum Density By Variant

| Variant | Minimum signals/year across declared entry grid |
| --- | ---: |
| `high_3d_jump_var_midmorning_long_1030` | 50.85 |
| `high_jump_var_open_long_1000` | 50.07 |
| `negative_jump_rebound_long_1130` | 51.95 |
| `positive_jump_reversal_short_1200` | 52.14 |
| `two_sided_signed_jump_extreme_1330` | 97.29 |

Result: all five official variants exceed the 50 signals/year pre-PnL density floor across the declared entry grid corners. This is not a performance result and does not justify promotion.

Rejected before PnL: the copied ES `high_jump_share_midmorning_long_1030` variant was not selected for NQ because its 0.80 rank corner produced only 49.55 signals/year in the density audit.

Full grid table: `research_artifacts/nq_realized_jump_variation_premium_density_audit_20260630.csv`

# NQ Sector Opening Breadth Orderflow Density Audit

Decision: FAIL_DENSITY

This is a pre-PnL density audit. It counts only same-day ETF opening-breadth conditions and completed NQ price/orderflow confirmation at each variant's declared 5-minute signal times. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Features: `data/external/nq_sector_opening_breadth_features_20110103_20260612.csv`
- Feature availability: same-day ETF raw Open after 09:30 ET plus prior ETF raw Close; no same-day ETF close/high/low is used.
- Test window for density: 2011-01-03 through 2026-06-10, matching available sector ETF opens.
- Sector-count grids for sparse NQ variants were widened before PnL testing based only on opportunity counts.

| Variant | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|
| broad_down_morning_signed_short_1130 | 223 | 637 | 14.45 | 41.27 |
| broad_two_sided_morning_large10_1130 | 996 | 1685 | 64.54 | 109.18 |
| broad_up_early_signed_long_1000 | 292 | 758 | 18.92 | 49.11 |
| cyclical_up_morning_signed_long_1130 | 314 | 896 | 20.35 | 58.06 |
| riskoff_cycdown_midday_signed_short_1230 | 200 | 638 | 12.96 | 41.34 |

Every variant now has at least one declared corner above the 50 candidate-session/year opportunity threshold; sparse corners remain subject to fail-closed core trade-count gates.

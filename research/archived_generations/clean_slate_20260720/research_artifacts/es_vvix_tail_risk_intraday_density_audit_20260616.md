# ES VVIX Tail Risk Intraday Density Audit - 2026-06-16

Decision: eligible for pre-registered staged testing.

This audit was run before any `es_vvix_tail_risk_intraday` performance backtest.
It checks only whether the proposed fixed-time daily VVIX states are plausibly
dense enough to meet the user's `>=50 trades/year` requirement. It does not use
trade PnL, stops, targets, or stage results.

Source data:
- ES RTH 1-minute bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Cboe VVIX history: `data/external/cboe_vvix_history.csv`
- Cboe VIX history: `data/external/cboe_vix_history.csv`
- Derived feature file: `data/external/es_vvix_tail_risk_features_20110103_20260609.csv`

Feature rows:
- Rows: `3817`
- Valid rank rows: `3759`
- Date range: `2011-01-03` to `2026-06-09`
- Approximate years: `15.430527`

Lookahead control:
- The builder uses the latest Cboe VVIX/VIX close strictly before the ES
  `session_date`.
- Same-day Cboe closes are not available to intraday ES signals and are not used.

Pre-performance density:

| Proposed variant | Feature | Thresholds | Approx trades/year |
| --- | --- | --- | --- |
| `high_vvix_short_1000` | `vvix_close_rank_252 >= threshold` | `0.55`, `0.60`, `0.65` | `117.24`, `107.45`, `96.30` |
| `low_vvix_long_1030` | `vvix_close_rank_252 <= threshold` | `0.45`, `0.40`, `0.35` | `103.95`, `94.36`, `83.41` |
| `rising_vvix_short_1130` | `vvix_change_1d_rank_252 >= threshold` | `0.55`, `0.60`, `0.65` | `111.86`, `99.67`, `86.65` |
| `falling_vvix_long_1200` | `vvix_change_1d_rank_252 <= threshold` | `0.45`, `0.40`, `0.35` | `109.00`, `96.17`, `85.09` |
| `high_vvix_vix_ratio_short_1330` | `vvix_vix_ratio_rank_252 >= threshold` | `0.55`, `0.60`, `0.65` | `121.58`, `111.60`, `102.91` |

Conclusion:
- All five proposed variants clear the density gate before performance testing.
- No threshold, entry time, direction, stop, target, or rescue parameter was
  chosen from trade results.

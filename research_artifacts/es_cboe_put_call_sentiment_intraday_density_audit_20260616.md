# ES Cboe Put/Call Sentiment Density Audit - 2026-06-16

Decision: PASS for pre-backtest density.

Scope: active-only duplicate policy, archived tests ignored. This audit only
checks whether the declared original grids are likely to meet the user's
`>=50 trades/year` rule before any performance results are inspected.

Data:
- Feature file: `data/external/es_cboe_put_call_features_20110103_20260609.csv`
- Source ES sessions: `2011-01-03` through `2026-06-09`
- Session count: `3817`
- Valid rank rows: `3759`
- Approximate span: `15.43` years
- Availability rule: latest Cboe put/call observation strictly before the ES
  session date.

Declared original entry grids:

| Variant | Feature | Thresholds | Approx trades/year by threshold | Decision |
| --- | --- | --- | --- | --- |
| `low_equity_pc_long_1000` | `equity_pc_ratio_rank_252 <= threshold` | `0.50, 0.45, 0.40` | `72.1, 58.8, 52.7` | PASS |
| `high_equity_pc_short_1030` | `equity_pc_ratio_rank_252 >= threshold` | `0.55, 0.60, 0.65` | `65.9, 57.0, 50.0` | PASS |
| `falling_total_pc_long_1130` | `total_pc_change_1d_rank_252 <= threshold` | `0.50, 0.45, 0.40` | `69.8, 61.4, 54.7` | PASS |
| `rising_total_pc_short_1200` | `total_pc_change_1d_rank_252 >= threshold` | `0.55, 0.60, 0.625` | `61.0, 54.4, 51.8` | PASS |
| `high_total_vs_equity_pc_short_1330` | `total_minus_equity_pc_rank_252 >= threshold` | `0.55, 0.60, 0.65` | `76.7, 68.9, 59.6` | PASS |

Rejected pre-test alternative:
- `rising_index_pc_short_1200` was not used because `index_pc_change_1d_rank_252`
  upper-tail thresholds would only produce about `6.4` to `7.8` trades/year.

Conclusion: the five selected original variants are dense enough to proceed to
the staged methodology without violating the trade-count rule.

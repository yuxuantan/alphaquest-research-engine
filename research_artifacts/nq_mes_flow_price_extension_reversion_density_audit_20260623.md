# NQ MES Flow Price Extension Reversion Density Audit

Status: PASS

This is a pre-PnL signal-count audit only. It uses `data/cache/orderflow/nq_mes_flow_divergence_1m_20190506_20260612_full_rth_ny.csv` and completed bars at the configured signal close. No stops, targets, trade logs, WFA, Monte Carlo, or holdout PnL were inspected for this campaign.

Rules checked:
- Each variant consumes the bar whose close equals the configured entry signal time; engine entry is next-bar-open or later.
- Entry parameter grid is `flow_threshold in [0.005, 0.0075, 0.01]` and `min_return_ticks in [0, 2, 4]`.
- Density pass floor is 50 signals per year at every declared entry-grid corner.

Summary:
- Sessions inspected: 1760
- Calendar-year denominator: 7.104723
- Minimum signals/year across all corners: 57.848844
- Maximum signals/year across all corners: 139.625434

| variant | min signals/year | max signals/year |
|---|---:|---:|
| `morning15_mes_buy_nq_up_extension_short_1000` | 61.367630 | 71.079480 |
| `morning15_mes_sell_nq_down_extension_long_1000` | 57.848844 | 66.012428 |
| `late_morning30_mes_buy_nq_up_extension_short_1030` | 59.115607 | 68.686705 |
| `late_morning30_mes_sell_nq_down_extension_long_1100` | 63.478902 | 72.627746 |
| `midday60_mes_two_sided_nq_extension_reversion_1200` | 118.653468 | 139.625434 |

CSV: `research_artifacts/nq_mes_flow_price_extension_reversion_density_audit_20260623.csv`

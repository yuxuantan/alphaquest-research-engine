# NQ Round-Number Barrier Reaction Density Audit

Pre-PnL density audit only. No trade PnL, stop/target outcome, WFA result, or backtest metric was inspected before fixing this NQ grid.

- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.csv`
- Source bars: deterministic 5-minute aggregation from local completed NQ 1-minute RTH bars
- Barrier grid fixed before PnL: `barrier_interval_points=[25,50,100]`, `buffer_ticks=[0,1]`
- Module-equivalent conditions used for density: fixed time windows, range filter, near-close distance, one signal day count

| Variant | Strict-corner min signals/year | Density decision |
|---|---:|---|
| morning_round_support_reclaim_long | 80.3174 | PASS |
| morning_round_resistance_reject_short | 78.0504 | PASS |
| midday_two_sided_round_reclaim | 114.5819 | PASS |
| round_number_upside_breakout_long | 81.4833 | PASS |
| round_number_downside_breakout_short | 75.0709 | PASS |

CSV: `research_artifacts/nq_round_number_barrier_reaction_density_audit_20260622.csv`

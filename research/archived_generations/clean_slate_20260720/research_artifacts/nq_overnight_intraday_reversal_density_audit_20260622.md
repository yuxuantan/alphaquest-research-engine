# NQ Overnight Intraday Reversal Density Audit

Pre-PnL density audit only. No trade PnL, stop/target outcome, WFA result, or backtest metric was inspected before fixing this NQ grid.

- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.csv`
- Signals use prior RTH close, RTH open, and completed 5/15/30-minute opening windows only.
- Entry grid fixed before PnL: `min_abs_overnight_bps=[10,25,30]`, `confirm_threshold_bps=[0,5]`
- Side-only variants were excluded before PnL because they did not clear the density floor.

| Variant | Strict-corner min signals/year | Density decision |
|---|---:|---|
| first5_confirm_reversal_1000 | 60.6915 | PASS |
| first15_confirm_reversal_1000 | 64.9664 | PASS |
| first30_confirm_reversal_1000 | 62.6346 | PASS |
| first30_noncontinuation_1000 | 70.0834 | PASS |
| overnight_only_two_sided_1000 | 139.1953 | PASS |

CSV: `research_artifacts/nq_overnight_intraday_reversal_density_audit_20260622.csv`

# NQ Prior-Day Stop-Run Reclaim Pre-PnL Density Rejection

Date: 2026-06-23

Verdict: FAIL

This was a pre-PnL NQ portability screen for the ES `es_prior_day_stop_run_reclaim` edge. The screen reused the five ES variant mechanics and their latest source rescue configs where applicable, changed only the market data contract to NQ, and counted entry signals before any NQ PnL, fills, stops, targets, or staged-test outcomes were inspected.

Data and method:

- Source bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Prepared feature path: repo `prepare_data` with `timeframe: 5m` and `feature_set: pdh_pdl_sweep`
- Window: 2011-01-03 through 2026-06-12 RTH
- Prepared bars: 297,414
- Sessions: 3,813
- Years at 252 sessions/year: 15.130952
- Latest-year check: latest 252 sessions through 2026-06-12
- Counting rule: one possible entry signal per session, matching `max_trades_per_day: 1`; entry module was `pdh_pdl_sweep_reclaim`

Result:

- Full declared entry-grid minimum: 4.494099 signals/year
- Latest-252 declared entry-grid minimum: 8 signals
- Only the loose full-session two-sided variant cleared 50/year on some entry corners; the strict declared corners and the side/time-specific variants were too sparse.

Failure reason:

Reject before full campaign staging. A strategy family whose declared corners mostly produce fewer than 30 signals/year, and whose strictest NQ corner produces only 4.49 signals/year, cannot support the required robustness tests without overfitting or relaxing mechanics after seeing scarcity. No NQ PnL was inspected.

Detailed table: `research_artifacts/nq_prior_day_stop_run_reclaim_density_rejected_20260623.csv`

# Methodology audit: NQ self-lead opening-range breakout

Verdict: FAIL. Five variants were frozen before staged PnL testing, each with 81 combinations and pre-PnL density above the trade-count floor. No post-result rescue or mechanic change was applied.

No-lookahead controls:
- Opening-range boundaries are only used after the configured opening window has completed.
- ES/NQ lead-lag fields are completed rolling bar features available at signal time.
- The derived NQ-primary cache maps NQ OHLCV/orderflow into tradeable columns and keeps ES only as a completed relative benchmark.
- Signals are generated on completed bar close and entered by the engine on the next eligible bar.

Failure evidence:
- or15_nq5_signed_long_1015: failed limited_core_grid_test; profitable=6/81; core_profitable_rate=0.07407407407407407; top_net=47.5; top_pf=1.002431533145636; top_trades=163; top_failure=max_best_day_concentration.
- or15_nq15_signed_long_1030: failed limited_core_grid_test; profitable=0/81; core_profitable_rate=0.0; top_net=-2497.5; top_pf=0.9001; top_trades=196; top_failure=min_total_net_profit.
- or30_nq15_signed_long_1030: failed limited_core_grid_test; profitable=0/81; core_profitable_rate=0.0; top_net=-100.0; top_pf=0.9946794360202181; top_trades=134; top_failure=min_total_net_profit.
- or30_nq30_signed_long_1130: failed limited_core_grid_test; profitable=0/81; core_profitable_rate=0.0; top_net=-3890.0; top_pf=0.8633169360505973; top_trades=204; top_failure=min_total_net_profit.
- or30_nq30_large10_long_1130: failed limited_core_grid_test; profitable=0/81; core_profitable_rate=0.0; top_net=-5335.0; top_pf=0.8179802115319004; top_trades=199; top_failure=min_total_net_profit.

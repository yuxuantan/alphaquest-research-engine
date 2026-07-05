# Methodology audit - NQ rolling range orderflow sweep reversal

Verdict: FAIL.

Rejected before staged NQ PnL by the pre-PnL density screen. The declared five-variant family had 41 of 45 entry-grid rows pass all density windows, but only 3 of 5 variants fully cleared density. `all_day_large20_36bar_sweep_reclaim_1500` had 6 of 9 passing rows and `morning_signed_12bar_sweep_reclaim_1130` had 8 of 9 passing rows. Dropping sparse rows or variants after seeing the screen would be post-result narrowing, so the full campaign is rejected.

No stop/target outcome, trade log, equity curve, limited core, monkey test, WFA, Monte Carlo, simulated incubation, acceptance OOS, final holdout PnL, or candidate report was produced.

- Source ES campaign: `es_rolling_range_orderflow_sweep_reversal`.
- NQ port keeps the same five rolling-range sweep/reclaim mechanics and modules.
- Duplicate screen: distinct from prior-day stop-run, opening-range failed breakout, ChartFanatics liquidity-inversion/FVG, one-bar key reversal, session-extreme divergence, and round-number barrier campaigns.
- Lookahead control: rolling highs/lows use prior completed bars only; sweep/reclaim/orderflow checks use completed 5-minute bars only; entry occurs next bar open or later.

Density detail: `research_artifacts/nq_rolling_range_orderflow_sweep_reversal_density_audit_20260630.md`.

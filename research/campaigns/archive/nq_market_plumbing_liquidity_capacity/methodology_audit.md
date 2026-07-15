# Methodology Audit - NQ Market Plumbing Liquidity Capacity

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded edge: lagged market-plumbing and funding-liquidity capacity state applied to same-day NQ intraday risk premia.
- Exactly five variants were authored before NQ PnL testing, using the corrected ES run2 mechanics as templates.
- Entry used completed 5-minute NQ bars with signal-on-close and next-bar-open execution; external feature rows came from the lagged no-lookahead market-plumbing feature file.
- All variants used NQ point value 20.0, tick size 0.25, one tick slippage, commissions, intraday flattening, and configured prop rules.
- No rescue was authorized.

Pre-PnL density:
- `research_artifacts/nq_market_plumbing_liquidity_capacity_initial_density_rejected_20260622.md` rejected the original ES VX strict-tail threshold corners as too sparse before any NQ PnL testing.
- `research_artifacts/nq_market_plumbing_liquidity_capacity_density_reform1_rejected_20260622.md` rejected the first VX-stress density reformulation before any NQ PnL testing.
- `research_artifacts/nq_market_plumbing_liquidity_capacity_density_audit_20260622.md` approved all five variants after signal-density-only VX grid widening.

Testing outcome:
- `dealer_lending_pressure_long_1130`: failed limited core grid gate: profitable_combos=18/27; top_net=3035.0; top_pf=1.2793373216751036; top_trades=68; top_mar=1.72930324703508.
- `dealer_lending_pressure_long_1330`: failed limited monkey gate after core pass: profitable_rate=0.431; median_net=-550.0; net_beat_rate=0.7675; dd_beat_rate=0.599875.
- `dual_pressure_priority_long_1130`: failed limited monkey gate after core pass: profitable_rate=0.4695; median_net=-305.0; net_beat_rate=0.835; dd_beat_rate=0.916625.
- `vx_oi_crowding_short_1330`: failed limited core grid gate: profitable_combos=0/27; top_net=-1355.0; top_pf=0.8535135135135136; top_trades=79; top_mar=-0.5754850169492362.
- `vx_oi_stress_long_1330`: failed limited core grid gate: profitable_combos=17/27; top_net=4365.0; top_pf=1.4968696642003414; top_trades=60; top_mar=1.7713765361054068.

No rescue was authorized or attempted after PnL results. No `candidate_strategy_report.md` was created.

# Methodology audit: NQ opening-drive inventory orderflow

Verdict: FAIL. The campaign used five predeclared variants and an 81-combination grid per variant before staged testing. No post-result rescue or mechanic change was applied.

No-lookahead controls:
- Opening-window return, imbalance, and volume features are only available after the 30-minute or 60-minute opening window closes.
- Opening-volume rank is computed from prior sessions and the current session is appended after the due-slot signal decision.
- Entry signals are emitted at completed bar close and filled by the engine on the next eligible bar.
- All variants are RTH-only and flatten before the configured prop-rule cutoff.

Failure evidence:
- open30_flow_continuation_1030: failed walk_forward_analysis; profitable=81/81; core_profitable_rate=1.0; top_net=1415.0; top_trades=19; top_failure=min_trades_per_year;preferred_min_total_trades; monkey_net_beat=0.940375; monkey_dd_beat=0.9545; monkey_goal=True; wfa_early_exit=True; stitched_oos_trades=0.
- open30_absorbed_pressure_fade_1015: failed limited_core_grid_test; profitable=9/81; core_profitable_rate=0.1111111111111111; top_net=257.5; top_trades=6; top_failure=min_trades_per_year;preferred_min_total_trades;max_best_day_concentration.
- open60_flow_continuation_1130: failed limited_monkey_test; profitable=76/81; core_profitable_rate=0.9382716049382716; top_net=912.5; top_trades=9; top_failure=min_trades_per_year;preferred_min_total_trades; monkey_net_beat=0.908625; monkey_dd_beat=0.44125; monkey_goal=False.
- open60_exhaustion_fade_1300: failed limited_core_grid_test; profitable=24/81; core_profitable_rate=0.2962962962962963; top_net=100.0; top_trades=4; top_failure=min_trades_per_year;preferred_min_total_trades;max_best_day_concentration.
- open30_price_flow_divergence_fade_1400: failed limited_monkey_test; profitable=60/81; core_profitable_rate=0.7407407407407407; top_net=320.0; top_trades=6; top_failure=min_trades_per_year;preferred_min_total_trades;max_best_day_concentration; monkey_net_beat=0.873875; monkey_dd_beat=0.565; monkey_goal=False.

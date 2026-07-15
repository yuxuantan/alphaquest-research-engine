# rolling30_full_session_notional_two_sided

Campaign: `es_mes_footprint_liquidity_sweep_reversion`

Fade completed one-minute sweeps of the prior 30-minute rolling high/low using notional-equivalent MES participation crowding plus footprint absorption on the reclaim bar.

Mechanics: build the rolling high/low from prior completed one-minute bars, require the current completed bar to sweep and reclaim that level, require footprint absorption against the sweep, require MES crowding in the sweep direction, then enter at the next bar open. Stop is beyond the sweep extreme; target is fixed R with no value below 1.0R.

Parameter grid: 36 combinations. Entry tunables: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`. Stop tunable: `sl.params.stop_offset_ticks`. Target tunable: `tp.params.target_r_multiple`.

## Rescue Attempt: parameter_space_rescue_1

Original notional rolling-30 variant had zero profitable combinations; the least-bad runs used the stricter two-tick sweep, lower 0.55 MES share-rank threshold, and two-tick stop offset. Rescue tests that same mechanic with a slightly stricter sweep band and stop offsets around the prior best stop without changing TP below or above the original grid.

Changed fields: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`, and `sl.params.stop_offset_ticks` grids only. `tp.params.target_r_multiple` remains `[1.0, 1.5, 2.0]`; no sub-1.0R target is allowed.

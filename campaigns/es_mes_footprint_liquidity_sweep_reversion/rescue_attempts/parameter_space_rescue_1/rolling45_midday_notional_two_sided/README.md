# rolling45_midday_notional_two_sided

Campaign: `es_mes_footprint_liquidity_sweep_reversion`

From 10:30 through 15:00 ET, fade 45-minute rolling-range sweeps only when the reclaim bar shows footprint absorption and high MES notional participation in the failed sweep direction.

Mechanics: build the rolling high/low from prior completed one-minute bars, require the current completed bar to sweep and reclaim that level, require footprint absorption against the sweep, require MES crowding in the sweep direction, then enter at the next bar open. Stop is beyond the sweep extreme; target is fixed R with no value below 1.0R.

Parameter grid: 36 combinations. Entry tunables: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`. Stop tunable: `sl.params.stop_offset_ticks`. Target tunable: `tp.params.target_r_multiple`.

## Rescue Attempt: parameter_space_rescue_1

Original notional rolling-45 midday variant had zero profitable combinations and the least-bad runs used the stricter two-tick sweep, lower 0.55 threshold, and two-tick stop. Rescue does not alter the midday notional mechanic or TP grid; it tests whether stricter sweeps plus adjacent stop offsets improve cost-adjusted behaviour.

Changed fields: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`, and `sl.params.stop_offset_ticks` grids only. `tp.params.target_r_multiple` remains `[1.0, 1.5, 2.0]`; no sub-1.0R target is allowed.

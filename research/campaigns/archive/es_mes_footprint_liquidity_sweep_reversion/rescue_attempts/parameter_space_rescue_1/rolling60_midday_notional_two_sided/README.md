# rolling60_midday_notional_two_sided

Campaign: `es_mes_footprint_liquidity_sweep_reversion`

Fade completed sweeps of the prior 60-minute rolling high/low when high MES notional participation and footprint absorption jointly indicate a failed liquidity grab.

Mechanics: build the rolling high/low from prior completed one-minute bars, require the current completed bar to sweep and reclaim that level, require footprint absorption against the sweep, require MES crowding in the sweep direction, then enter at the next bar open. Stop is beyond the sweep extreme; target is fixed R with no value below 1.0R.

Parameter grid: 36 combinations. Entry tunables: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`. Stop tunable: `sl.params.stop_offset_ticks`. Target tunable: `tp.params.target_r_multiple`.

## Rescue Attempt: parameter_space_rescue_1

Original notional rolling-60 midday variant had zero profitable combinations and again ranked best around the stricter two-tick sweep, lower 0.55 threshold, and two-tick stop. Rescue keeps the longer rolling window and notional MES crowding mechanic while testing adjacent sweep and stop parameters only.

Changed fields: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`, and `sl.params.stop_offset_ticks` grids only. `tp.params.target_r_multiple` remains `[1.0, 1.5, 2.0]`; no sub-1.0R target is allowed.

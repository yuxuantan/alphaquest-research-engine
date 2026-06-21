# rolling30_full_session_notional_two_sided

Campaign: `es_mes_footprint_liquidity_sweep_reversion`

Fade completed one-minute sweeps of the prior 30-minute rolling high/low using notional-equivalent MES participation crowding plus footprint absorption on the reclaim bar.

Mechanics: build the rolling high/low from prior completed one-minute bars, require the current completed bar to sweep and reclaim that level, require footprint absorption against the sweep, require MES crowding in the sweep direction, then enter at the next bar open. Stop is beyond the sweep extreme; target is fixed R with no value below 1.0R.

Parameter grid: 36 combinations. Entry tunables: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`. Stop tunable: `sl.params.stop_offset_ticks`. Target tunable: `tp.params.target_r_multiple`.

# rolling45_full_session_trade_large10_two_sided

Campaign: `es_mes_footprint_liquidity_sweep_reversion`

Fade completed sweeps of a 45-minute rolling high/low when MES trade-share rank is high and footprint absorption confirms failed continuation at the swept edge.

Mechanics: build the rolling high/low from prior completed one-minute bars, require the current completed bar to sweep and reclaim that level, require footprint absorption against the sweep, require MES crowding in the sweep direction, then enter at the next bar open. Stop is beyond the sweep extreme; target is fixed R with no value below 1.0R.

Parameter grid: 36 combinations. Entry tunables: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`. Stop tunable: `sl.params.stop_offset_ticks`. Target tunable: `tp.params.target_r_multiple`.

## Rescue Attempt: parameter_space_rescue_1

Original large-trade rolling-45 variant was the strongest expression but still failed the 70 percent profitable-combo benchmark. Profitable runs clustered around 0.55 share rank and a two-tick stop, with both one- and two-tick sweeps viable. Rescue keeps the mechanic and TP grid unchanged while testing whether a lower-but-still-crowded 0.50 share-rank threshold and adjacent stop offsets create a broader profitable zone.

Changed fields: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`, and `sl.params.stop_offset_ticks` grids only. `tp.params.target_r_multiple` remains `[1.0, 1.5, 2.0]`; no sub-1.0R target is allowed.

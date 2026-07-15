# rolling30_full_session_trade_large10_two_sided

Campaign: `es_mes_footprint_liquidity_sweep_reversion`

Fade completed one-minute sweeps of the prior 30-minute rolling high/low from 10:00 to 15:00 ET when footprint absorption rejects the sweep and MES large-trade participation is crowded in the sweep direction.

Mechanics: build the rolling high/low from prior completed one-minute bars, require the current completed bar to sweep and reclaim that level, require footprint absorption against the sweep, require MES crowding in the sweep direction, then enter at the next bar open. Stop is beyond the sweep extreme; target is fixed R with no value below 1.0R.

Parameter grid: 36 combinations. Entry tunables: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`. Stop tunable: `sl.params.stop_offset_ticks`. Target tunable: `tp.params.target_r_multiple`.

## Rescue Attempt: parameter_space_rescue_1

Original large-trade rolling-30 variant produced one profitable combination, with the best result at a two-tick sweep, 0.55 share-rank threshold, two-tick stop offset, and the existing 2.0R grid value. Rescue keeps the same TP grid and tests adjacent entry/stop thresholds to see whether that behaviour is stable rather than isolated.

Changed fields: `entry.params.min_sweep_ticks`, `entry.params.share_rank_min`, and `sl.params.stop_offset_ticks` grids only. `tp.params.target_r_multiple` remains `[1.0, 1.5, 2.0]`; no sub-1.0R target is allowed.

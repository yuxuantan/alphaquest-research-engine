# midday_symmetric_shock_reversion

This variant fades completed high-volume 5-minute shock bars during the midday window from 11:30 through 13:30 ET. Both long and short reversals are allowed.

Tunable parameters are fixed before testing: shock size, volume-ratio threshold, percent stop, and fixed-R target.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_volume_shock_liquidity_reversal/midday_symmetric_shock_reversion/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

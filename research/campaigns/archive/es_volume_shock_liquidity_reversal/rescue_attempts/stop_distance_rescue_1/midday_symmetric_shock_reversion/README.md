# midday_symmetric_shock_reversion

This variant fades completed high-volume 5-minute shock bars during the midday window from 11:30 through 13:30 ET. Both long and short reversals are allowed.

Tunable parameters are fixed before testing: shock size, volume-ratio threshold, percent stop, and fixed-R target.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_volume_shock_liquidity_reversal/midday_symmetric_shock_reversion/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

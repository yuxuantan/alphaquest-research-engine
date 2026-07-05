# contango_morning_signed_vwap_reclaim_long_1300

Mechanic: Contango/risk-on state plus morning-to-midday NQ VWAP reclaim with signed aggregate buy-flow confirmation.

Why this expresses the edge: the prior-close Cboe VIX term-structure state chooses the risk regime and allowed direction before the NQ session starts. The NQ trade must also show current-session VWAP pullback/rejection continuation and completed aggregate orderflow in the same direction before next-bar entry.

Profitability rationale: Low VIX/VIX3M rank states proxy easier equity-risk conditions. A same-session NQ trend that pulls back to VWAP and reclaims it with net buying flow should represent institutions using VWAP-area liquidity to continue risk-on exposure rather than a blind timed long.

Lookahead controls: the Cboe observation is strictly before `session_date`; VWAP and orderflow use completed NQ bars only; entry is next bar; stop, target, costs, slippage, tick size, point value, and forced flatten are read from `config.yaml`.

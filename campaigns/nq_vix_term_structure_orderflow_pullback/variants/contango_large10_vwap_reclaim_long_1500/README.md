# contango_large10_vwap_reclaim_long_1500

Mechanic: Contango/risk-on state plus all-session NQ VWAP reclaim with large-10 buy-flow confirmation.

Why this expresses the edge: the prior-close Cboe VIX term-structure state chooses the risk regime and allowed direction before the NQ session starts. The NQ trade must also show current-session VWAP pullback/rejection continuation and completed aggregate orderflow in the same direction before next-bar entry.

Profitability rationale: If the option-implied term structure signals benign risk appetite, larger trade-size buy pressure at VWAP can indicate that bigger participants are defending intraday fair value. The long is only taken after NQ confirms the regime with price acceptance above VWAP.

Lookahead controls: the Cboe observation is strictly before `session_date`; VWAP and orderflow use completed NQ bars only; entry is next bar; stop, target, costs, slippage, tick size, point value, and forced flatten are read from `config.yaml`.

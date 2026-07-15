# curve_flattening_signed_vwap_reject_short_1500

Mechanic: High VIX3M/VIX6M curve-flattening state plus ES VWAP rejection with signed aggregate sell-flow confirmation.

Why this expresses the edge: the prior-close Cboe VIX term-structure state chooses the risk regime and allowed direction before the ES session starts. The ES trade must also show current-session VWAP pullback/rejection continuation and completed aggregate orderflow in the same direction before next-bar entry.

Profitability rationale: A flatter medium-term volatility curve can indicate deteriorating risk appetite. A current-session ES pullback that fails at VWAP with net selling flow expresses acceptance of lower prices while avoiding a timed short disconnected from intraday auction state.

Lookahead controls: the Cboe observation is strictly before `session_date`; VWAP and orderflow use completed ES bars only; entry is next bar; stop, target, costs, slippage, tick size, point value, and forced flatten are read from `config.yaml`.

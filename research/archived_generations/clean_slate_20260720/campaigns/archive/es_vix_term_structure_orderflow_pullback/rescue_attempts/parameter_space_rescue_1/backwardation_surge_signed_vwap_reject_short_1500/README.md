# backwardation_surge_signed_vwap_reject_short_1500

Mechanic: Lagged VIX/VIX3M backwardation-surge state plus ES VWAP rejection with signed aggregate sell-flow confirmation.

Why this expresses the edge: the prior-close Cboe VIX term-structure state chooses the risk regime and allowed direction before the ES session starts. The ES trade must also show current-session VWAP pullback/rejection continuation and completed aggregate orderflow in the same direction before next-bar entry.

Profitability rationale: A sharp prior-day rise in VIX/VIX3M can mark abrupt risk-premium stress. The variant does not short automatically; it requires the current ES session to remain below VWAP and reject a pullback with selling pressure, selecting days where stress is continuing intraday.

Lookahead controls: the Cboe observation is strictly before `session_date`; VWAP and orderflow use completed ES bars only; entry is next bar; stop, target, costs, slippage, tick size, point value, and forced flatten are read from `config.yaml`.

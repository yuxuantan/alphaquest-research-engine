# front_stress_large10_vwap_reject_short_1500

Mechanic: High VIX9D/VIX front-stress state plus ES VWAP rejection with large-10 sell-flow confirmation.

Why this expresses the edge: the prior-close Cboe VIX term-structure state chooses the risk regime and allowed direction before the ES session starts. The ES trade must also show current-session VWAP pullback/rejection continuation and completed aggregate orderflow in the same direction before next-bar entry.

Profitability rationale: Front-end volatility stress should reflect near-term hedging demand. Large-10 selling into a VWAP retest is a plausible sign that larger participants are using the benchmark bounce to reduce risk, rather than a random continuation short.

Lookahead controls: the Cboe observation is strictly before `session_date`; VWAP and orderflow use completed ES bars only; entry is next bar; stop, target, costs, slippage, tick size, point value, and forced flatten are read from `config.yaml`.

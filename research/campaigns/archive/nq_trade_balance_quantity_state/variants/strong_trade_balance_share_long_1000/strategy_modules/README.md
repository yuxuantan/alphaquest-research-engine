# strong_trade_balance_share_long_1000 Strategy Modules

Entry module: `nq_trade_balance_quantity_state`

Mechanic: At 10:00 ET, buy NQ when the 60-day-lagged trade-balance-to-total-trade rank is in the upper tail.

Rationale: A smaller trade deficit relative to total trade may proxy healthier external balance and less external-adjustment pressure.

Availability rule: each NQ session can use only the latest monthly FRED/Census/BEA BOP trade observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.

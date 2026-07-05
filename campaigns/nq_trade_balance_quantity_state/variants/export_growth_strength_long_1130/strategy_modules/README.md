# export_growth_strength_long_1130 Strategy Modules

Entry module: `nq_trade_balance_quantity_state`

Mechanic: At 11:30 ET, buy NQ when the 60-day-lagged three-month export growth rank is in the upper tail.

Rationale: Export growth may proxy stronger global demand and revenue conditions for U.S. risk assets.

Availability rule: each NQ session can use only the latest monthly FRED/Census/BEA BOP trade observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.

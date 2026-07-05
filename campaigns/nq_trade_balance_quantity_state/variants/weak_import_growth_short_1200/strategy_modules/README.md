# weak_import_growth_short_1200 Strategy Modules

Entry module: `nq_trade_balance_quantity_state`

Mechanic: At 12:00 ET, short NQ when the 60-day-lagged three-month import growth rank is in the lower tail.

Rationale: Weak import growth may proxy softening domestic demand rather than benign external rebalancing.

Availability rule: each NQ session can use only the latest monthly FRED/Census/BEA BOP trade observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.

# strong_receipts_yoy_long_1130 Strategy Modules

Entry module: `nq_fiscal_deficit_treasury_supply_state`

Mechanic: At 11:30 ET, buy NQ when 60-day-lagged federal receipts year-over-year growth rank is in the upper tail.

Rationale: Strong receipts may proxy nominal income/profit strength and a lower financing need, supporting risk appetite if the effect is real.

Availability rule: each NQ session can use only the latest monthly Treasury/FRED Monthly Treasury Statement observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.

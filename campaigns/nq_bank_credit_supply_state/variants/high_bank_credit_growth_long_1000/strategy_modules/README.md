# high_bank_credit_growth_long_1000 Strategy Modules

Entry module: `nq_bank_credit_supply_state`

Mechanic: At 10:00 ET, buy NQ when 14-day-lagged 13-week broad bank-credit growth rank is in the upper tail.

Rationale: Broad commercial-bank credit expansion may proxy easier credit supply and stronger risk appetite.

Availability rule: each NQ session can use only the latest weekly Federal Reserve/FRED H.8 observation on or before `session_date - 14 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.

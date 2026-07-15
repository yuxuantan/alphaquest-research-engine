# high_export_import_ratio_long_1030 Strategy Modules

Entry module: `nq_trade_balance_quantity_state`

Mechanic: At 10:30 ET, buy NQ when the 60-day-lagged export/import ratio rank is in the upper tail.

Rationale: A stronger export/import ratio may proxy improving net-export contribution and external demand.

Availability rule: each NQ session can use only the latest monthly FRED/Census/BEA BOP trade observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.

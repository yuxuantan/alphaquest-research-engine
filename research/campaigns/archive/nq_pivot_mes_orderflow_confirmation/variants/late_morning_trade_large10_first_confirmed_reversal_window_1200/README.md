# late_morning_trade_large10_first_confirmed_reversal_window_1200

Mechanic: From 10:30 through 12:00 ET, fade the first pivot-aligned MES trade-share crowding signal whose completed 30-minute native NQ large-10 signed flow agrees with the fade direction; flatten by 13:00 ET.

Source variant: `late_morning_trade_two_sided_reversal_window_1200` from `nq_pivot_filtered_mes_participation_crowding_reversion`.

Fixed orderflow fields: `flow_mode=large10_imbalance`, `orderflow_window_minutes=30`, `min_orderflow_imbalance=0.0`, `consume_unconfirmed_base_signal=false`.

Density audit: `research_artifacts/nq_pivot_mes_orderflow_confirmation_density_audit_20260623.md`.

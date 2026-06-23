# morning_notional_large20_first_confirmed_reversal_window_1130

Mechanic: From 10:30 through 11:30 ET, fade the first pivot-aligned MES notional-share crowding signal whose completed 30-minute native NQ large-20 signed flow agrees with the fade direction; flatten by 12:30 ET.

Source variant: `morning_notional_two_sided_reversal_window_1130` from `nq_pivot_filtered_mes_participation_crowding_reversion`.

Fixed orderflow fields: `flow_mode=large20_imbalance`, `orderflow_window_minutes=30`, `min_orderflow_imbalance=0.0`, `consume_unconfirmed_base_signal=false`.

Density audit: `research_artifacts/nq_pivot_mes_orderflow_confirmation_density_audit_20260623.md`.

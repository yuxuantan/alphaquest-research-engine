# es_prior_value_area_orderflow_acceptance Campaign Summary

Decision: FAIL

All five original variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space/fixed-parameter rescue preserving the same prior value-area acceptance mechanic. Four rescues failed limited_core_grid_test; morning_signed_vah_acceptance_long/rescue1 passed limited core but failed limited_monkey_test with net beat rate 0.8767, drawdown beat rate 0.8833, negative median monkey PnL, and one-tick-worse slippage net negative. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original: morning_signed_vah_acceptance_long run1 top_net=3232.5 profitable_combo_rate=0.5679012345679012
Best rescue: morning_signed_vah_acceptance_long rescue1 top_net=3232.5 profitable_combo_rate=1.0 terminal=limited_monkey_test

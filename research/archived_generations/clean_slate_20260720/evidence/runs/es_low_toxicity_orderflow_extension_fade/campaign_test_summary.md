# Campaign Test Summary

Campaign: `es_low_toxicity_orderflow_extension_fade`

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed the limited_core_grid_test profitable-combination gate before monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

## Best Runs

- Best original: `two_slot_midday_balanced_extension_fade/run1` profitable_combo_rate=0.06172839506172839, benchmark_passing_combos=0, top_net=1430.0, PF=1.2104488594554819, MAR=0.4229436435347066, trades/year=48.26338305866597.
- Best rescue: `three_slot_up_extension_fade_short/rescue1` profitable_combo_rate=0.2839506172839506, benchmark_passing_combos=3, top_net=1426.25, PF=1.1969958563535912, MAR=0.3531103679896602, trades/year=54.299392039154206.

No candidate_strategy_report.md was created because no run passed the staged methodology.

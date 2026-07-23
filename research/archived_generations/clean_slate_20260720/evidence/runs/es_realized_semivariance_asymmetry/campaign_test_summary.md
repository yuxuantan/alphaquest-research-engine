# ES Realized Semivariance Asymmetry Campaign Summary

Decision: FAIL.

Original runs: 5. Rescue runs: 5. Monkey reached: 1. WFA reached: 1.

Failure reason: All five original realized-semivariance variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue preserving the same semivariance feature, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, fill rules, session rules, prop rules, and validation gates. Four rescues failed limited_core_grid_test. One rescue, high_1d_badvol_continuation_short_1030/rescue1, passed core and limited monkey but failed walk_forward_analysis: window 2 triggered early exit with selected IS profit factor 0.84 < 1.00, and stitched OOS after window 1 had net profit -9625.0, PF 0.6356926570779712, MAR -0.7825314922408811, and expectancy R -0.24698221123551944. No run reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

# ES OFR Financial Stress Intraday Rescue Attempt 1

Decision: FAIL.

All five original variants failed `limited_core_grid_test`, so each failed variant received exactly one allowed parameter-space rescue. The rescue retained the OFR financial-stress edge, entry module, setup modes, directions, entry times, stop module, target module, 1-minute timeframe, data window, costs, fill assumptions, flatten rule, and OFR two-business-day availability lag. Only the existing stress threshold, stop percentage, and fixed-R target grids changed.

Rescue grid: threshold `[0.65, 0.70, 0.75]`; stop_pct `[0.004, 0.006, 0.008]`; target R `[1.5, 2.0, 2.5]`.

Best rescue: `high_credit_stress_short_1030` with profitable-combo rate `0.5185185185185185`, top net `4816.25`, PF `1.1366408965174835`, MAR `1.1298599938968712`, and `193` top-combo trades. It still failed the required `0.70` profitable-combo gate.

No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.

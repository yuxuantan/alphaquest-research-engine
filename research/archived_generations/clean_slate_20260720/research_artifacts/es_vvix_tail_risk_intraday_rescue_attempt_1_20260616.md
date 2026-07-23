# ES VVIX Tail Risk Intraday Rescue Attempt 1

Decision: FAIL.

All five original variants failed `limited_core_grid_test`, so each failed variant received exactly one allowed parameter-space rescue. The rescue retained the VVIX tail-risk edge, entry module, setup modes, directions, entry times, stop module, target module, 1-minute timeframe, data window, costs, fill assumptions, flatten rule, and Cboe prior-close availability rule. Only the existing VVIX threshold, stop percentage, and fixed-R target grids changed.

The only rescue that passed core was `low_vvix_long_1030/rescue1`: core profitable-combo rate `0.9629629629629629`, top net `3041.25`, PF `1.6872881355932203`, MAR `1.8214174302938066`, but only `48` top-combo trades and `38.59755230589296` trades/year in the limited-core window.

It failed `limited_monkey_test`: random-placebo profitable rate `0.31666666666666665` and median net profit `-1482.5`, despite trade-path stress itself passing. No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.

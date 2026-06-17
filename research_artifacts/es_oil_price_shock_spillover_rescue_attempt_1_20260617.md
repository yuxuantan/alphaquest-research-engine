# ES Oil Price Shock Spillover Rescue Attempt 1 - 2026-06-17

Decision: FAIL.

Scope: one allowed parameter-space rescue per failed original variant. The
rescue kept the EIA two-business-day availability lag, setup mode, direction,
entry time, entry module, stop module, target module, 1-minute timeframe, data
window, costs, fill assumptions, flatten rules, and validation gates unchanged.

Allowed changes used:
- Entry rank threshold grids.
- Fixed threshold defaults.
- Stop percentage grid.
- Fixed-R target grid.

Original result:
- All five original variants failed `limited_core_grid_test`.
- Best original was `wti_up_risk_off_short_1030/run1` with profitable-combo
  rate `0.07407407407407407`, zero benchmark-passing combinations, top net
  `1250.0`, top PF `1.0855871276959945`, top MAR `0.23116690498374848`, and
  `105` top-combo trades.

Rescue result:
- Four rescues failed `limited_core_grid_test`.
- `wti_up_risk_off_short_1030/rescue1` passed core with profitable-combo rate
  `0.7777777777777778`, `21` profitable combinations, zero benchmark-passing
  combinations, top net `2432.5`, top PF `1.2272302662307333`, top MAR
  `0.5067138541122316`, and `76` top-combo trades.
- `wti_up_risk_off_short_1030/rescue1` then failed `limited_monkey_test` with
  random-monkey profitable rate `0.17`, median net `-3905.0`, trade-path stress
  profitable rate `0.15666666666666668`, stress median net
  `-1105.2168487687982`, and `one_tick_worse_profitable=false`.

Conclusion: no oil price-shock spillover variant reached WFA, WFA OOS monkey,
Monte Carlo, simulated incubation, or frozen validation. No candidate strategy
report was created.

# NQ NY Fed RRP Liquidity State Methodology Audit

Verdict: FAIL

This campaign was a pre-PnL NQ port of `es_nyfed_rrp_liquidity_state`. The initial NQ density screen rejected the release-long side and the strict 0.375 drain threshold before any NQ PnL inspection. The final tested campaign used five RRP-drain short timing variants with `entry.params.rrp_drain_threshold=[0.125, 0.25]`.

No-lookahead controls:

- The RRP feature file is lagged by one listed trade date.
- Entries use completed 5-minute bar closes and the engine enters on the next bar open or later.
- No same-day RRP result, final session high/low, final VWAP, future orderflow, or post-entry path information is used for signal generation.

Execution controls:

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission is 2.5 per contract and slippage is one tick.
- Same-day flatten is configured at 15:55 ET with Apex-style no-overnight checks enabled.

Testing outcome:

- `rrp_drain_short_1000`: failed `limited_monkey_test` after passing limited core.
- `rrp_drain_short_1130`: failed `limited_core_grid_test`.
- `rrp_drain_short_1330`: failed `limited_core_grid_test`.
- `rrp_drain_short_1430`: failed `limited_core_grid_test`.
- `rrp_drain_short_1500`: failed `limited_core_grid_test`.

No rescue was run. No candidate strategy report was created.

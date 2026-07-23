# nq_aqr_bab_factor_state Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ AQR BAB variants failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bab_63d_extreme_two_sided_1330 | limited_core_grid_test | 0 | 27 | -2175.0 | 0.7774936061381074 | -0.6573858175827626 | 119 | summary.percentage_profitable_iterations=0.0 |
| low_bab_21d_rebound_long_1000 | limited_core_grid_test | 0 | 27 | -1472.5 | 0.7537625418060201 | -0.5279167242136189 | 53 | summary.percentage_profitable_iterations=0.0 |
| low_bab_63d_rebound_long_1030 | limited_core_grid_test | 9 | 27 | 1415.0 | 1.1624569460390355 | 1.778394491018067 | 83 | summary.percentage_profitable_iterations=0.3333333333333333 |
| low_bab_daily_rebound_long_0935 | limited_core_grid_test | 18 | 27 | 2615.0 | 1.297328027288232 | 0.9811879806991302 | 93 | summary.percentage_profitable_iterations=0.6666666666666666 |
| low_bab_z63_rebound_long_1100 | limited_core_grid_test | 5 | 27 | 740.0 | 1.0826353992183138 | 0.2801574062403459 | 104 | summary.percentage_profitable_iterations=0.18518518518518517 |

## Rejection Rationale

- The closest core stability result was `low_bab_daily_rebound_long_0935`: 18/27 profitable combinations, top net 2615.0, PF 1.2973, MAR 0.9812, but the profitable-combo rate was 0.6667 versus the required 0.70.
- `low_bab_z63_rebound_long_1100`, the strongest ES analog, produced only 5/27 profitable combinations and failed best-day concentration on the top row.
- No NQ rescue is authorized after these results.

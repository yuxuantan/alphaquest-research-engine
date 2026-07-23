# Campaign Test Summary: nq_monthly_opex_pressure

Date: 2026-06-23

Verdict: FAIL.

Four variants failed limited_core_grid_test or did not meet benchmark concentration requirements. The only core-and-monkey passing branch, nonquarterly_opex_thursday_positioning_short_1330, failed walk_forward_analysis: first training window had no selectable row and stitched OOS trades were 0. No Monte Carlo, simulated incubation, or acceptance OOS stage was reached.

- Event-density audit: `research_artifacts/nq_monthly_opex_pressure_event_density_audit_20260623.md`
- Candidate strategy report created: false

## Variant Results

| variant | terminal stage | core profitable | benchmark pass | top net | top PF | top trades/year | top MAR | monkey profitable | WFA OOS trades |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nonquarterly_opex_thursday_positioning_short_1330 | walk_forward_analysis | 11/12 | 2 | 450.0 | 1.6923076923076923 | 8.944074029461571 | 1.8704609447292069 | 0.33325 | 0 |
| nonquarterly_opex_late_short_1500 | limited_core_grid_test | 7/12 | 0 | 333.75 | 1.8042168674698795 | 8.944200778000582 | 1.1321714474361937 |  |  |
| nonquarterly_post_opex_monday_reversal_long_1000 | limited_core_grid_test | 6/12 | 0 | 577.5 | 1.6243243243243244 | 8.03917997185054 | 1.0740003746437243 |  |  |
| nonquarterly_opex_midday_long_1200 | limited_core_grid_test | 4/12 | 0 | 233.75 | 1.4288990825688073 | 8.941919853790191 | 0.5727566945786314 |  |  |
| nonquarterly_opex_open_short_1000 | limited_core_grid_test | 0/12 | 0 | -2.5 | 0.9972677595628415 | 8.940399883845288 | -0.004233752575380078 |  |  |

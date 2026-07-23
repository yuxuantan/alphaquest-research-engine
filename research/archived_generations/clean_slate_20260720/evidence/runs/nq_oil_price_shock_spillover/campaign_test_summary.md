# Campaign Test Summary: nq_oil_price_shock_spillover

Date: 2026-06-23

Verdict: FAIL.

Four variants failed limited_core_grid_test. The only core-passing branch, wti_up_risk_off_short_1030, had 25/27 profitable core combinations and 1 benchmark-pass combination, but failed limited_monkey_test with profitable random-entry rate 0.235875 and median net profit -1537.5. No WFA, Monte Carlo, simulated incubation, or acceptance OOS stage was reached.

- Density audit: `research_artifacts/nq_oil_price_shock_spillover_density_audit_20260623.md`
- Candidate strategy report created: false

## Variant Results

| variant | terminal stage | core profitable | benchmark pass | top net | top PF | top trades | top MAR | monkey profitable | monkey median net |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wti_up_risk_off_short_1030 | limited_monkey_test | 25/27 | 1 | 3065.0 | 1.2834026814609338 | 82 | 0.4666546972726379 | 0.235875 | -1537.5 |
| wti_down_relief_long_1000 | limited_core_grid_test | 5/18 | 1 | 1255.0 | 1.1360433604336044 | 83 | 0.3511046171759777 |  |  |
| brent_wti_spread_widen_short_1330 | limited_core_grid_test | 0/27 | 0 | -490.0 | 0.9408212560386473 | 88 | -0.17024940784238 |  |  |
| oil_volatility_stress_short_1200 | limited_core_grid_test | 0/27 | 0 | -1797.5 | 0.7817243472981178 | 93 | -0.4501002817688356 |  |  |
| brent_up_global_shock_short_1130 | limited_core_grid_test | 0/27 | 0 | -2865.0 | 0.7952840300107181 | 114 | -0.4684292719120357 |  |  |

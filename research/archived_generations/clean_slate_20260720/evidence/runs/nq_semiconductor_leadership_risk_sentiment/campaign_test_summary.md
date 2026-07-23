# NQ Semiconductor Leadership Risk Sentiment Summary

Decision: FAIL.

Four variants failed limited_core_grid_test; soxx_3d_nonleadership_short_1330 passed limited core but failed limited_monkey_test. No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Results CSV: `backtest-campaigns/nq_semiconductor_leadership_risk_sentiment/campaign_results.csv`
Density audit: `research_artifacts/nq_semiconductor_leadership_density_audit_20260701.md`

| Variant | Terminal Stage | Core Passing Cells | Profitable Rate | Top Net | Top PF | Fixed Net | Fixed PF | Monkey Net Beat | Monkey DD Beat |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| smh_1d_leadership_long_1000 | limited_core_grid_test | 5/27 | 0.5925925925925926 | 3010.0 | 1.175356830760268 | 1600.0 | 1.0880088008800881 | None | None |
| smh_1d_nonleadership_short_1000 | limited_core_grid_test | 0/27 | 0.0 | -145.0 | 0.9936997610254182 | -2120.0 | 0.9131503482179435 | None | None |
| smh_3d_leadership_long_1030 | limited_core_grid_test | 0/27 | 0.18518518518518517 | 1565.0 | 1.0862972153294734 | -2090.0 | 0.891849935316947 | None | None |
| soxx_3d_leadership_long_1130 | limited_core_grid_test | 0/27 | 0.18518518518518517 | 910.0 | 1.0736245954692556 | -1350.0 | 0.9220329194340168 | None | None |
| soxx_3d_nonleadership_short_1330 | limited_monkey_test | 10/27 | 0.8518518518518519 | 3050.0 | 1.2086183310533516 | 2050.0 | 1.1389359539139274 | 0.969125 | 0.837125 |

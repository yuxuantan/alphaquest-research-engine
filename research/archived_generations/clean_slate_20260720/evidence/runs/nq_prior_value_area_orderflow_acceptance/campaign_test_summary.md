# NQ Prior Value-Area Orderflow Acceptance Campaign Summary

Final verdict: FAIL.

All five predeclared NQ variants were run through the staged workflow. Every variant failed the limited core grid gate, so no variant reached monkey testing, walk-forward analysis, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| variant | terminal stage | core profitable combos | top net | top PF | top trades | top MAR | monkey net beat | monkey DD beat | WFA net | WFA PF | WFA MAR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| afternoon_large20_two_sided_acceptance | limited_core_grid_test | 0/81 | -2535.0 | 0.8588922905649875 | 189 | -0.6040325565826263 | None | None | None | None | None |
| late_morning_large10_two_sided_acceptance | limited_core_grid_test | 0/54 | -510.0 | 0.9590525893215576 | 175 | -0.18678333219090318 | None | None | None | None | None |
| midday_signed_two_sided_acceptance | limited_core_grid_test | 0/27 | -855.0 | 0.9338747099767981 | 175 | -0.2004388476283451 | None | None | None | None | None |
| morning_signed_vah_acceptance_long | limited_core_grid_test | 18/54 | 1145.0 | 1.09439406430338 | 125 | 0.496150181908971 | None | None | None | None | None |
| morning_signed_val_acceptance_short | limited_core_grid_test | 5/54 | 1320.0 | 1.093319194061506 | 116 | 0.2956263856401449 | None | None | None | None | None |

CSV detail: `backtest-campaigns/nq_prior_value_area_orderflow_acceptance/campaign_results.csv`

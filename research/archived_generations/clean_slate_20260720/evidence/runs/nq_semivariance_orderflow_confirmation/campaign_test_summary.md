# NQ Semivariance Orderflow Confirmation Campaign Summary

Final verdict: FAIL.

All five predeclared NQ variants were run through the staged workflow. Two variants passed limited core and limited monkey, but both failed WFA with negative stitched OOS results and WFA early-exit flags. The other three variants failed the limited core grid gate. No variant reached WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| variant | terminal stage | core profitable combos | top net | top PF | top trades | top MAR | monkey net beat | monkey DD beat | WFA net | WFA PF | WFA MAR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| badvol_signed_multitime_short | walk_forward_analysis | 33/36 | 3772.5 | 1.4422626025791325 | 96 | 3.4838479420952257 | 0.99575 | 0.990375 | -11505.0 | 0.7031350793446007 | -0.2748944193289918 |
| downside_share_signed_multitime_short | walk_forward_analysis | 31/36 | 2412.5 | 1.2289985761746558 | 109 | 1.0718986706633111 | 0.938625 | 0.933875 | -8030.0 | 0.5696677384780279 | -0.8992446669898104 |
| badvol_signed_multitime_twosided | limited_core_grid_test | 6/36 | 1082.5 | 1.061003099464638 | 197 | 0.29523508273112575 | None | None | None | None | None |
| semivar_balance_signed_multitime_twosided | limited_core_grid_test | 0/36 | -415.0 | 0.9605513307984791 | 177 | -0.19682808326569906 | None | None | None | None | None |
| low_badvol_signed_multitime_long | limited_core_grid_test | 0/36 | -1160.0 | 0.8503225806451613 | 97 | -0.34529836789214613 | None | None | None | None | None |

CSV detail: `backtest-campaigns/nq_semivariance_orderflow_confirmation/campaign_results.csv`

# nq_usdjpy_safe_haven_spillover Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ USDJPY safe-haven variants failed the clean `run1` staged flow. Strong-yen reached WFA but failed out-of-sample; no variant reached OOS monkey, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | monkey_profitable | monkey_median_net | net_beat | dd_beat | wfa_net | wfa_pf | wfa_mar | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| five_day_yen_appreciation_short_1330 | limited_core_grid_test | 0 | 27 | -422.5 | 0.9578973592426507 | -0.1889286664049251 | 106 |  |  |  |  |  |  |  | summary.percentage_profitable_iterations=0.0 |
| strong_yen_short_1130 | walk_forward_analysis | 27 | 27 | 5175.0 | 1.3201360965047944 | 2.577490978298795 | 133 | 0.188375 | -2595.0 | 0.966125 | 0.902625 | -200.0 | 0.0 | -289.2994568157961 | summary.early_exit=True;stitched_oos_metrics.profit_factor=0.0;stitched_oos_metrics.mar=-289.2994568157961 |
| weak_yen_long_1200 | limited_monkey_test | 18 | 18 | 860.0 | 1.1264705882352941 | 0.492199803412648 | 85 | 0.345125 | -980.0 | 0.773125 | 0.96575 |  |  |  | summary.core_beats_monkey_net_profit_rate=0.773125 |
| yen_appreciation_short_1000 | limited_core_grid_test | 2 | 18 | 362.5 | 1.0268022181146026 | 0.10757956896630277 | 101 |  |  |  |  |  |  |  | summary.percentage_profitable_iterations=0.1111111111111111 |
| yen_depreciation_long_1030 | limited_core_grid_test | 0 | 18 | -825.0 | 0.8902195608782435 | -0.35094969531088044 | 115 |  |  |  |  |  |  |  | summary.percentage_profitable_iterations=0.0 |

## Rejection Rationale

- Five-day yen appreciation, yen appreciation, and yen depreciation variants failed core stability.
- Weak-yen long passed core but failed monkey net robustness: profitable monkey rate 0.345125, median net -980.0, net beat rate 0.773125.
- Strong-yen short passed core and monkey but failed WFA: early_exit=true, stitched OOS net -200.0, PF 0.0, MAR -289.2995, only one stitched OOS trade.
- No post-result NQ rescue is authorized for this campaign.

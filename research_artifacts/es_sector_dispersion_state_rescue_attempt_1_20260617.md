# ES sector dispersion state rescue attempt 1 - 2026-06-17

All five original realized sector-dispersion variants failed `limited_core_grid_test`. Each failed original received exactly one parameter-space-only rescue. The rescues preserved the entry module, setup mode, entry time, data source, costs, session rules, prop rules, validation gates, and core economic edge. Only the dispersion threshold grid and stop/target grids changed.

| variant | run | profitable combo rate | benchmark pass combos | top net | top PF | top trades | top trades/year | terminal stage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| high_1d_dispersion_short_1000 | run1 | 0.0 | 0 | -3397.5 | 0.5856707317073171 | 127 | 85.74436731089156 | limited_core_grid_test |
| high_1d_dispersion_short_1000 | rescue1 | 0.0 | 0 | -1931.25 | 0.8567056204785755 | 110 | 75.52013784191256 | limited_core_grid_test |
| high_5d_dispersion_short_1030 | run1 | 0.0 | 0 | -890.0 | 0.9587772116720704 | 138 | 92.28482972136223 | limited_core_grid_test |
| high_5d_dispersion_short_1030 | rescue1 | 0.037037037037037035 | 0 | 237.5 | 1.0130404941660947 | 95 | 65.32340617462299 | limited_core_grid_test |
| rising_1d_dispersion_short_1130 | run1 | 0.0 | 0 | -2825.0 | 0.8417145258439558 | 130 | 84.76862900676291 | limited_core_grid_test |
| rising_1d_dispersion_short_1130 | rescue1 | 0.25925925925925924 | 0 | 1945.0 | 1.1158600148920328 | 111 | 72.37936784423603 | limited_core_grid_test |
| low_1d_dispersion_long_1200 | run1 | 0.0 | 0 | -2142.5 | 0.7911284426029734 | 136 | 88.36879134726452 | limited_core_grid_test |
| low_1d_dispersion_long_1200 | rescue1 | 0.0 | 0 | -996.25 | 0.9305507145346811 | 118 | 76.6729219042442 | limited_core_grid_test |
| falling_5d_dispersion_long_1330 | run1 | 0.07407407407407407 | 0 | 385.0 | 1.0265151515151516 | 153 | 99.78100026658895 | limited_core_grid_test |
| falling_5d_dispersion_long_1330 | rescue1 | 0.2222222222222222 | 0 | 780.0 | 1.070748299319728 | 109 | 71.7261552512558 | limited_core_grid_test |

Best run by top net was `rising_1d_dispersion_short_1130/rescue1` with top net `1945.0`, PF `1.1158600148920328`, trades/year `72.37936784423603`, but it still had only `0.25925925925925924` profitable-combo rate and `0` benchmark-passing combinations.

Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

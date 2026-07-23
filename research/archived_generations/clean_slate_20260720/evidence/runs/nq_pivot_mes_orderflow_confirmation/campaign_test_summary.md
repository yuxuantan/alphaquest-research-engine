# nq_pivot_mes_orderflow_confirmation Campaign Summary

Date: 2026-06-23

Decision: FAIL

All five frozen variants failed the staged flow. Three failed limited core grid stability; two passed core and failed limited monkey robustness. No candidate strategy report was created.

## Variant Outcomes

| variant_id | terminal_stage | core profitable | benchmark pass | top net | top PF | top trades | monkey net beat | monkey DD beat |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| afternoon_trade_large10_first_confirmed_reversal_window_1500 | limited_monkey_test | 60/81 | 48 | 22775.0 | 1.81998199819982 | 59 | 0.867875 | 0.77 |
| late_morning_trade_large10_first_confirmed_reversal_window_1200 | limited_core_grid_test | 54/81 | 54 | 19392.5 | 1.942756441419543 | 52 |  |  |
| late_morning_trade_large20_first_confirmed_reversal_window_1200 | limited_monkey_test | 69/81 | 61 | 16547.5 | 1.8825333333333334 | 46 | 0.799625 | 0.851125 |
| morning_notional_large10_first_confirmed_reversal_window_1130 | limited_core_grid_test | 54/81 | 17 | 7945.0 | 1.313783570300158 | 47 |  |  |
| morning_notional_large20_first_confirmed_reversal_window_1130 | limited_core_grid_test | 34/81 | 8 | 2085.0 | 1.262429200755192 | 40 |  |  |

Results CSV: `backtest-campaigns/nq_pivot_mes_orderflow_confirmation/campaign_results.csv`

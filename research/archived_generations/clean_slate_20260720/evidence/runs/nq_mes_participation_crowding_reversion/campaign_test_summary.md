# NQ MES Participation Crowding Reversion Campaign Summary

Final verdict: FAIL.

All five predeclared NQ variants were run through the staged workflow after a pre-PnL density reformulation of the two sparse short-checkpoint variants. Two variants passed limited core but failed limited monkey. Three variants failed limited core. No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| variant | terminal stage | core profitable combos | top net | top PF | top trades | top MAR | monkey net beat | monkey DD beat | monkey median net |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| morning_notional_down_reversal_long_1030 | limited_core_grid_test | 42/81 | 8365.0 | 1.2309497515184982 | 48 | 2.899193853685838 | None | None | None |
| morning_notional_up_reversal_short_1030 | limited_monkey_test | 45/54 | 12030.0 | 1.4773809523809525 | 65 | 3.7431889832330394 | 0.8145 | 0.823375 | -1152.5 |
| midday_notional_two_sided_reversal_1200 | limited_monkey_test | 81/81 | 17855.0 | 1.4661879895561358 | 75 | 3.817725067936681 | 0.84225 | 0.476625 | -995.0 |
| afternoon_trade_down_reversal_long_1400 | limited_core_grid_test | 0/54 | -2305.0 | 0.9083863275039745 | 61 | -0.4350498468763505 | None | None | None |
| afternoon_trade_up_reversal_short_1400 | limited_core_grid_test | 0/54 | -570.0 | 0.9862202344977639 | 85 | -0.10512104251711969 | None | None | None |

CSV detail: `backtest-campaigns/nq_mes_participation_crowding_reversion/campaign_results.csv`

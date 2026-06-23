# Methodology Audit: nq_pivot_mes_orderflow_confirmation

Decision: FAIL

## Scope

- Campaign: `nq_pivot_mes_orderflow_confirmation`
- Source NQ campaign: `nq_pivot_filtered_mes_participation_crowding_reversion`
- NQ/MES cache: `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`
- Density audit: `research_artifacts/nq_pivot_mes_orderflow_confirmation_density_audit_20260623.md`
- Aggregate summary: `backtest-campaigns/nq_pivot_mes_orderflow_confirmation/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_pivot_mes_orderflow_confirmation/campaign_results.csv`

## Integrity Notes

- MES participation ranks use same-clock prior-history fields embedded in the cache.
- Pivot structure uses completed OHLC bars and right-side confirmation before a pivot becomes available.
- Native NQ large-trade orderflow confirmation uses only completed 30-minute rolling windows through signal close.
- Entry is emitted at signal close and the staged engine handles next-bar-or-later execution.
- Stop, target, forced flatten, commission, slippage, tick size, point value, and prop-rule settings are read from config.
- The parameter grid was fixed before PnL testing; no rescue was authorized or attempted.

## Staged Outcome

All five frozen variants failed the staged flow. Three failed limited core grid stability; late_morning_trade_large20_first_confirmed_reversal_window_1200 and afternoon_trade_large10_first_confirmed_reversal_window_1500 passed core but failed limited monkey robustness. No WFA, Monte Carlo, incubation, acceptance, or candidate report survivor.

- `afternoon_trade_large10_first_confirmed_reversal_window_1500`: terminal stage `limited_monkey_test`; core top net 22775.0, PF 1.81998199819982, benchmark pass 48/81; monkey net-beat 0.867875, drawdown-beat 0.77.
- `late_morning_trade_large10_first_confirmed_reversal_window_1200`: terminal stage `limited_core_grid_test`; core top net 19392.5, PF 1.942756441419543, benchmark pass 54/81.
- `late_morning_trade_large20_first_confirmed_reversal_window_1200`: terminal stage `limited_monkey_test`; core top net 16547.5, PF 1.8825333333333334, benchmark pass 61/81; monkey net-beat 0.799625, drawdown-beat 0.851125.
- `morning_notional_large10_first_confirmed_reversal_window_1130`: terminal stage `limited_core_grid_test`; core top net 7945.0, PF 1.313783570300158, benchmark pass 17/81.
- `morning_notional_large20_first_confirmed_reversal_window_1130`: terminal stage `limited_core_grid_test`; core top net 2085.0, PF 1.262429200755192, benchmark pass 8/81.

No `candidate_strategy_report.md` was created.

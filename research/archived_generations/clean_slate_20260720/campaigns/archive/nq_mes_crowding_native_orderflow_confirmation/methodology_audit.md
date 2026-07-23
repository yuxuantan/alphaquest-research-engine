# Methodology Audit: nq_mes_crowding_native_orderflow_confirmation

Decision: FAIL

## Scope

- Campaign: `nq_mes_crowding_native_orderflow_confirmation`
- Source ES campaign: `es_extreme_vol_filtered_mes_trend_pullback_crowding`
- Prior failed NQ port: `nq_mes_crowding_vol_filtered_trend_pullback_reversion`
- NQ/MES cache: `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`
- Lagged volatility features: `data/external/nq_lagged_volatility_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_mes_crowding_native_orderflow_window_confirmation_density_audit_20260623.md`
- Aggregate summary: `backtest-campaigns/nq_mes_crowding_native_orderflow_confirmation/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_mes_crowding_native_orderflow_confirmation/campaign_results.csv`

## Integrity Notes

- MES crowding ranks use same-clock prior-session history embedded in the cache.
- The NQ trend window ends before the NQ pullback and native-orderflow confirmation window.
- Lagged volatility features are prior-session values.
- Native NQ signed-flow confirmation uses only completed bars in the configured 15-minute window ending at the signal close.
- Entry is emitted at the signal-bar close and the staged engine handles next-bar-or-later execution.
- Stop, target, forced flatten, commission, slippage, tick size, point value, and prop-rule settings are read from config.
- The parameter grid was fixed before PnL testing; no rescue was authorized or attempted.

## Staged Outcome

All five frozen variants passed limited_core_grid_test and failed limited_monkey_test. Strong 10:30 core profits did not survive randomized-timing robustness, which is the same failure family observed in the prior NQ MES-crowding port.

- `absret5_1030_notional_signed_window15_pressure_reversal`: core top net 21155.0, PF 1.884221525600836, benchmark pass 56/81; monkey net-beat 0.79475, drawdown-beat 0.468625.
- `absret5_1030_signed_window15_pressure_reversal`: core top net 24475.0, PF 1.9827343906846016, benchmark pass 67/81; monkey net-beat 0.854875, drawdown-beat 0.663375.
- `downside20_1030_signed_window15_pressure_reversal`: core top net 16060.0, PF 1.7878341918077016, benchmark pass 59/81; monkey net-beat 0.882125, drawdown-beat 0.579375.
- `range10_1030_signed_window15_pressure_reversal`: core top net 20320.0, PF 1.937701892016613, benchmark pass 43/81; monkey net-beat 0.799875, drawdown-beat 0.524625.
- `vol20_1030_signed_window15_pressure_reversal`: core top net 13045.0, PF 1.5056201550387598, benchmark pass 53/81; monkey net-beat 0.874, drawdown-beat 0.739875.

No `candidate_strategy_report.md` was created.

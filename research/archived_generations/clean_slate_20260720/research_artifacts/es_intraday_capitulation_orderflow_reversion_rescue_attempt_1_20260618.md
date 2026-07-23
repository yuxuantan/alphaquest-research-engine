# ES intraday capitulation orderflow reversion rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space/fixed-parameter rescue for each failed variant. No entry module, stop module, target module, timeframe, data source, cost model, fill model, stage criteria, or edge thesis was changed.

Original campaign:
- Edge: completed downside capitulation below session VWAP with session-local RSI/volume confirmation and completed aggregate sell imbalance.
- Variants: `all_day_5m_capitulation_long_1530`, `late_day_5m_capitulation_long_1530`, `afternoon_5m_capitulation_long_1530`, `all_day_10m_capitulation_long_1530`, `late_day_10m_capitulation_long_1530`.
- Pre-PnL density artifact: `research_artifacts/es_intraday_capitulation_orderflow_reversion_density_audit_20260618.md`.

Original result:
- All five variants failed `limited_core_grid_test`.
- Profitable-combo rate was `0.0` for every original variant.
- No original run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Rescue change:
- Kept the same completed downside capitulation orderflow-reversion mechanic.
- Tightened/shifted only declared values inside existing parameters:
  - `entry.params.max_rsi`: `[30, 35, 40]`
  - `entry.params.min_sell_imbalance`: `[0.04, 0.05, 0.06]`
  - `sl.params.stop_offset_ticks`: `[2, 4, 6]`
  - `tp.params.target_r_multiple`: `[0.5, 0.75, 1.0]`
- Each rescue still had `81` combinations.

Rescue result:
- All five rescues failed `limited_core_grid_test`.
- Profitable-combo rate was `0.0` for every rescue.
- Best rescue: `late_day_10m_capitulation_long_1530/rescue1`, top net `-2477.5`, PF `0.6868878357030016`, MAR `-0.595188936659132`, and `73.57176633697684` trades/year.

Decision: FAIL. The edge expression produced enough trades but did not survive costs and pessimistic execution assumptions even before monkey testing or WFA.

Primary artifacts:
- `backtest-campaigns/es_intraday_capitulation_orderflow_reversion/campaign_test_summary.json`
- `backtest-campaigns/es_intraday_capitulation_orderflow_reversion/campaign_results.csv`
- `backtest-campaigns/es_intraday_capitulation_orderflow_reversion/wfa_table.csv`
- `backtest-campaigns/es_intraday_capitulation_orderflow_reversion/monte_carlo_summary.json`

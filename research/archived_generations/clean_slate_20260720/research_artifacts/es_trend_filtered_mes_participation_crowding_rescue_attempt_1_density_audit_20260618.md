# es_trend_filtered_mes_participation_crowding Rescue Attempt 1 Pre-PnL Density Audit

Date: 2026-06-18

Data: `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`. No external or paid data was downloaded.

Scope: signal-count audit for the one allowed per-failed-variant parameter-space rescue, before rescue PnL was run.

Rescue entry grid: `share_rank_min=[0.4, 0.5, 0.6]`, `min_abs_return_ticks=[2, 3, 4]`. Stop grid: `[0.002, 0.003, 0.004]`. Target grid: `[1.0, 1.5, 2.0]`.

Reason: original morning variants passed core but failed monkey; midday/afternoon variants failed core with profit concentration. The rescue keeps the same mechanics and broadens entry density moderately while removing the tightest stop from the grid.

| Variant | Min signals/year | Max signals/year | Decision |
|---|---:|---:|---|
| `afternoon_notional_trend_pullback_reversal_1400` | 54.3 | 71.9 | approve_for_rescue_testing |
| `early_afternoon_notional_trend_pullback_reversal_1300` | 53.9 | 72.7 | approve_for_rescue_testing |
| `midday_notional_trend_pullback_reversal_1200` | 52.0 | 69.2 | approve_for_rescue_testing |
| `morning_notional_trend_pullback_reversal_1030` | 57.0 | 77.5 | approve_for_rescue_testing |
| `morning_trade_trend_pullback_reversal_1030` | 57.4 | 76.8 | approve_for_rescue_testing |

Result: all rescue entry-grid corners clear the pre-PnL 50 signals/year plausibility floor. This does not evaluate profitability and does not promote the strategy.

Detailed CSV: `research_artifacts/es_trend_filtered_mes_participation_crowding_rescue_attempt_1_density_audit_20260618.csv`.

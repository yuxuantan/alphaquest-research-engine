# NQ High-Semivariance MES Crowding Density Audit

Pre-PnL signal-density audit using completed NQ/MES one-minute RTH bars, NQ return-tick columns, and lagged NQ downside-semivariance ranks. Counts are first signal per session before any stop/target simulation or profitability review.

- source cache: `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`
- feature cache: `data/external/nq_realized_semivariance_features_20110103_20260612.csv`
- period: 2019-05-06 through 2026-06-12
- pass floor: at least 50 signals per year for each predeclared entry combo

| variant | entry combos | passing combos | min trades/year | max trades/year | min latest-year signals |
|---|---:|---:|---:|---:|---:|
| afternoon60_notional_high_downside_window_1530 | 6 | 6 | 78.57 | 108.84 | 67 |
| late_morning30_notional_high_downside_window_1230 | 6 | 6 | 79.98 | 109.12 | 69 |
| midday60_notional_high_downside_window_1430 | 6 | 6 | 80.12 | 109.69 | 69 |
| morning15_notional_high_downside_window_1130 | 6 | 6 | 84.48 | 112.64 | 72 |
| morning15_trade_high_downside_window_1130 | 6 | 6 | 86.17 | 114.05 | 75 |

CSV detail: `research_artifacts/nq_high_semivariance_mes_trend_pullback_crowding_density_audit_20260622.csv`

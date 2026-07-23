# NQ MES-Crowding Native Orderflow Confirmation Density Audit

Signal-count screen only. No PnL, stops, targets, WFA, or trade outcomes were inspected. Counts use completed 1m NQ/MES cache rows, lagged NQ volatility features, and native completed NQ orderflow through the signal bar close.

## Selected Fixed Pullback Thresholds

- `absret5_1030_large20_vwap_pressure_reversal`: fixed `min_abs_return_ticks=8`; grid signal density min/median/max = 12.53/14.78/17.32 per year.
- `absret5_1030_signed_pressure_reversal`: fixed `min_abs_return_ticks=8`; grid signal density min/median/max = 0.00/3.80/30.84 per year.
- `absret5_1200_signed_absorption_reversal`: fixed `min_abs_return_ticks=8`; grid signal density min/median/max = 0.00/0.70/12.25 per year.
- `downside20_1030_signed_pressure_reversal`: fixed `min_abs_return_ticks=8`; grid signal density min/median/max = 0.00/3.80/30.98 per year.
- `range10_1030_signed_pressure_reversal`: fixed `min_abs_return_ticks=8`; grid signal density min/median/max = 0.00/3.94/31.82 per year.

CSV: `research_artifacts/nq_mes_crowding_native_orderflow_confirmation_density_audit_20260623.csv`

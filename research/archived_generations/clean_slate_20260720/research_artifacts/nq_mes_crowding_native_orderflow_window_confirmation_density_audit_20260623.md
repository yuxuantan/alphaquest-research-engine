# NQ MES-Crowding Native Orderflow Window Confirmation Density Audit

Signal-count screen only. No PnL, stops, targets, WFA, or trade outcomes were inspected. Confirmation uses completed native NQ orderflow over the configured lookback window ending at the signal bar close.

Final pre-PnL density knobs: `min_trend_return_ticks=8`, `min_orderflow_imbalance` grid `[0.0, 0.005, 0.01]`, and selected campaign gate `min_trades_per_year=35`.

## Selected Five Variants

- `absret5_1030_signed_window15_pressure_reversal`: PASS; fixed `min_abs_return_ticks=16`; grid signal density min/median/max = 40.55/50.13/58.86 per year.
- `downside20_1030_signed_window15_pressure_reversal`: PASS; fixed `min_abs_return_ticks=16`; grid signal density min/median/max = 39.85/49.14/57.87 per year.
- `range10_1030_signed_window15_pressure_reversal`: PASS; fixed `min_abs_return_ticks=16`; grid signal density min/median/max = 41.54/51.25/60.41 per year.
- `vol20_1030_signed_window15_pressure_reversal`: PASS; fixed `min_abs_return_ticks=20`; grid signal density min/median/max = 38.86/48.30/56.46 per year.
- `absret5_1030_notional_signed_window15_pressure_reversal`: PASS; fixed `min_abs_return_ticks=20`; grid signal density min/median/max = 40.55/49.14/57.87 per year.

## Density-Rejected Alternatives

- `absret5_1030_large20_window15_vwap_pressure_reversal`: rejected before PnL; grid min density was 21.54 signals/year.
- `absret5_1200_signed_window30_pressure_reversal`: rejected before PnL; grid min density was 18.30 signals/year.
- `absret5_1030_signed_window30_pressure_reversal`: rejected before PnL; grid min density was 22.39 signals/year.
- `range10_1030_signed_window30_pressure_reversal`: rejected before PnL; grid min density was 22.39 signals/year.

CSV: `research_artifacts/nq_mes_crowding_native_orderflow_window_confirmation_density_audit_20260623.csv`
Extra screen CSV: `research_artifacts/nq_mes_crowding_native_orderflow_window_confirmation_extra_density_20260623.csv`

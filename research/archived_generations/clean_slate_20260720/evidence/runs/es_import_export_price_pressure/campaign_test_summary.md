# ES Import/Export Price Pressure Campaign Summary

Decision: **FAIL**

All five original variants failed. Each failed variant received exactly one parameter-space-only rescue that widened stop distance while preserving entry mechanics, macro thresholds, signal time, flow column, TP grid, data, costs, sessions, and gates. The best rescue, import_disinflation_large20_long_1200/rescue1, passed limited core with profitable-combo rate 0.9259259259259259 and 13 benchmark-passing combinations, but failed limited monkey/stress because the max-drawdown beat rate was 0.49333333333333335, below the required 0.90, despite net-profit beat rate 0.9066666666666666. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. TP was not adjusted because all target_r_multiple values were already >= 1.0R.

Best original: `import_disinflation_large20_long_1200/run1` with profitable-combo rate 0.3333333333333333, benchmark-passing combinations 3, top net 1285.0, PF 1.1513991163475699, MAR 0.46342591529032295, and trades/year 84.54790066400578.

Best rescue: `import_disinflation_large20_long_1200/rescue1`. Terminal stage: `limited_monkey_test`. Limited-core profitable-combo rate 0.9259259259259259; limited-monkey net-profit beat rate 0.9066666666666666; max-drawdown beat rate 0.49333333333333335.

Artifacts:
- `backtest-campaigns/es_import_export_price_pressure/campaign_results.csv`
- `backtest-campaigns/es_import_export_price_pressure/trade_logs_manifest.csv`
- `backtest-campaigns/es_import_export_price_pressure/equity_curves_manifest.csv`
- `backtest-campaigns/es_import_export_price_pressure/wfa_table.csv`
- `backtest-campaigns/es_import_export_price_pressure/monte_carlo_summary.csv`

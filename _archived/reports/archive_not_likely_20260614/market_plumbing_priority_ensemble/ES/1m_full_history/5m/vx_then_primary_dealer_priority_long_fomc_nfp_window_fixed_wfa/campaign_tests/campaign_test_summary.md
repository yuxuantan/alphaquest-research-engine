# Campaign Test Summary

- Campaign: `market_plumbing_priority_ensemble`
- Variant: `vx_then_primary_dealer_priority_long_fomc_nfp_window_fixed_wfa`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>summary.windows actual=1 expected={'min': 10}<br>stitched_oos_metrics.profit_factor actual=0.0 expected={'min': 1.5}<br>stitched_oos_metrics.mar actual=0.0 expected={'min': 1.5, 'dynamic_min': 'length_adjusted_mar', 'span_metric': 'summary.oos_evaluation_years', 'span_years': 0.5010266940451745}<br>stitched_oos_metrics.expectancy_r actual=0.0 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=0 expected={'min': 500}<br>stitched_oos_metrics.win_rate actual=0.0 expected={'min': 0.45} |

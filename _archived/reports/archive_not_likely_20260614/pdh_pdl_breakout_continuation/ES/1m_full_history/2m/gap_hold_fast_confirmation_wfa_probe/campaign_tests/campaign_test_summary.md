# Campaign Test Summary

- Campaign: `pdh_pdl_breakout_continuation`
- Variant: `gap_hold_fast_confirmation_wfa_probe`
- Timeframe: `2m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>summary.windows actual=1 expected={'min': 10}<br>stitched_oos_metrics.profit_factor actual=0.0 expected={'min': 1.5}<br>stitched_oos_metrics.mar actual=0.0 expected={'min': 1.5}<br>stitched_oos_metrics.expectancy_r actual=0.0 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=0 expected={'min': 500}<br>stitched_oos_metrics.win_rate actual=0.0 expected={'min': 0.45} |

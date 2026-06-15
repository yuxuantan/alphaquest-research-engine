# Campaign Test Summary

- Campaign: `cftc_tff_hedging_pressure`
- Variant: `broad_spx_open_interest_expansion`
- Timeframe: `15m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>summary.windows actual=2 expected={'min': 10}<br>stitched_oos_metrics.profit_factor actual=0.5221663072130361 expected={'min': 1.5}<br>stitched_oos_metrics.mar actual=-7.893186519788556 expected={'min': 1.5, 'dynamic_min': 'length_adjusted_mar', 'span_metric': 'summary.oos_evaluation_years', 'span_years': 0.999315537303217}<br>stitched_oos_metrics.expectancy_r actual=-0.15258974358974356 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=25 expected={'min': 500}<br>stitched_oos_metrics.win_rate actual=0.44 expected={'min': 0.45} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

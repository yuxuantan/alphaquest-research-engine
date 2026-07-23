# Campaign Test Summary

- Campaign: `es_semivariance_orderflow_confirmation`
- Variant: `badvol_signed_multitime_twosided`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>stitched_oos_metrics.profit_factor actual=0.5956962025316456 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=-0.9333625893824896 expected={'min': 0.4} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

# Campaign Test Summary

- Campaign: `nq_cboe_vix_term_structure_intraday`
- Variant: `curve_flattening_short_1200`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>stitched_oos_metrics.profit_factor actual=0.700375201000536 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=-0.8860051507478656 expected={'min': 0.4} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

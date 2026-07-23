# ES Dollar Risk-Appetite Intraday Rescue Audit - 2026-06-17

## Decision

FAIL.

`es_dollar_risk_appetite_intraday` produced no candidate strategy. All five
original variants failed `limited_core_grid_test`; all five one-time
parameter-space rescues also failed `limited_core_grid_test`. No run reached
monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen
validation, or candidate reporting.

## Data And Availability

- ES data: existing local Sierra RTH cache.
- External feature data: free official FRED DTWEXBGS nominal broad dollar index
  cache, `data/external/fred_dtwexbgs_nominal_broad_dollar_2006_2026.csv`.
- Feature file:
  `data/external/es_dollar_risk_appetite_features_20110103_20260609.csv`.
- Paid data: none.
- Lookahead control: each ES session uses the most recent dollar observation on
  or before `session_date - 1 business day`; no same-day dollar close is used.

## Rescue Scope

Every failed variant received exactly one rescue attempt. The rescues changed
only declared threshold, stop, and target parameter spaces. They did not change
the economic edge, data source, one-business-day availability rule, setup mode,
direction, entry time, entry module, stop module, target module, timeframe, data
window, costs, fill rules, session rules, prop rules, or validation gates.

## Results

| Variant | Run | Stage | Profitable Combo Rate | Benchmark-Passing Combos | Top Net | Top PF | Top Trades/Year |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| dollar_up_risk_off_short_1000 | run1 | limited_core_grid_test | 0.0000 | 0 | -2970.00 | 0.7732 | 112.57 |
| dollar_up_risk_off_short_1000 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -2970.00 | 0.7732 | 112.57 |
| dollar_down_risk_on_long_1030 | run1 | limited_core_grid_test | 0.0000 | 0 | -1147.50 | 0.9034 | 86.46 |
| dollar_down_risk_on_long_1030 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -1880.62 | 0.7975 | 95.35 |
| high_dollar_up_short_1130 | run1 | limited_core_grid_test | 0.0000 | 0 | -295.00 | 0.9749 | 97.42 |
| high_dollar_up_short_1130 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -2982.50 | 0.2318 | 115.99 |
| five_day_dollar_up_short_1200 | run1 | limited_core_grid_test | 0.0000 | 0 | -1385.00 | 0.8604 | 110.30 |
| five_day_dollar_up_short_1200 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -3444.38 | 0.5822 | 126.74 |
| five_day_dollar_down_long_1330 | run1 | limited_core_grid_test | 0.0000 | 0 | -2210.00 | 0.5958 | 69.99 |
| five_day_dollar_down_long_1330 | rescue1 | limited_core_grid_test | 0.0000 | 0 | -2012.50 | 0.5681 | 80.45 |

## Artifact Index

- Campaign source: `campaigns/es_dollar_risk_appetite_intraday/campaign.yaml`
- Aggregate summary:
  `backtest-campaigns/es_dollar_risk_appetite_intraday/campaign_test_summary.json`
- Density audit:
  `research_artifacts/es_dollar_risk_appetite_intraday_density_audit_20260617.md`
- Ledger rows: `research_ledger.csv` rows for `es_dollar_risk_appetite_intraday`
- Methodology note: `methodology_audit.md`

## Active Sweep After Update

- Active campaigns: 46
- Active source variants: 230
- Rescue configs: 230
- Raw variant-level reports: 478
- Aggregate passes: 0
- Active variants missing an original run: 0
- Active variants missing `rescue1`: 0

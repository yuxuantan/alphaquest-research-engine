# NQ Retail Inventory Demand Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_retail_inventory_demand_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_retail_inventory_demand_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_retail_inventory_demand_features_20110103_20260612.csv`
- Density pass rows: 35/45
- Passing variants: 2/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| inventory_sales_falling_long_1330 | 8/9 | 31.307143 | 169.580357 | FAIL |
| inventory_sales_high_short_1200 | 3/9 | 0.000000 | 164.585964 | FAIL |
| retail_1m_strength_long_1130 | 9/9 | 64.219780 | 146.969643 | PASS |
| retail_3m_strength_short_1030 | 9/9 | 65.223214 | 167.841071 | PASS |
| retail_3m_weakness_long_1000 | 6/9 | 0.000000 | 121.415522 | FAIL |

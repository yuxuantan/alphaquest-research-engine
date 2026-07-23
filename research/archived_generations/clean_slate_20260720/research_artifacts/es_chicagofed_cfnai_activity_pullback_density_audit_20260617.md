# ES Chicago Fed CFNAI activity pullback density audit - 2026-06-17

Campaign: `es_chicagofed_cfnai_activity_pullback`

Purpose: pre-PnL eligibility check for the user rule to avoid campaigns that are
unlikely to reach at least 50 trades per year. This audit was performed before
staged testing and before any PnL results for this campaign.

Data:

- ES bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- CFNAI session features: `data/external/es_chicagofed_cfnai_activity_features_20110103_20260609.csv`
- Period: 2011-01-03 through 2026-06-09
- Sessions: 3817
- Availability rule: latest monthly CFNAI row with `eligible_date <= session_date`

Predeclared entry frequency check:

| variant | driver | signal time | entry driver grid | pullback grid bps | lowest grid-corner frequency | default-grid signal count |
|---|---:|---:|---:|---:|---:|---:|
| `production_income_weak_pullback_long_1100` | `P_I` | 11:00 | 0.0, 0.1, 0.2 | 0, -5, -10 | 51.1/year | 1158 |
| `headline_activity_weak_pullback_long_1100` | `CFNAI` | 11:00 | 0.05, 0.15, 0.25 | 0, -5, -10 | 56.3/year | 1129 |
| `ma3_activity_weak_pullback_long_1130` | `CFNAI_MA3` | 11:30 | 0.0, 0.1, 0.2 | 0, -5, -10 | 58.6/year | 1229 |
| `diffusion_weak_pullback_long_1200` | `DIFFUSION` | 12:00 | 0.05, 0.15, 0.25 | 0, -5, -10 | 56.1/year | 1164 |
| `employment_hours_weak_pullback_long_1330` | `EU_H` | 13:30 | 0.1, 0.2, 0.3 | 0, -5, -10 | 68.4/year | 1410 |

Decision: frequency eligible for testing. All declared grid corners were at or
above 50 signals per year before PnL inspection.

Guardrail: if these variants fail, a rescue may only change fixed parameters or
parameter space. It may not change the CFNAI availability rule, driver column,
direction, entry time, entry module, stop module, target module, data window,
timeframe, costs, or validation gates.

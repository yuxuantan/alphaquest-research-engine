# NQ Treasury Rate Shock Intraday Density Audit - 2026-06-30

Pre-PnL audit only. The ES Treasury-rate source grids were checked against the NQ RTH session cache before any NQ PnL inspection. No density adjustment was needed.

Data: `data/external/nq_treasury_rate_state_features_20110103_20260612.csv` with 3,813 rows from 2011-01-03 through 2026-06-12. Each NQ session uses the latest Treasury 2-year/10-year observation strictly before the session date. Minimum selected-grid density is 52.854052 signals/year.

Full density table: `research_artifacts/nq_treasury_rate_shock_intraday_density_audit_20260630.csv`.

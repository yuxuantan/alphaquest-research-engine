# NQ EMV Macro-News Intraday Density Audit - 2026-06-30

Pre-PnL audit only. The ES EMV macro-news source grids were checked against the NQ RTH session cache before any NQ PnL inspection. No density adjustment was needed.

Data: `data/external/nq_emv_macro_news_features_20110103_20260612.csv` with 3,813 rows from 2011-01-03 through 2026-06-12. Each NQ session uses only monthly FRED EMV observations available after observation month-end plus 21 calendar days. Minimum selected-grid density is 81.289014 signals/year.

Full density table: `research_artifacts/nq_emv_macro_news_intraday_density_audit_20260630.csv`.

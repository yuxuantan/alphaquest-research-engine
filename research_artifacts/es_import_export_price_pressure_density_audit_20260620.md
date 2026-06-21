# ES Import/Export Price Pressure Density Audit - 2026-06-20

This is a pre-PnL density gate for `campaigns/es_import_export_price_pressure`. It uses only local Sierra ES RTH 1-minute aggregate-orderflow data and the already-built free public FRED/BLS import/export price feature file. No paid market data was downloaded.

Windows used for the screen:
- Full: 2011-01-03 to 2026-06-09
- Limited-core reference: 2012-07-19 to 2014-02-03, the 10%-to-20% slice of available data used here to avoid latest data and avoid the COVID period
- WFA90 reference: 2011-01-03 to 2024-11-22
- Latest one year: 2025-06-09 to 2026-06-09

| variant | setup | fixed macro threshold | entry time | flow | full tpy | limited 10% tpy | WFA90 tpy | latest 1y tpy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| import_disinflation_signed_long_1030 | import_all_mom3_rank_120m <= 0.45 | 0.45 | 10:30 | signed_volume | 53.34 | 90.66 | 52.64 | 66.05 |
| import_disinflation_large20_long_1200 | import_all_mom3_rank_120m <= 0.45 | 0.45 | 12:00 | large20_signed_volume | 55.15 | 97.14 | 54.01 | 66.05 |
| import_disinflation_large20_long_1430 | import_all_mom3_rank_120m <= 0.45 | 0.45 | 14:30 | large20_signed_volume | 54.57 | 95.85 | 53.94 | 62.04 |
| core_pressure_signed_short_1100 | core_vs_headline_rank_120m >= 0.45 | 0.45 | 11:00 | signed_volume | 61.57 | 90.02 | 62.72 | 54.04 |
| core_pressure_large20_short_1200 | core_vs_headline_rank_120m >= 0.40 | 0.40 | 12:00 | large20_signed_volume | 54.11 | 80.95 | 53.15 | 57.04 |


Rejected pre-test shapes:
- Export-demand longs failed the limited 10% reference window with only about 22-25 trades/year despite full/latest density above 50/year.
- Broad import-pressure shorts failed the limited 10% reference window; the only dense short regime came from core-vs-headline import-price pressure, not headline import prices alone.
- Core-relief pullback longs failed the trade-count gate and were not authored.

Mechanics decision before PnL: approve the five variants above for staged testing. Each has fixed macro thresholds that are materially tied to the economic thesis and clears the 50/year density gate in the full, limited, WFA90, and latest-year reference windows at fixed review settings.

Source density grids:
- `research_artifacts/es_import_export_price_pressure_density_screen_grid_20260620.csv`
- `research_artifacts/es_import_export_price_pressure_density_extra_screen_20260620.csv`

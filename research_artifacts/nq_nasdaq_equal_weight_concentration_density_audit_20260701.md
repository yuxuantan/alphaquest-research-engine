# NQ Nasdaq Equal-Weight Concentration Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged QQQ-minus-QQQE state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_nasdaq_equal_weight_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 21/21.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| concentration_volume_pressure_long_1330 | 9 | 9 | 58.291109 | 55.213483 | 65 | True |
| equal_weight_1d_breadth_short_1000 | 3 | 3 | 79.307632 | 92.022472 | 87 | True |
| equal_weight_5d_breadth_short_1130 | 3 | 3 | 79.307632 | 80.696629 | 92 | True |
| qqq_1d_concentration_long_1000 | 3 | 3 | 79.505901 | 92.022472 | 85 | True |
| qqq_5d_concentration_long_1030 | 3 | 3 | 81.752950 | 97.685393 | 97 | True |

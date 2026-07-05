# NQ Fama-French Style Factor Rotation Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged Fama-French style-factor state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_fama_french_style_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 15/15.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| cma_63d_conservative_short_1200 | 3 | 3 | 71.178600 | 69.370787 | 95 | True |
| hml_21d_growth_strength_long_1030 | 3 | 3 | 76.796223 | 75.033708 | 70 | True |
| hml_21d_value_strength_short_1000 | 3 | 3 | 68.072384 | 60.876404 | 82 | True |
| hml_63d_extreme_two_sided_1330 | 3 | 3 | 132.377655 | 97.685393 | 164 | True |
| rmw_63d_quality_strength_long_1130 | 3 | 3 | 62.586939 | 126.000000 | 58 | True |

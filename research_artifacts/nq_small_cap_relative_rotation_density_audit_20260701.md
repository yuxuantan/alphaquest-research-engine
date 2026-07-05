# NQ Small-Cap Relative Rotation Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged IWM/QQQ state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_small_cap_relative_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 21/21.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| iwm_1d_strength_long_1000 | 3 | 3 | 87.899292 | 80.696629 | 91 | True |
| iwm_1d_weakness_short_1000 | 3 | 3 | 90.146341 | 84.943820 | 80 | True |
| iwm_5d_strength_long_1030 | 3 | 3 | 85.520063 | 80.696629 | 97 | True |
| iwm_5d_weakness_short_1130 | 3 | 3 | 90.542880 | 76.449438 | 78 | True |
| iwm_attention_strength_long_1330 | 9 | 9 | 64.966168 | 58.044944 | 72 | True |

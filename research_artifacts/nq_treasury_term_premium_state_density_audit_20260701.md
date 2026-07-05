# NQ Treasury Term Premium State Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged Treasury term-premium state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_treasury_term_premium_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 15/15.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| falling_21d_term_premium_rebound_long_1200 | 3 | 3 | 85.453973 | 84.943820 | 55 | True |
| high_21d_term_premium_rebound_long_1330 | 3 | 3 | 61.727773 | 138.741573 | 85 | True |
| high_21d_term_premium_short_1000 | 3 | 3 | 61.727773 | 138.741573 | 85 | True |
| high_5d_term_premium_short_1130 | 3 | 3 | 63.842644 | 150.067416 | 84 | True |
| rising_5d_term_premium_short_1030 | 3 | 3 | 63.710464 | 66.539326 | 59 | True |

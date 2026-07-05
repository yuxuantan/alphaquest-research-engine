# NQ Infectious Disease EMV State Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged infectious-disease EMV state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_infectious_disease_emv_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 15/15.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| high_1d_emv_rebound_long_1200 | 3 | 3 | 65.098348 | 50.966292 | 53 | True |
| high_21d_emv_rebound_long_1330 | 3 | 3 | 98.341463 | 76.449438 | 50 | True |
| high_21d_emv_riskoff_short_1000 | 3 | 3 | 98.341463 | 76.449438 | 50 | True |
| high_7d_emv_short_1130 | 3 | 3 | 89.022817 | 72.202247 | 56 | True |
| rising_5d_emv_short_1030 | 3 | 3 | 67.741935 | 65.123596 | 66 | True |

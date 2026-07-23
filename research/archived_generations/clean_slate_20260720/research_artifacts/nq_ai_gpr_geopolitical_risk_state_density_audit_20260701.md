# NQ AI-GPR Geopolitical Risk State Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged AI-GPR state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_ai_gpr_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 15/15.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| high_acts_gpr_rebound_long_1200 | 3 | 3 | 65.891424 | 77.865169 | 94 | True |
| high_ai_gpr_rebound_long_1330 | 3 | 3 | 66.948859 | 94.853933 | 80 | True |
| high_ai_gpr_short_1000 | 3 | 3 | 66.948859 | 94.853933 | 80 | True |
| high_threats_gpr_short_1130 | 3 | 3 | 73.227380 | 120.337079 | 81 | True |
| rising_ai_gpr_short_1030 | 3 | 3 | 68.006294 | 82.112360 | 64 | True |

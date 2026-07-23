# NQ Corporate Equity Supply State Density Audit

Verdict: PASS.

No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged corporate equity supply state would allow a fixed-time NQ signal.

Feature CSV: `data/external/nq_corporate_equity_supply_features_20110103_20260612.csv`
Annualized full/limited-window threshold: 50.00 signals/year.
Latest-252-session threshold: 50 signals.
Limited-core proxy window: 2021-07-13 through 2022-03-28.

Passing entry rows: 15/15.
Passing variants: 5/5.

## Variant Summary

| variant_id | declared_entry_rows | passing_entry_rows | min_full_signals_per_year | min_limited_signals_per_year | min_latest_252_signals | variant_pass_density |
| --- | --- | --- | --- | --- | --- | --- |
| high_1q_net_equity_short_1000 | 3 | 3 | 73.359559 | 252.000000 | 128 | True |
| high_4q_net_equity_short_1030 | 3 | 3 | 65.428796 | 252.000000 | 252 | True |
| high_equity_share_short_1200 | 3 | 3 | 69.658537 | 252.000000 | 123 | True |
| low_debt_minus_equity_short_1330 | 3 | 3 | 65.230527 | 252.000000 | 252 | True |
| rising_4q_net_equity_short_1130 | 3 | 3 | 69.724626 | 164.224719 | 199 | True |

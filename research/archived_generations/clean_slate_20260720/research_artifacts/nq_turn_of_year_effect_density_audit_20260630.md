# NQ Turn-of-Year Effect Density Audit - 2026-06-30

Verdict: FAIL before staged PnL.

No NQ PnL, stop/target outcome, trade net, benchmark row, WFA, Monte Carlo, simulated incubation, or acceptance OOS result was inspected. This audit counts only deterministic calendar signal opportunities on prepared one-minute NQ bars.

Session span: 2011-01-03 through 2026-06-12 (15.441 years).
Limited-core reference window from the canonical random-fraction stage window: 2011-02-22 through 2012-09-07 (1.544 years).
Latest-session density window: last 252 sessions.

## Variant Summary

| variant_id | entry_combos | min_full_signals_per_year | min_limited_core_signals_per_year | min_latest_252_signals | full_failures | limited_core_failures | latest_failures |
| --- | --- | --- | --- | --- | --- | --- | --- |
| december_window_long_1500 | 1 | 4.792287 | 3.238032 | 5 | 1 | 1 | 1 |
| january_first2_open_long_1000 | 1 | 2.007580 | 1.295213 | 2 | 1 | 1 | 1 |
| santa_momentum_confirmed_midday_long_1200 | 3 | 2.072340 | 3.238032 | 1 | 3 | 3 | 3 |
| santa_window_midday_long_1200 | 1 | 6.799867 | 4.533245 | 7 | 1 | 1 | 1 |
| santa_window_open_long_1000 | 1 | 6.799867 | 4.533245 | 7 | 1 | 1 | 1 |

Every declared entry-grid row failed at least one density gate. Under fail-closed rules this campaign must not proceed to staged PnL without an explicit pre-PnL reformulation decision.

## Failing Rows

| variant_id | entry_combo | full_signals | signals_per_year_full | limited_core_signals | signals_per_year_limited_core | latest_252_signals |
| --- | --- | --- | --- | --- | --- | --- |
| december_window_long_1500 | fixed_entry | 74 | 4.792287 | 5 | 3.238032 | 5 |
| january_first2_open_long_1000 | fixed_entry | 31 | 2.007580 | 2 | 1.295213 | 2 |
| santa_momentum_confirmed_midday_long_1200 | entry.params.min_session_return_bps=0 | 48 | 3.108511 | 6 | 3.885638 | 3 |
| santa_momentum_confirmed_midday_long_1200 | entry.params.min_session_return_bps=10 | 37 | 2.396144 | 6 | 3.885638 | 2 |
| santa_momentum_confirmed_midday_long_1200 | entry.params.min_session_return_bps=20 | 32 | 2.072340 | 5 | 3.238032 | 1 |
| santa_window_midday_long_1200 | fixed_entry | 105 | 6.799867 | 7 | 4.533245 | 7 |
| santa_window_open_long_1000 | fixed_entry | 105 | 6.799867 | 7 | 4.533245 | 7 |

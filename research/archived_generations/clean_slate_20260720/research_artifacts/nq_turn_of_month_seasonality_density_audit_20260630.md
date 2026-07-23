# NQ Turn-of-Month Seasonality Density Audit - 2026-06-30

Verdict: FAIL before staged PnL.

No NQ PnL, stop/target outcome, trade net, or benchmark result was inspected. This audit counts only calendar signal opportunities on prepared 5-minute NQ bars.

Session span: 2011-01-03 through 2026-06-12 (15.439 years).
Latest-session density window: last 252 sessions.

## Variant Summary

| variant_id | entry_combos | min_full_signals_per_year | min_latest_252_signals | full_failures | latest_failures |
| --- | --- | --- | --- | --- | --- |
| classic_turn_window_1000_long | 9 | 24.160002 | 23 | 5 | 5 |
| early_month_first_days_1000_long | 3 | 15.804398 | 16 | 3 | 3 |
| late_turn_window_1300_long | 9 | 24.160002 | 23 | 5 | 5 |
| month_end_last_days_1000_long | 3 | 8.355604 | 7 | 3 | 3 |
| opening_turn_window_0935_long | 9 | 24.160002 | 23 | 5 | 5 |

At least one declared entry-grid combination failed density. Under fail-closed rules this campaign must not proceed to staged PnL without an explicit pre-PnL reformulation decision.

## Failing Rows

| variant_id | entry_combo | signals_per_year_full | signals_latest_252_sessions |
| --- | --- | --- | --- |
| classic_turn_window_1000_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=1 | 24.160002 | 23 |
| classic_turn_window_1000_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=3 | 40.029172 | 39 |
| classic_turn_window_1000_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=4 | 48.255231 | 47 |
| classic_turn_window_1000_long | entry.params.first_calendar_days=4,entry.params.last_calendar_days=1 | 39.510995 | 38 |
| classic_turn_window_1000_long | entry.params.first_calendar_days=5,entry.params.last_calendar_days=1 | 47.737054 | 47 |
| early_month_first_days_1000_long | entry.params.first_calendar_days=2 | 15.804398 | 16 |
| early_month_first_days_1000_long | entry.params.first_calendar_days=3 | 23.447508 | 23 |
| early_month_first_days_1000_long | entry.params.first_calendar_days=5 | 39.381451 | 40 |
| late_turn_window_1300_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=1 | 24.160002 | 23 |
| late_turn_window_1300_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=3 | 40.029172 | 39 |
| late_turn_window_1300_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=4 | 48.255231 | 47 |
| late_turn_window_1300_long | entry.params.first_calendar_days=4,entry.params.last_calendar_days=1 | 39.510995 | 38 |
| late_turn_window_1300_long | entry.params.first_calendar_days=5,entry.params.last_calendar_days=1 | 47.737054 | 47 |
| month_end_last_days_1000_long | entry.params.last_calendar_days=1 | 8.355604 | 7 |
| month_end_last_days_1000_long | entry.params.last_calendar_days=2 | 16.452119 | 15 |
| month_end_last_days_1000_long | entry.params.last_calendar_days=4 | 32.450833 | 31 |
| opening_turn_window_0935_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=1 | 24.160002 | 23 |
| opening_turn_window_0935_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=3 | 40.029172 | 39 |
| opening_turn_window_0935_long | entry.params.first_calendar_days=2,entry.params.last_calendar_days=4 | 48.255231 | 47 |
| opening_turn_window_0935_long | entry.params.first_calendar_days=4,entry.params.last_calendar_days=1 | 39.510995 | 38 |
| opening_turn_window_0935_long | entry.params.first_calendar_days=5,entry.params.last_calendar_days=1 | 47.737054 | 47 |

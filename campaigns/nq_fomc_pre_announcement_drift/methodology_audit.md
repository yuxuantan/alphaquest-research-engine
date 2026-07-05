# NQ FOMC Pre-Announcement Drift Methodology Audit

Created: 2026-06-30

Verdict before staged testing: TEST

This campaign is a weak-prior NQ symbol-transfer from the failed `es_fomc_pre_announcement_drift` family. It is included because no active NQ scheduled-FOMC pre-announcement drift campaign was found.

## No-Lookahead Contract

The event calendar `data/external/fomc_scheduled_decision_dates_20110101_20260609.csv` contains only scheduled FOMC decision dates known from Federal Reserve calendars. Signals use only the event date, the configured event-day offset, and completed same-session RTH bars before the configured entry time. The strategy does not use the policy decision, statement text, surprise data, press conference, minutes, or post-announcement bars. Decision-day variants flatten by 12:00 ET.

## Variant Set

Exactly five variants are declared:

- `decision_day_open_long_1000`
- `decision_day_late_morning_long_1130`
- `decision_day_momentum_confirmed_long_1130`
- `decision_day_low_range_long_1130`
- `prior_day_late_long_1500`

Each variant uses `fomc_pre_announcement_drift` for entry, `percent_from_entry` for stop loss, and `fixed_r` for take profit. The declared grids contain 9, 9, 27, 27, and 9 combinations respectively.

## Current Outcome

Final verdict: FAIL

All five variants failed `limited_core_grid_test`. The best profitable-rate was `decision_day_low_range_long_1130` at 0/27, or 0.0, below the 0.70 gate. Across all official variants, 0/81 combinations were profitable, 0 rows passed the benchmark suite, and 0 iterations violated Apex rules.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.

# Methodology Audit - NQ Prior-Session Level Breakout Continuation

Verdict: FAIL.

Rejected before PnL because signal-density screening showed sparse direct prior high/low break and retest variants. Only `gap_hold_two_sided_continuation` cleared the density gate; running one dense sibling would violate the five-variant campaign structure.

Testing outcome:
- `gap_hold_two_sided_continuation`: failed pre-PnL signal-density gate: limited_min_signals_per_year=68.77; full_history_min_signals_per_year=70.02; required_min=50.
- `midday_two_sided_close_break`: failed pre-PnL signal-density gate: limited_min_signals_per_year=9.73; full_history_min_signals_per_year=6.28; required_min=50.
- `morning_prior_high_breakout_long`: failed pre-PnL signal-density gate: limited_min_signals_per_year=12.33; full_history_min_signals_per_year=13.41; required_min=50.
- `morning_prior_low_breakout_short`: failed pre-PnL signal-density gate: limited_min_signals_per_year=16.87; full_history_min_signals_per_year=18.52; required_min=50.
- `retest_hold_two_sided_breakout`: failed pre-PnL signal-density gate: limited_min_signals_per_year=17.52; full_history_min_signals_per_year=19.89; required_min=50.

No staged PnL test was run. No `candidate_strategy_report.md` was created.

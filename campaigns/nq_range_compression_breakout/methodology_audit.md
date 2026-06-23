# Methodology Audit - NQ Range Compression Breakout

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded edge: NQ volatility expansion after completed prior-session NR4/NR7-style range compression.
- Exactly five variants were authored before NQ PnL testing, using the ES range-compression templates with NQ data, costs, and a pre-PnL NQ range-cap grid.
- Entry logic used completed prior-session ranges and completed 5-minute breakout bars with next-bar-open execution.
- No PnL was inspected and no staged backtest was run.

Pre-PnL density outcome:
- `id_nr4_prior_session_breakout`: failed pre-PnL signal-density gate: limited_min_signals_per_year=12.33; full_history_min_signals_per_year=5.44; required_min=50.
- `nr4_prior_session_breakout`: failed pre-PnL signal-density gate: limited_min_signals_per_year=50.60; full_history_min_signals_per_year=23.06; required_min=50.
- `nr7_opening_range_15_long_breakout`: failed pre-PnL signal-density gate: limited_min_signals_per_year=22.06; full_history_min_signals_per_year=9.97; required_min=50.
- `nr7_opening_range_15_short_breakout`: failed pre-PnL signal-density gate: limited_min_signals_per_year=16.87; full_history_min_signals_per_year=8.36; required_min=50.
- `nr7_opening_range_30_breakout`: failed pre-PnL signal-density gate: limited_min_signals_per_year=33.09; full_history_min_signals_per_year=15.35; required_min=50.

Rejected before PnL because sparse signal availability would make WFA, trade-count, and prop-rule evidence unreliable. No `candidate_strategy_report.md` was created.

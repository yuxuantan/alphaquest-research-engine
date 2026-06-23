# Methodology Audit - NQ VWAP Pullback Continuation

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded edge: completed-bar VWAP pullback continuation on NQ.
- Exactly five variants were authored before NQ PnL testing, using ES VWAP pullback templates with NQ data, costs, and pre-PnL signal-density grid adjustments.
- Session VWAP, opening-drive state, trend counts, pullback touch, and reclaim/reject signals used completed 5-minute bars only.
- All variants used NQ point value 20.0, tick size 0.25, one tick slippage, commissions, intraday flattening, and configured prop rules.
- No rescue was authorized after PnL results.

Pre-PnL density:
- `research_artifacts/nq_vwap_pullback_continuation_initial_density_rejected_20260622.md` rejected the initial NQ-scaled strict corners before PnL.
- `research_artifacts/nq_vwap_pullback_continuation_density_reform1_rejected_20260622.md` rejected the first density reformulation before PnL.
- `research_artifacts/nq_vwap_pullback_continuation_density_audit_20260622.md` approved all five variants after signal-density-only grid widening.

Testing outcome:
- `failed_vwap_break_two_sided`: failed limited core grid gate: profitable_combos=0/54; top_net=-1400.0; top_pf=0.5947901591895803; top_trades=73; top_mar=-0.5551699330104689.
- `midday_trend_reclaim_two_sided`: failed limited core grid gate: profitable_combos=7/36; top_net=1352.5; top_pf=1.3105625717566016; top_trades=55; top_mar=0.870205808871298.
- `morning_opening_drive_pullback_long`: failed limited core grid gate: profitable_combos=11/54; top_net=2917.5; top_pf=1.3658307210031349; top_trades=87; top_mar=1.5940783528349052.
- `morning_opening_drive_pullback_short`: failed limited core grid gate: profitable_combos=0/54; top_net=-355.0; top_pf=0.8536082474226804; top_trades=60; top_mar=-0.2357539687571774.
- `morning_trend_reclaim_two_sided`: failed limited core grid gate: profitable_combos=0/36; top_net=-1320.0; top_pf=0.7760814249363868; top_trades=140; top_mar=-0.5007310890687274.

No rescue was authorized or attempted after PnL results. No `candidate_strategy_report.md` was created.

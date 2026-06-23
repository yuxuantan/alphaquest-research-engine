# Methodology Audit - NQ Semivariance Orderflow Confirmation

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded composite edge: lagged NQ realized semivariance state with same-session NQ price and completed aggregate orderflow confirmation.
- Exactly five variants were authored before NQ PnL testing.
- Each variant used two entry parameters, one stop parameter, and one target parameter; each grid had 36 combinations.
- Entry used completed 5-minute bars with signal-on-close and next-bar-open execution; lagged semivariance features were shifted by one completed RTH session.
- All variants used NQ point value 20.0, tick size 0.25, one tick slippage, commissions, intraday flattening, and configured prop rules.

Pre-PnL density:
- `research_artifacts/nq_semivariance_orderflow_confirmation_density_audit_20260622.md` approved all five variants for limited-core signal density before PnL review.
- `downside_share_signed_multitime_short` had one full-history sparse parameter corner at 44.62 signals/year; the staged WFA/trade-count gates were left to reject it if selected.

Testing outcome:
- `badvol_signed_multitime_short`: failed WFA after core+monkey pass: early_exit=True; stitched_net=-11505.0; stitched_pf=0.7031350793446007; stitched_mar=-0.2748944193289918; stitched_trades_per_year=65.1975349477991.
- `downside_share_signed_multitime_short`: failed WFA after core+monkey pass: early_exit=True; stitched_net=-8030.0; stitched_pf=0.5696677384780279; stitched_mar=-0.8992446669898104; stitched_trades_per_year=81.11581281025592.
- `badvol_signed_multitime_twosided`: failed limited core grid gate: profitable_combos=6/36; top_net=1082.5; top_pf=1.061003099464638; top_trades=197; top_mar=0.29523508273112575.
- `semivar_balance_signed_multitime_twosided`: failed limited core grid gate: profitable_combos=0/36; top_net=-415.0; top_pf=0.9605513307984791; top_trades=177; top_mar=-0.19682808326569906.
- `low_badvol_signed_multitime_long`: failed limited core grid gate: profitable_combos=0/36; top_net=-1160.0; top_pf=0.8503225806451613; top_trades=97; top_mar=-0.34529836789214613.

No rescue was authorized or attempted. No `candidate_strategy_report.md` was created.

# Methodology Audit - NQ MES Participation Crowding Reversion

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded edge: NQ mean reversion after completed NQ moves with unusually high same-clock MES participation.
- Exactly five variants were authored before staged PnL testing.
- Each variant used at most two entry parameters, one stop parameter, and one target parameter; grids were 54 or 81 combinations.
- Entry used completed one-minute bars with next-bar-open execution; MES same-clock participation ranks are precomputed from prior same-clock observations.
- All variants used NQ point value 20.0, tick size 0.25, one tick slippage, commissions, intraday flattening, and configured prop rules.

Pre-PnL density:
- The first fixed-checkpoint density audit is preserved at `research_artifacts/nq_mes_participation_crowding_reversion_initial_density_rejected_20260622.md`.
- `morning_notional_up_reversal_short_1030` and `afternoon_trade_up_reversal_short_1400` were reformulated before PnL to use first-signal windows rather than sparse single checkpoints.
- The final density audit at `research_artifacts/nq_mes_participation_crowding_reversion_density_audit_20260622.md` approved all five variants for limited-core signal density.
- `afternoon_trade_down_reversal_long_1400` and `morning_notional_down_reversal_long_1030` had sparse full-history parameter corners; staged gates rejected both before WFA.

Testing outcome:
- `morning_notional_down_reversal_long_1030`: failed limited core grid gate: profitable_combos=42/81; top_net=8365.0; top_pf=1.2309497515184982; top_trades=48; top_mar=2.899193853685838.
- `morning_notional_up_reversal_short_1030`: failed limited monkey gate after core pass: profitable_rate=0.441625; median_net=-1152.5; net_beat_rate=0.8145; dd_beat_rate=0.823375.
- `midday_notional_two_sided_reversal_1200`: failed limited monkey gate after core pass: profitable_rate=0.464125; median_net=-995.0; net_beat_rate=0.84225; dd_beat_rate=0.476625.
- `afternoon_trade_down_reversal_long_1400`: failed limited core grid gate: profitable_combos=0/54; top_net=-2305.0; top_pf=0.9083863275039745; top_trades=61; top_mar=-0.4350498468763505.
- `afternoon_trade_up_reversal_short_1400`: failed limited core grid gate: profitable_combos=0/54; top_net=-570.0; top_pf=0.9862202344977639; top_trades=85; top_mar=-0.10512104251711969.

No rescue was authorized or attempted after staged results. No `candidate_strategy_report.md` was created.

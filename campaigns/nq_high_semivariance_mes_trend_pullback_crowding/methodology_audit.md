# Methodology Audit - NQ High-Semivariance MES Crowding Trend-Pullback Reversion

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded composite edge: MES participation crowding during completed NQ trend pullbacks conditioned on lagged high NQ downside semivariance.
- Exactly five variants were authored before testing.
- Each variant used no more than two entry parameters, one stop parameter, and one target parameter.
- Entry used completed one-minute bars with next-bar open execution; no current-session semivariance or future daily levels were used.
- All variants used NQ point value 20.0, tick size 0.25, one tick slippage, commissions, intraday flattening, and configured prop rules.

Pre-PnL density:
- `research_artifacts/nq_high_semivariance_mes_trend_pullback_crowding_density_audit_20260622.md` approved all five variant shapes for signal density before PnL review.

Testing outcome:
- `afternoon60_notional_high_downside_window_1530`: failed limited monkey gate after core pass: profitable_rate=0.468; median_net=-1335.0; net_beat_rate=0.816375; dd_beat_rate=0.590375.
- `late_morning30_notional_high_downside_window_1230`: failed limited core grid gate: profitable_combos=18/54; top_net=10165.0; top_pf=1.1694449074845807; top_trades=85; top_mar=2.284271271231375.
- `midday60_notional_high_downside_window_1430`: failed limited core grid gate: profitable_combos=27/54; top_net=28687.5; top_pf=1.3915847665847665; top_trades=96; top_mar=3.1871332779097465.
- `morning15_notional_high_downside_window_1130`: failed limited core grid gate: profitable_combos=2/54; top_net=3375.0; top_pf=1.0466998754669987; top_trades=86; top_mar=0.3451071201246235.
- `morning15_trade_high_downside_window_1130`: failed limited core grid gate: profitable_combos=18/54; top_net=14750.0; top_pf=1.2042653372109127; top_trades=90; top_mar=1.731962627036529.

No rescue was authorized or attempted. No candidate_strategy_report.md was created.
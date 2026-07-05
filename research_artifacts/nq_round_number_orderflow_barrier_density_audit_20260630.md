# NQ Round-Number Orderflow Barrier Density Audit

Pre-performance density check only. Counts use completed 5-minute RTH bars aggregated from the NQ Sierra one-minute orderflow cache. No PnL, stop, target, WFA, monkey, Monte Carlo, prop-rule, or holdout result was inspected.

Source cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
Prepared data period: 2011-01-03 through 2026-06-12 RTH, America/New_York.

Declared campaign grid:
- Support/rejection variants: fixed 25-point barriers, buffer ticks [0, 1], signed-volume absorption thresholds [0.01, 0.03, 0.05].
- Midday two-sided large10 absorption reclaim: fixed 25-point barriers, buffer ticks [0, 1], large10 absorption thresholds [0.10, 0.20, 0.30].
- Breakout variants: 25- and 50-point barriers, fixed buffer 1 tick, signed-volume alignment thresholds [0.01, 0.03, 0.05].

Pre-PnL rejected corners:
- 50-point support/rejection barriers failed limited-core and/or latest-252 density for some threshold corners.
- 100-point breakout barriers failed limited-core and/or latest-252 density for some threshold corners.
- 50-point midday large10 absorption passed density but was not declared because adding barrier interval as a tunable would exceed the two-entry-parameter cap for that variant.

Declared density result: 30/30 entry rows passed; 5/5 variants passed all declared rows.
Rejected nondeclared corner failures: 18/24.

Summary by declared variant:

| variant | declared_rows | passing_rows | min_full_signals_per_year | min_limited_core_signals_per_year | min_latest_252_signals |
| --- | --- | --- | --- | --- | --- |
| midday_two_sided_large10_absorption_reclaim | 6 | 6 | 173.948072 | 115.050285 | 220 |
| morning_resistance_buy_absorption_short | 6 | 6 | 72.037766 | 60.990512 | 69 |
| morning_support_sell_absorption_long | 6 | 6 | 78.250197 | 70.000474 | 72 |
| round_number_downside_flow_breakout_short | 6 | 6 | 73.557828 | 53.366698 | 80 |
| round_number_upside_flow_breakout_long | 6 | 6 | 75.540519 | 51.287476 | 78 |

Detail CSV: `research_artifacts/nq_round_number_orderflow_barrier_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_round_number_orderflow_barrier_density_summary_20260630.csv`

Decision: PASS for authoring and staged testing of the declared five-variant campaign. This is not a trading pass and does not inspect profitability.

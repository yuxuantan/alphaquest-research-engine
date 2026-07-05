# NQ ChartFanatics JadeCap session-liquidity FVG density audit - 2026-07-01

Scope: pre-PnL signal-density check only. This audit counted completed-bar entry signals using the actual `session_liquidity_fvg_reversal` entry module. It did not inspect trade PnL, stops, targets, equity curves, WFA, monkey, Monte Carlo, or holdout results.

Data:
- RTH source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Session-level source: `data/external/nq_asia_london_session_levels_20110103_20260529.csv`
- Strategy timeframe: `5m`
- Full configured sessions: `3803`
- Limited-core proxy window: `2011-02-22` through `2012-09-07` (`371` sessions)

Gate: every declared entry-grid row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core proxy window, and at least 50 signals in the latest 252 sessions before any staged PnL is inspected.

| Variant | Rows | Pass rows | Min full/year | Min limited/year | Min latest-252 | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `asia_high_failed_sweep_short_1130` | 9 | 9 | 100.72 | 101.21 | 91 | PASS |
| `asia_high_fvg_reject_short_1200` | 9 | 9 | 76.93 | 71.32 | 67 | PASS |
| `asia_low_failed_sweep_long_1130` | 9 | 9 | 93.83 | 92.38 | 83 | PASS |
| `asia_low_fvg_reject_long_1200` | 9 | 9 | 72.89 | 76.08 | 52 | PASS |
| `london_two_sided_fvg_reject_1200` | 9 | 9 | 124.18 | 120.23 | 108 | PASS |

Decision: approve for staged testing.
Detail CSV: `research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_audit_20260701.csv`
Summary CSV: `research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_summary_20260701.csv`

Verdict: PASS.

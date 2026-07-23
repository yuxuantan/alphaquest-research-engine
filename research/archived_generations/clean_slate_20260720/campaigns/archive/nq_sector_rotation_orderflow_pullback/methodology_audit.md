# Methodology Audit - NQ Sector-Rotation Orderflow Pullback

Verdict: FAIL as of 2026-06-30T13:15:44+08:00.

Source and duplicate review:
- Source ES campaign: `es_sector_rotation_orderflow_pullback`, which failed limited core; best rescue reached 54/81 profitable combinations, below the 70% gate.
- This NQ port is distinct from fixed-time NQ sector-rotation risk appetite and same-day sector opening-breadth orderflow because it combines lagged sector state with live NQ VWAP/EMA pullback and orderflow confirmation.

No-lookahead and execution checks:
- Sector features use ETF observations available with a one-business-day lag before the NQ session.
- VWAP/EMA pullback and orderflow confirmation use completed 5-minute NQ bars only; entry is next-bar open or later.
- No future NQ bar, future sector close, final session VWAP, final high/low, or post-entry orderflow is used.

Pre-PnL density result:
- Detail CSV: `research_artifacts/nq_sector_rotation_orderflow_pullback_density_audit_20260630.csv`
- Audit artifact: `research_artifacts/nq_sector_rotation_orderflow_pullback_density_audit_20260630.md`
- Required floor: every declared entry-grid corner should reach at least 50 signals/year in both full-history and limited-core windows.
- Result: density failed before PnL. No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.

Variant density summary:
- `cyclical_vwap_reclaim_signed_long_1400`: 8/9 entry corners passed all windows; min full 49.10/year; min limited-core 57.74/year.
- `defensive_ema_pullback_signed_short_1530`: 5/9 entry corners passed all windows; min full 41.50/year; min limited-core 52.30/year.
- `defensive_vwap_reject_large10_short_1130`: 3/9 entry corners passed all windows; min full 40.58/year; min limited-core 45.51/year.
- `financial_industrial_ema_pullback_large10_long_1500`: 3/9 entry corners passed all windows; min full 41.24/year; min limited-core 44.83/year.
- `growth_vwap_reclaim_large10_long_1130`: 3/9 entry corners passed all windows; min full 45.21/year; min limited-core 44.15/year.

Terminal decision:
- FAIL. No rescue was authorized or run.

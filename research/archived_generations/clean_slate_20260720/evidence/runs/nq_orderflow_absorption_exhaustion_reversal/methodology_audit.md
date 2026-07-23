# Methodology Audit - NQ Orderflow Absorption Exhaustion Reversal

Verdict: FAIL as of 2026-06-30T13:08:22+08:00.

Source and duplicate review:
- Source ES campaign: `es_orderflow_absorption_exhaustion_reversal`, which failed before WFA; only one original reached limited monkey and it failed robustness.
- This NQ port is distinct from NQ morning orderflow momentum because it fades same-clock signed-flow pressure rather than following it.
- It is distinct from NQ capitulation, VPIN toxicity, MES divergence, opening-drive inventory, and prior-session level campaigns because it requires fixed-slot rolling signed-flow rank, high effort-vs-result rank, and weak completed-window displacement.

No-lookahead and execution checks:
- Rolling orderflow, return, and effort-vs-result features use completed 1-minute bars only.
- Same-clock ranks are computed against prior same-clock observations only.
- The signal is evaluated on the completed bar whose close equals the configured slot time; entry is no earlier than next-bar open.
- No final session high/low, VWAP, daily range, future orderflow, or post-entry path is used.

Pre-PnL density result:
- Detail CSV: `research_artifacts/nq_orderflow_absorption_exhaustion_reversal_density_audit_20260630.csv`
- Audit artifact: `research_artifacts/nq_orderflow_absorption_exhaustion_reversal_density_audit_20260630.md`
- Required floor: every declared entry-grid corner should reach at least 50 signals/year in both the full-history and limited-core reference windows.
- Result: density failed before PnL. No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.

Variant density summary:
- `afternoon_60m_absorption_fade_1400`: 0/9 entry corners passed all windows; min full 0.99/year; max full 5.68/year; min limited-core 4.08/year; max limited-core 10.19/year.
- `early_5m_absorption_fade_1000`: 0/9 entry corners passed all windows; min full 1.52/year; max full 7.40/year; min limited-core 4.08/year; max limited-core 18.34/year.
- `late_30m_absorption_fade_1500`: 0/9 entry corners passed all windows; min full 1.12/year; max full 6.87/year; min limited-core 3.40/year; max limited-core 13.58/year.
- `late_morning_15m_absorption_fade_1130`: 0/9 entry corners passed all windows; min full 1.06/year; max full 6.81/year; min limited-core 2.72/year; max limited-core 13.58/year.
- `midday_30m_absorption_fade_1230`: 0/9 entry corners passed all windows; min full 0.86/year; max full 6.08/year; min limited-core 0.68/year; max limited-core 10.19/year.

Terminal decision:
- FAIL. No rescue was authorized or run.

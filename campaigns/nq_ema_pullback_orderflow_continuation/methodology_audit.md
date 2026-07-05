# NQ EMA Pullback Orderflow Continuation Methodology Audit

Status: authored pending pre-PnL density and staged validation.

- One campaign, one edge: same-session dynamic EMA pullback continuation with completed aggregate orderflow confirmation.
- Duplicate screen: distinct from active NQ VWAP pullback, Chart Fanatics measured-move pullback, MES-crowding pullback reversion, impulse-pause continuation, and fixed-time momentum families.
- Timing: EMA state uses prior completed closes; the signal bar is evaluated only after close; entries are next-bar open or later.
- Data: NQ Sierra RTH 1-minute orderflow cache aggregated deterministically to 5-minute bars by the repo pipeline.
- Parameter discipline: 27 combinations per variant, with two entry tunables, one stop tunable, and fixed 1R target.
- Rescue policy: no rescue authorized for this NQ search unless the user explicitly allows it after a failure.

## Pre-PnL Density Audit

- Decision: PASS. All 45 declared entry-grid rows passed full-history, limited-core proxy, and latest-252-session density gates before any NQ PnL was inspected.
- Artifact: `research_artifacts/nq_ema_pullback_orderflow_continuation_density_audit_20260630.md`.

## Staged Validation Result

Decision: FAIL. Four variants failed limited_core_grid_test. The short-only late-morning variant passed limited core and limited monkey but failed walk_forward_analysis by early exit before stitched OOS trading. No candidate report was produced.

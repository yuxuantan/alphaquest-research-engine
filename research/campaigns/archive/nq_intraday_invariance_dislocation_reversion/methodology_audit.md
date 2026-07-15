# Methodology Audit: NQ Intraday Trading-Invariance Dislocation Reversion

Decision: FAIL

## Scope

This campaign tested exactly five NQ variants expressing one edge: completed-bar transaction-clock dislocation mean reversion. The signal used NQ completed OHLCV, aggregate signed volume, completed trade count, average trade size, and prior-only same-clock invariance ranks. It did not use future VWAP, final session ranges, future orderflow, print sequencing, or intra-minute fill ordering.

## Pre-PnL Controls

- Density audit passed before staged PnL: `research_artifacts/nq_intraday_invariance_dislocation_reversion_density_audit_20260623.md`.
- Grid was frozen before PnL: invariance rank threshold `[0.85, 0.90, 0.95]`, minimum return ticks `[8, 12, 16]`, stop percent `[0.0015, 0.0025, 0.0035]`, target R `[1.0, 1.5, 2.0]`.
- Same-clock ranks were prior-only: the current completed score is appended after the signal decision.
- Entries occur no earlier than the next bar open after a completed signal bar.
- Same-day flatten times and prop constraints came from each config.

## Verification

- Unit tests: `PYTHONPATH=src pytest -q tests/test_strategy_modules.py -k intraday_invariance_dislocation` -> 3 passed, 164 deselected.
- Preflight: `PYTHONPATH=src python3 -m research.preflight --config <five configs> --pytest-args "tests/test_strategy_modules.py -k intraday_invariance_dislocation"` -> PASS for 5 configs.

## Staged Outcome

All five variants failed `limited_core_grid_test`. Each variant tested 81 combinations, had 0 profitable combinations, and had 0 benchmark-passing combinations. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Verdict

FAIL. The NQ transaction-clock dislocation mean-reversion edge did not survive the first objective rejection gate and should not be rescued without explicit user authorization and a new predeclared research reason.

# Methodology Audit: NQ Overnight Inventory Sweep Reversion

Decision: FAIL

## Scope

This campaign tested exactly five variants expressing one edge: same-day reversion after completed NQ RTH sweeps and reclaims of pre-known ETH overnight highs/lows. The final variants and parameter grid were fixed before any PnL test.

## Data Controls

A local NQ Databento ETH/RTH explicit-roll cache was generated from existing monthly parquet shards: `data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet`. Roll dates were translated from the ES MotiveWave/Rithmic CME equity-index quarterly roll calendar to NQ contract symbols. This avoids same-day volume roll selection but requires manual roll-calendar review before any future promotion.

## Pre-PnL Controls

- Density audit passed after rejecting midpoint, open-outside-range, and VWAP-filtered variants before PnL: `research_artifacts/nq_overnight_inventory_sweep_reversion_density_audit_20260623.md`.
- Grid was frozen before PnL: `min_overnight_range_points=[20,40,60]`, `reclaim_buffer_ticks=[0,1,2]`, `stop_pct=[0.002,0.0035,0.005]`, `target_r_multiple=[1.0,1.5,2.0]`.
- Overnight highs/lows are computed from completed ETH bars for the current RTH session and are known before RTH begins.
- Entries occur no earlier than the next 5-minute bar after a completed reclaim bar.

## Verification

- Unit tests: `PYTHONPATH=src pytest -q tests/test_strategy_modules.py -k overnight_inventory_reversion` -> 6 passed, 161 deselected.
- Preflight: `PYTHONPATH=src python3 -m research.preflight --config <five configs> --pytest-args "tests/test_strategy_modules.py -k overnight_inventory_reversion"` -> PASS for 5 configs.

## Staged Outcome

All five variants failed `limited_core_grid_test`; no branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Verdict

FAIL. The NQ overnight sweep/reclaim edge did not survive the first objective rejection gate and should not be rescued without explicit user authorization and a new predeclared research reason.

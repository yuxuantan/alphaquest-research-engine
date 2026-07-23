# Core-grid signal-density reporting - 2026-06-17

Reason: the `pdh_buy_absorption_long` core-grid run had zero trades across all
81 parameter combinations. That raised a valid methodology question: a failed
variant can be caused by fixed gates or entry parameter space that do not
actually express the intended edge in the selected limited-core regime.

Change made:

- `src/propstack/research/core_grid.py` now writes per-combination diagnostics:
  `signals_generated`, `entries_opened`, `trades_closed`, total entry
  rejections, and rejection buckets.
- `core_grid_summary.json` now includes a `signal_density` section with
  zero-signal, zero-trade, and `>=50 trades/year` counts.
- The existing staged benchmark-table gates are unchanged. These fields are
  diagnostic evidence for deciding whether a failure is caused by economics,
  density, or over-restrictive mechanics.

Interpretation rule:

- If all combinations have zero signals or zero trades, the run should be read
  as a mechanics/parameter-space density failure. Widening stop/target space
  cannot repair that. A rescue may only adjust allowed fixed values or declared
  parameter ranges that preserve the same core mechanic.
- If signals/trades exist but fewer combinations reach the 50 trades/year
  feasibility floor, future variants should be reformulated before PnL testing
  rather than optimized after seeing results.

Verification:

`PYTHONPATH=src python3 -m pytest tests/test_core_grid.py -q`

Result: `7 passed`.

# Positive Delta Dislocation NQ Test - 2026-06-14

## Rule Tested

Long-only NQ setup from the user-supplied screenshot:

- Current close is above the previous RTH high.
- The latest completed RTH-aligned 60-minute candle is negative.
- That same 60-minute candle has positive signed volume delta.
- Minimum signed volume delta is 500.
- Exit first trigger: +10000 dollars per NQ contract, -10000 dollars per NQ contract, or flatten at RTH end of day.

In NQ terms, the fixed bracket is 500.00 points per contract because NQ is 20 dollars per point.

## Data Prep

Built a validated NQ Sierra orderflow cache from `data/raw/NQ/sierra-nq-trades`:

- CSV: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.csv`
- Parquet: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Validation report: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.validation.json`
- Dropped-session audit: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.dropped_sessions.csv`

Validation summary:

- Rows: 1487070
- Sessions: 3813
- First timestamp: 2011-01-03 09:30:00
- Last timestamp: 2026-06-12 15:59:00
- Dropped sessions: 197
- Duplicate timestamps: 0
- Invalid OHLC rows: 0
- Missing session segments: 0
- Non-regular sessions after filtering: 0
- Low side-coverage sessions after filtering: 0
- Minimum retained session side-volume coverage: 0.994648

## Implementation

- Entry module: `positive_delta_dislocation`
- Config: `configs/campaigns/positive_delta_dislocation/variants/NQ/1m/pdh_negative_hour_positive_delta_long_10000_bracket.yaml`
- Dataset: corrected Sierra NY cache `nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny`
- Feature method: 1-minute bars with `trade_orderflow_features.windows: [60]`, evaluated only at completed RTH-aligned hourly closes from 10:30 through 15:30 ET.
- Grid size: 125 combinations across close-above-PDH ticks, negative-hour ticks, and minimum hour delta.

## Commands

The cache builder was run with provisional output names, then the artifacts were renamed to the validated retained span shown in the data-prep section.

```bash
PYTHONPATH=src python3 tools/build_sierra_trade_orderflow_cache.py \
  --raw-dir data/raw/NQ/sierra-nq-trades \
  --roll-calendar configs/data/ES/motivewave_rithmic_roll_calendar.csv \
  --root-symbol NQ \
  --output-csv data/cache/orderflow/nq_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.csv \
  --output-parquet data/cache/orderflow/nq_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet \
  --report-json data/cache/orderflow/nq_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.validation.json \
  --dropped-sessions-csv data/cache/orderflow/nq_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.dropped_sessions.csv

PYTHONPATH=src pytest -q tests/test_strategy_modules.py -k "fixed_dollar_per_contract or positive_delta_dislocation" tests/test_sierra_trade_orderflow_cache.py tests/test_config_layout.py

PYTHONPATH=src python3 -m propstack.run_core \
  --config configs/campaigns/positive_delta_dislocation/variants/NQ/1m/pdh_negative_hour_positive_delta_long_10000_bracket.yaml \
  --skip-validation

PYTHONPATH=src python3 -m propstack.run_campaign_stages \
  --config configs/campaigns/positive_delta_dislocation/variants/NQ/1m/pdh_negative_hour_positive_delta_long_10000_bracket.yaml \
  --skip-validation
```

## Exact Full-History Core Result

Report root:

`data/reports/campaigns/positive_delta_dislocation/NQ/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny/1m/pdh_negative_hour_positive_delta_long_10000_bracket/core`

Metrics:

- Total trades: 169
- Trades per year: 10.96
- Net profit: 4495.00
- Profit factor: 1.0831
- Expectancy R: 0.00316
- Win rate: 57.99%
- Max drawdown: 11225.00
- Max drawdown pct: 7.08%
- CAGR: 0.19%
- MAR: 0.0271
- Best day concentration: 85.87%
- Apex rule violations: 0

Exit distribution:

- EOD flatten: 169
- Stop: 0
- Target: 0

The 500-point NQ target and stop were never hit in the exact full-history run. Like ES, this behaves as an intraday directional EOD-flatten bet rather than a true bracket-driven strategy.

Yearly net PnL was unstable. The largest recent warning is 2026 YTD through 2026-06-12: 6 trades, -10115.00 net PnL.

## Staged Campaign Result

Report root:

`data/reports/campaigns/positive_delta_dislocation/NQ/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny/1m/pdh_negative_hour_positive_delta_long_10000_bracket/campaign_tests`

Overall result: failed and halted at `limited_core_grid_test`.

Limited core grid:

- Total combinations tested: 125
- Profitable iterations: 51
- Percentage profitable iterations: 40.80%
- Required profitable iteration rate: 70.00%
- Apex rule violating iterations: 0
- Benchmark-passing combinations: 0

Top limited-grid row by net profit:

- `min_close_above_prev_high_ticks`: 4
- `min_negative_hour_ticks`: 1
- `min_hour_delta`: 500
- Trades: 17
- Trades per year: 12.27
- Net profit: 1965.00
- Profit factor: 4.3305
- Expectancy R: 0.01206
- MAR: 3.1613
- Best day concentration: 49.36%
- Benchmark passed: false
- Failure reason: `min_expectancy_r;min_trades_per_year;preferred_min_total_trades`

Base-threshold limited-grid row:

- `min_close_above_prev_high_ticks`: 1
- `min_negative_hour_ticks`: 1
- `min_hour_delta`: 500
- Trades: 20
- Trades per year: 14.43
- Net profit: 1300.00
- Profit factor: 2.0359
- Expectancy R: 0.00700
- MAR: 2.0836
- Best day concentration: 74.62%
- Benchmark passed: false

## Verdict

Rejected. NQ is materially better than the ES version on the exact full-history core run, but it still fails the first staged robustness gate. Only 40.8% of nearby threshold combinations are profitable versus the 70% requirement, and zero combinations pass the benchmark screen.

The full-history exact run is also too sparse and concentrated for promotion: 169 trades over roughly 15.4 years, 10.96 trades per year, 85.87% best-day concentration, no target or stop hits, and a weak 0.00316 expectancy R. This should remain research-only and should not be added to live or incubation tracking.

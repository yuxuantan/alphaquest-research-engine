# Positive Delta Dislocation ES Test - 2026-06-14

## Rule Tested

Long-only ES setup from the user-supplied screenshot:

- Current close is above the previous RTH high.
- The latest completed RTH-aligned 60-minute candle is negative.
- That same 60-minute candle has positive signed volume delta.
- Minimum signed volume delta is 500.
- Exit first trigger: +10000 dollars per ES contract, -10000 dollars per ES contract, or flatten at RTH end of day.

In ES terms, the fixed bracket is 200.00 points per contract because ES is 50 dollars per point.

## Implementation

- Entry module: `positive_delta_dislocation`
- Config: `configs/campaigns/positive_delta_dislocation/variants/ES/1m/pdh_negative_hour_positive_delta_long_10000_bracket.yaml`
- Dataset: corrected Sierra NY cache `sierra_trade_orderflow_1m_20101229_20260609_full_rth_ny`
- Feature method: 1-minute bars with `trade_orderflow_features.windows: [60]`, evaluated only at completed RTH-aligned hourly closes from 10:30 through 15:30 ET.

## Commands

```bash
PYTHONPATH=src pytest -q tests/test_strategy_modules.py tests/test_config_layout.py
PYTHONPATH=src python3 -m propstack.run_core --config configs/campaigns/positive_delta_dislocation/variants/ES/1m/pdh_negative_hour_positive_delta_long_10000_bracket.yaml --skip-validation
PYTHONPATH=src python3 -m propstack.run_campaign_stages --config configs/campaigns/positive_delta_dislocation/variants/ES/1m/pdh_negative_hour_positive_delta_long_10000_bracket.yaml --skip-validation
```

## Exact Full-History Core Result

Report root:

`data/reports/campaigns/positive_delta_dislocation/ES/sierra_trade_orderflow_1m_20101229_20260609_full_rth_ny/1m/pdh_negative_hour_positive_delta_long_10000_bracket/core`

Metrics:

- Total trades: 268
- Trades per year: 17.45
- Net profit: -16802.50
- Profit factor: 0.7534
- Expectancy R: -0.00577
- Win rate: 45.90%
- Max drawdown: 19025.00
- Max drawdown pct: 12.54%
- CAGR: -0.77%
- MAR: -0.0614
- Apex rule violations: 0

Exit distribution:

- EOD flatten: 267
- Stop: 1
- Target: 0

The 200-point target was not hit in the full-history exact run. The fixed bracket is so wide that the strategy mostly behaves like a same-day directional close-to-close bet after entry.

## Staged Campaign Result

Report root:

`data/reports/campaigns/positive_delta_dislocation/ES/sierra_trade_orderflow_1m_20101229_20260609_full_rth_ny/1m/pdh_negative_hour_positive_delta_long_10000_bracket/campaign_tests`

Overall result: failed and halted at `limited_core_grid_test`.

Limited core grid:

- Total combinations tested: 125
- Profitable iterations: 10
- Percentage profitable iterations: 0.08
- Required profitable iteration rate: 0.70
- Apex rule violating iterations: 0
- Benchmark-passing combinations: 0

Top limited-grid row by net profit:

- `min_close_above_prev_high_ticks`: 1
- `min_negative_hour_ticks`: 2
- `min_hour_delta`: 2000
- Trades: 16
- Net profit: 882.50
- Profit factor: 1.3541
- Expectancy R: 0.00602
- MAR: 0.4073
- Benchmark passed: false

## Verdict

Rejected. The exact rule loses over full history, and the staged robustness screen fails immediately because only 8% of nearby threshold combinations are profitable. The few profitable limited-window rows are too sparse and fail trade-count, expectancy, MAR, and best-day-concentration requirements.

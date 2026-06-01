# Prop Stack Automation

Research skeleton for futures prop-firm strategy testing. The project is organized around **campaigns**:

```text
one campaign config -> one strategy/symbol/dataset experiment -> one grouped report folder
```

The normal workflow is:

```text
download/export data
place raw CSV under data/raw/
create one campaign YAML
run validation/backtest/grid/monkey/WFA/Monte Carlo
review campaign_summary.json and runs_index.csv
```

## Install

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
```

## Project Layout

```text
configs/
  campaigns/
    pdh_pdl_sweep/
      ES/
        sample.yaml

data/
  raw/
    ES/
    NQ/
  cleaned/
  reports/
    strategies/
      pdh_pdl_sweep/
        ES/
          sample/
            campaign_config.yaml
            campaign_summary.json
            config_hash.txt
            input_data_hash.txt
            run_manifest.json
            validation/
            backtest/
            grid/
            monkey/
            wfa/
            monte_carlo/
          runs_index.csv

src/
  propstack/

tests/
```

## 1. Download Or Export Data

Start with 1-minute OHLCV futures data exported from your data vendor or platform.

Save raw files without modifying them:

```text
data/raw/ES/es_1m_20221201-20260529.csv
data/raw/NQ/nq_1m_20221201-20260529.csv
```

The currently supported headerless format is:

```text
yyyyMMdd HHmmss,O,H,L,C,V
```

Example:

```csv
20240102 083000,100.00,101.00,99.50,100.50,100
20240102 083100,100.50,100.75,99.00,99.75,110
```

Expected columns by position:

```text
timestamp, open, high, low, close, volume
```

For ES/NQ CME data, use exchange timezone:

```text
America/Chicago
```

## 2. Create A Campaign Config

Copy the sample campaign:

```bash
cp configs/campaigns/pdh_pdl_sweep/ES/sample.yaml configs/campaigns/pdh_pdl_sweep/ES/es_5y_baseline.yaml
```

Edit the new file:

```yaml
campaign_id: es_5y_baseline
strategy_name: pdh_pdl_sweep
symbol: ES

data:
  raw_csv: data/raw/ES/es_1m_20221201-20260529.csv
  csv_format: yyyymmdd_hhmmss_ohlcv
  has_header: false
  timestamp_format: "%Y%m%d %H%M%S"
  symbol: ES
  timezone: America/Chicago
  exchange_timezone: America/Chicago
  rth_start: "08:30:00"
  rth_end: "15:00:00"
  eth_start: "17:00:00"
  eth_end: "08:29:00"
  rolling_volume_window: 3
```

The `campaign_id` is mandatory. All runs using the same campaign file write to:

```text
data/reports/strategies/{strategy_name}/{symbol}/{campaign_id}/
```

## 3. Configure Strategy Rules

In the same campaign file:

```yaml
strategy:
  strategy_name: pdh_pdl_sweep
  entry:
    module: pdh_pdl_sweep_reclaim
    params:
      reclaim_window_bars: 3
      min_volume_ratio: 0.0
      start_time: "08:30:00"
      end_time: "14:45:00"
      max_trades_per_day: 3
      allow_long: true
      allow_short: true
  tp:
    module: fixed_r
    params:
      target_r_multiple: 1.5
  sl:
    module: sweep_extreme
    params:
      stop_offset_ticks: 1
  flatten_time: "14:55:00"
```

The strategy is composed of three explicit modules:

```text
entry -> detects setup and emits a signal
tp    -> calculates target price
sl    -> calculates stop price
```

Each module implementation lives in its own file:

```text
src/propstack/strategy_modules/
  entry/
    pdh_pdl_sweep_reclaim.py
  tp/
    fixed_r.py
  sl/
    sweep_extreme.py
```

To add a reusable module, create a new file in the correct folder and register it in that folder's `__init__.py`.

Current strategy logic:

```text
Long:
  price trades below previous RTH low
  price closes back above previous RTH low within reclaim_window_bars
  enter long on next bar open plus slippage

Short:
  price trades above previous RTH high
  price closes back below previous RTH high within reclaim_window_bars
  enter short on next bar open minus slippage
```

## 4. Configure Backtest Costs And Risk

```yaml
backtest:
  initial_balance: 50000
  tick_size: 0.25
  tick_value: 12.50
  commission_per_contract: 2.50
  slippage_ticks: 1
  contracts: 1
  daily_loss_limit: 1000
  daily_profit_stop: 1000
  flatten_time: "14:55:00"
```

Important simulator assumptions:

```text
signals confirm only after bar close
entry happens at next bar open
stop and target activate only after entry fills
if stop and target both hit in one bar, stop is assumed first
commission and slippage are included
```

## 5. Configure Benchmarks

Benchmarks live inside the campaign:

```yaml
benchmarks:
  min_trades_per_year: 100
  preferred_min_total_trades: 500
  min_profit_factor: 1.30
  min_total_net_profit: 0
  min_expectancy_r: 0.0
  min_win_rate: 0.50
  max_drawdown_pct: 0.03
  min_cagr: 0.06
  min_mar: 2.0
  max_daily_loss: 1000
  max_consecutive_losses: 8
  max_best_day_concentration: 0.40
  min_positive_month_rate: 0.50
  min_wfa_profitable_window_rate: 0.70
  min_monte_carlo_prop_pass_chance: 0.50
```

`max_drawdown_pct` is the worst percentage drawdown from the equity curve all-time high.

Example:

```text
peak equity: 110000
trough equity: 88000
max_drawdown_pct: 0.20
```

## 6. Run Data Validation And Baseline Backtest

```bash
CAMPAIGN_CONFIG=configs/campaigns/pdh_pdl_sweep/ES/es_5y_baseline.yaml
PYTHONPATH=src python3 -m propstack.run_backtest --config "$CAMPAIGN_CONFIG"
```

Outputs:

```text
data/reports/strategies/pdh_pdl_sweep/ES/es_5y_baseline/
  validation/
    cleaned_data.csv
    features_data.csv
    data_quality_report.csv
    missing_bars.csv
    tradingview_comparison.csv
  backtest/
    trade_log.csv
    daily_results.csv
    metrics.json
    sample_trades_for_tv_validation.csv
```

Before trusting results, manually compare these against TradingView or your charting platform:

```text
validation/tradingview_comparison.csv
backtest/sample_trades_for_tv_validation.csv
```

Check:

```text
RTH open/high/low/close
overnight high/low
previous RTH high/low
sample trade entry/stop/target/exit bars
timezone and session boundaries
```

## 7. Run Grid Search

Configure grid parameters:

```yaml
grid:
  objective: net_profit
  parameters:
    entry.params.reclaim_window_bars: [2, 3, 5]
    tp.params.target_r_multiple: [1.0, 1.5, 2.0]
    sl.params.stop_offset_ticks: [1, 2]
    entry.params.min_volume_ratio: [0.0, 1.0]
    entry.params.start_time: ["08:30:00", "09:00:00"]
    entry.params.end_time: ["11:00:00", "14:45:00"]
    entry.params.max_trades_per_day: [1, 3]
    entry.params.allow_long: [true]
    entry.params.allow_short: [true]
```

Run:

```bash
PYTHONPATH=src python3 -m propstack.run_grid --config "$CAMPAIGN_CONFIG"
```

Outputs:

```text
grid/grid_results.csv
grid/grid_summary.json
```

Review:

```text
percentage_passing_benchmark
top_10_combinations
stable_parameter_zones
failure_reason
```

Prefer stable parameter regions over the single best row.

## 8. Run Monkey / Random Robustness Testing

Configure random parameter and stress ranges:

```yaml
monkey:
  runs: 200
  seed: 7
  parameter_ranges:
    entry.params.reclaim_window_bars: [2, 8]
    tp.params.target_r_multiple: [1.0, 2.5]
    sl.params.stop_offset_ticks: [1, 4]
    entry.params.min_volume_ratio: [0.0, 1.5]
  stress:
    extra_slippage_ticks: [0, 2]
    commission_multiplier: [1.0, 1.5]
    skip_trade_probability: [0.0, 0.2]
    skip_winning_trade_probability: [0.0, 0.2]
```

Run:

```bash
PYTHONPATH=src python3 -m propstack.run_monkey --config "$CAMPAIGN_CONFIG"
```

Outputs:

```text
monkey/monkey_results.csv
monkey/monkey_summary.json
```

Review:

```text
percentage_profitable
percentage_passing_benchmark
median_net_profit
p5_net_profit
p95_max_drawdown
```

## 9. Run Walk-Forward Analysis

Configure train/test windows:

```yaml
wfa:
  train_months: 3
  test_months: 1
  step_months: 1
  objective: net_profit
```

Run:

```bash
PYTHONPATH=src python3 -m propstack.run_wfa --config "$CAMPAIGN_CONFIG"
```

Outputs:

```text
wfa/wfa_results.csv
wfa/wfa_summary.json
```

Review:

```text
selected_params
train_net_profit
test_net_profit
test_profit_factor
test_max_drawdown
profitable_window_rate
meets_profitable_window_benchmark
```

Target:

```text
profitable_window_rate >= 0.70
```

## 10. Configure Prop Rules

```yaml
prop_rules:
  starting_balance: 50000
  daily_loss_limit: 1000
  trailing_drawdown: 2500
  max_contracts: 5
  max_best_day_profit_percentage: 0.40
  min_trading_days: 2
  payout_threshold: 1000
  profit_target_pct: 0.06
  drawdown_limit_pct: 0.03
```

The Monte Carlo prop-pass benchmark uses:

```text
probability_profit_before_drawdown
```

This estimates how often shuffled/stressed paths reach `profit_target_pct` before hitting `drawdown_limit_pct`.

## 11. Run Monte Carlo

Configure Monte Carlo:

```yaml
monte_carlo:
  trade_log:
  runs: 1000
  seed: 11
  path_months: 1
  skip_trade_probability: 0.05
  skip_winning_trade_probability: 0.05
  adverse_slippage_per_trade: 0.0
  cluster_losses: true
```

If `trade_log` is blank, Monte Carlo first runs the campaign strategy and uses that trade log.

You can also point it at an existing trade log:

```yaml
monte_carlo:
  trade_log: data/reports/strategies/pdh_pdl_sweep/ES/es_5y_baseline/backtest/trade_log.csv
```

Run:

```bash
PYTHONPATH=src python3 -m propstack.run_monte_carlo --config "$CAMPAIGN_CONFIG"
```

Outputs:

```text
monte_carlo/monte_carlo_results.csv
monte_carlo/monte_carlo_summary.json
```

Review:

```text
probability_account_breach
probability_payout_eligible
probability_profit_before_drawdown
probability_net_profit_gt_0
p5_ending_balance
p95_drawdown
```

Target:

```text
probability_profit_before_drawdown >= 0.50
```

## 12. Track What Ran

Each runner updates:

```text
campaign_config.yaml
campaign_summary.json
config_hash.txt
input_data_hash.txt
run_manifest.json
```

Use these to answer:

```text
which config was used?
which raw CSV was used?
did the config change?
did the input data change?
which sections have been run?
```

The campaign summary accumulates results:

```json
{
  "campaign_id": "es_5y_baseline",
  "strategy_name": "pdh_pdl_sweep",
  "symbol": "ES",
  "raw_csv": "data/raw/ES/es_1m_20221201-20260529.csv",
  "config_hash": "...",
  "input_data_hash": "...",
  "sections": {
    "backtest": {},
    "grid": {},
    "monkey": {},
    "wfa": {},
    "monte_carlo": {}
  }
}
```

The symbol-level index lets you compare campaigns:

```text
data/reports/strategies/pdh_pdl_sweep/ES/runs_index.csv
```

## Recommended End-To-End Workflow

For a serious strategy test:

```bash
CAMPAIGN_CONFIG=configs/campaigns/pdh_pdl_sweep/ES/es_5y_baseline.yaml

PYTHONPATH=src python3 -m propstack.run_backtest --config "$CAMPAIGN_CONFIG"
PYTHONPATH=src python3 -m propstack.run_grid --config "$CAMPAIGN_CONFIG"
PYTHONPATH=src python3 -m propstack.run_monkey --config "$CAMPAIGN_CONFIG"
PYTHONPATH=src python3 -m propstack.run_wfa --config "$CAMPAIGN_CONFIG"
PYTHONPATH=src python3 -m propstack.run_monte_carlo --config "$CAMPAIGN_CONFIG"
```

Review in this order:

```text
1. validation/data_quality_report.csv
2. validation/tradingview_comparison.csv
3. backtest/metrics.json
4. backtest/trade_log.csv
5. grid/grid_summary.json
6. monkey/monkey_summary.json
7. wfa/wfa_summary.json
8. monte_carlo/monte_carlo_summary.json
9. campaign_summary.json
10. runs_index.csv
```

## Important Limitations

This is a research skeleton, not a production trading engine.

It does not implement:

```text
broker adapters
live order routing
database storage
tick data
order-book data
machine learning
broker reconciliation
```

The first trust checkpoint is always manual data and trade validation against your charting platform.

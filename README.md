# Prop Stack Automation

Research skeleton for futures prop-firm strategy testing. The project is organized around **campaigns** and **variants**:

```text
campaign -> strategy idea found online or designed for research
variant  -> one concrete test configuration for that idea
reports  -> generated evidence for one variant
```

The normal workflow is:

```text
download/export data
place raw data under data/raw/
create or update one campaign
create one variant YAML
run validation/core/core_grid/monkey/WFA/Monte Carlo
review variant_summary.json and runs_index.csv
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
      campaign.yaml
      variants/
        ES/
          1m_20221201_20260529/
            baseline.yaml

data/
  raw/
    ES/
    NQ/
  cleaned/
  reports/
    campaigns/
      pdh_pdl_sweep/
        ES/
          1m_20221201_20260529/
            baseline/
              variant_config.yaml
              variant_summary.json
              config_hash.txt
              input_data_hash.txt
              run_manifest.json
              validation/
              core/
              core_grid/
              monkey/
              wfa/
              monte_carlo/
            runs_index.csv

src/
  propstack/
    strategy/
      modular.py
    strategy_modules/

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

Databento monthly DBN downloads are also supported. Keep the downloaded
`.dbn.zst` files as the immutable raw archive and point the variant at the
folder:

```yaml
data:
  dataset_id: 1m_full_history
  source: databento_dbn
  raw_dir: data/raw/ES/GLBX-20260601-U6S3S4F4GM
  cache_dir: data/cache/databento/GLBX-20260601-U6S3S4F4GM
  symbol: ES
  timezone: America/New_York
  continuous_contract: explicit_roll_calendar
  roll_calendar: configs/data/ES/motivewave_rithmic_roll_calendar.csv
  price_adjustment: none
  roll_boundary_policy:
    reset_previous_day_levels: true
    skip_sessions_around_roll: 1
  include_spreads: false
  warmup_days: 7
```

The first run converts only the required monthly DBN files to Parquet under
`data/cache/`; later runs read those cached monthly files. For Databento parent
futures requests, `continuous_contract: explicit_roll_calendar` filters each bar
to the contract in the configured roll calendar while exposing the backtest
symbol as `ES`. Use `dominant_session_volume` only as a quick diagnostic rule;
it can roll early because it uses same-session volume.

The included ES calendar at
`configs/data/ES/motivewave_rithmic_roll_calendar.csv` covers 2010-2026. Rows
from 2022-2026 were inferred from the MotiveWave/Rithmic export; earlier rows
use the same observed Tuesday-of-expiration-week roll rule and should be
manually spot-checked if you use pre-2022 results for decisions.

## 2. Create A Campaign And Variant Config

A campaign is the strategy idea you are researching. It should stay the same while you test reasonable variations of that same idea: different parameters, slightly different entry/exit mechanics, symbols, timeframes, or datasets.

```text
configs/campaigns/{campaign_id}/campaign.yaml
```

Example:

```text
configs/campaigns/pdh_pdl_sweep/campaign.yaml
```

A variant is one concrete test configuration under that campaign:

```text
configs/campaigns/{campaign_id}/variants/{symbol}/{dataset_id}/{variant_id}.yaml
```

Example:

```text
configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/baseline.yaml
```

This makes the path readable without opening the YAML:

```text
pdh_pdl_sweep         campaign / strategy idea
ES                    instrument
1m_20221201_20260529  timeframe and dataset date range
baseline              exact variant being tested
```

Copy the baseline variant when you want a new version of the same strategy idea:

```bash
cp configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/baseline.yaml configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/tp_2r.yaml
```

Edit the new file:

```yaml
campaign_id: pdh_pdl_sweep
variant_id: tp_2r
strategy_name: pdh_pdl_sweep
symbol: ES
dataset_id: 1m_20221201_20260529

data:
  dataset_id: 1m_full_history
  source: databento_dbn
  raw_dir: data/raw/ES/GLBX-20260601-U6S3S4F4GM
  cache_dir: data/cache/databento/GLBX-20260601-U6S3S4F4GM
  symbol: ES
  timezone: America/New_York
  exchange_timezone: America/New_York
  continuous_contract: explicit_roll_calendar
  roll_calendar: configs/data/ES/motivewave_rithmic_roll_calendar.csv
  price_adjustment: none
  roll_boundary_policy:
    reset_previous_day_levels: true
    skip_sessions_around_roll: 1
  include_spreads: false
  warmup_days: 7
  rth_start: "09:30:00"
  rth_end: "16:00:00"
  eth_start: "16:00:00"
  eth_end: "09:29:00"
  rolling_volume_window: 3
```

Each run section can choose its own test window:

```yaml
core:
  data_subset:
    start_date: "2022-12-01"
    end_date: "2023-05-29"
```

`start_date` and `end_date` are session dates. The loader reads a configurable
warmup period before `start_date` so previous-session features remain available,
then filters the prepared data to the requested test window.

The `campaign_id`, `variant_id`, and `dataset_id` are mandatory. All runs using the same variant file write to:

```text
data/reports/campaigns/{campaign_id}/{symbol}/{dataset_id}/{variant_id}/
```

Use one variant YAML per concrete test configuration, not one YAML per report type. A single variant YAML can produce the core, core grid, monkey, WFA, and Monte Carlo reports for the same controlled setup.

Keep the same campaign when the core idea is still recognizable:

```text
reconfiguring default parameters
slight changes to entry or exit mechanics
testing ES versus NQ
testing 1-minute versus 5-minute data
changing costs, slippage, or prop rules
running robustness tests for the same online strategy idea
```

Create a new campaign only when the strategy idea itself changes:

```text
different source strategy
different market thesis
different setup concept
old idea is no longer recognizable
```

Create a new variant when you want to preserve and compare a meaningful version of the same campaign:

```text
different important parameter set
different entry, TP, or SL module
different dataset or date range
different symbol or timeframe
different cost or benchmark assumptions
```

Do not create a new variant for a temporary crash check or one-off debugging edit. Reuse `baseline` or create a clearly disposable `scratch.yaml` in the same dataset folder.

Use this naming rule:

```text
folder path = stable context
file name   = experiment variation
```

Examples:

```text
configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/baseline.yaml
configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/tp_2r.yaml
configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/long_only.yaml
configs/campaigns/pdh_pdl_sweep/variants/NQ/1m_20221201_20260529/baseline.yaml
```

## 3. Configure Strategy Rules

In the same campaign file:

```yaml
strategy:
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

The simulation engine uses a generic `ModularStrategy` composer. There is no separate PDH/PDL strategy wrapper; the variant YAML is the source of truth for which entry, TP, and SL modules are combined.

Each module implementation lives in its own file:

```text
src/propstack/strategy/
  modular.py

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

## Strategy Creation And Backtest Guide

Use this section when you want to create a strategy, choose one exact parameter set, run the core test, and understand the generated report.

The cleanest workflow is:

```text
1. Define the strategy idea
2. Build or reuse entry, TP, and SL modules
3. Wire those modules in one variant YAML
4. Set the exact data, costs, and risk assumptions
5. Run the core test
6. Validate data and sample trades
7. Interpret metrics, trades, daily results, and campaign metadata
```

### Step 1: Define The Strategy Idea

Write the strategy as three separate decisions:

```text
entry: when does the setup trigger?
sl:    where is the invalidation point?
tp:    where is the profit target?
```

For example, the current PDH/PDL sweep strategy is:

```text
entry: previous day high/low sweep, then reclaim
sl:    beyond the sweep candle extreme, offset by ticks
tp:    fixed R multiple from entry to stop
```

For normal one-entry, one-stop, one-target strategies, do not create a strategy file. Create or swap the relevant module and wire it in the variant YAML. A custom strategy orchestrator is only worth adding later if the engine needs behavior beyond this composition model, such as partial exits, trailing stops, pyramiding, or multiple simultaneous entry systems.

### Step 2: Create Or Reuse An Entry Module

Entry modules live here:

```text
src/propstack/strategy_modules/entry/
```

The current example is:

```text
src/propstack/strategy_modules/entry/pdh_pdl_sweep_reclaim.py
```

An entry module must expose:

```python
class MyEntry:
    name = "my_entry"

    def __init__(self, params: dict):
        self.params = params

    def on_bar_close(self, bar, trades_today: int = 0):
        ...
```

When the setup triggers, it returns a `Signal`:

```python
from propstack.strategy_modules.entry import Signal

return Signal(
    direction="long",
    level_type="pdl",
    swept_level=previous_low,
    sweep_timestamp=sweep_bar_timestamp,
    sweep_high=sweep_bar_high,
    sweep_low=sweep_bar_low,
    reclaim_timestamp=bar["timestamp"],
)
```

When there is no setup, return `None`.

Register the module in:

```text
src/propstack/strategy_modules/entry/__init__.py
```

Add it to `ENTRY_MODULES`:

```python
ENTRY_MODULES = {
    PdhPdlSweepReclaimEntry.name: PdhPdlSweepReclaimEntry,
    MyEntry.name: MyEntry,
}
```

### Step 3: Create Or Reuse A Stop Loss Module

Stop modules live here:

```text
src/propstack/strategy_modules/sl/
```

The current example is:

```text
src/propstack/strategy_modules/sl/sweep_extreme.py
```

A stop module must expose:

```python
class MyStop:
    name = "my_stop"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float) -> float:
        ...
```

For a long, the stop should normally be below entry. For a short, it should normally be above entry.

Register the module in:

```text
src/propstack/strategy_modules/sl/__init__.py
```

Add it to `SL_MODULES`:

```python
SL_MODULES = {
    SweepExtremeStop.name: SweepExtremeStop,
    MyStop.name: MyStop,
}
```

### Step 4: Create Or Reuse A Take Profit Module

Take profit modules live here:

```text
src/propstack/strategy_modules/tp/
```

The current example is:

```text
src/propstack/strategy_modules/tp/fixed_r.py
```

A TP module must expose:

```python
class MyTarget:
    name = "my_target"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str) -> float:
        ...
```

Register the module in:

```text
src/propstack/strategy_modules/tp/__init__.py
```

Add it to `TP_MODULES`:

```python
TP_MODULES = {
    FixedRTarget.name: FixedRTarget,
    MyTarget.name: MyTarget,
}
```

### Step 5: Wire The Modules In A Variant Config

Campaign configs live under:

```text
configs/campaigns/
```

For a new single parameter run, copy an existing variant and give it a unique `variant_id`:

```bash
cp configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/baseline.yaml configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/tp_2r.yaml
```

Set the campaign and variant identity:

```yaml
campaign_id: pdh_pdl_sweep
variant_id: tp_2r
strategy_name: pdh_pdl_sweep
symbol: ES
dataset_id: 1m_20221201_20260529
```

Use a new `variant_id` for every result set you want to preserve. If you reuse the same variant id, the latest run writes to the same report folder.

Do not split one experiment into separate YAML files for core, core grid, monkey, WFA, and Monte Carlo. Keep those report sections together inside the same variant YAML so every report points back to the same data, modules, parameters, costs, and benchmarks.

Then wire the modules and parameters:

```yaml
strategy:
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

The important pattern is:

```text
strategy.{entry|tp|sl}.module = module name registered in __init__.py
strategy.{entry|tp|sl}.params = parameters passed into that module
```

Core grid, monkey, and WFA use dotted paths to override the same values:

```yaml
core_grid:
  data_subset:
    start_date: "2022-12-01"
    end_date: "2026-05-29"
  parameters:
    entry.params.reclaim_window_bars: [2, 3, 5]
    tp.params.target_r_multiple: [1.0, 1.5, 2.0]
    sl.params.stop_offset_ticks: [1, 2]
```

### Step 6: Set The Exact Data And Core Assumptions

The `data` section records exactly which raw dataset is used:

```yaml
data:
  dataset_id: 1m_full_history
  source: databento_dbn
  raw_dir: data/raw/ES/GLBX-20260601-U6S3S4F4GM
  cache_dir: data/cache/databento/GLBX-20260601-U6S3S4F4GM
  symbol: ES
  timezone: America/New_York
  exchange_timezone: America/New_York
  continuous_contract: explicit_roll_calendar
  roll_calendar: configs/data/ES/motivewave_rithmic_roll_calendar.csv
  price_adjustment: none
  roll_boundary_policy:
    reset_previous_day_levels: true
    skip_sessions_around_roll: 1
  include_spreads: false
  warmup_days: 7
  rth_start: "09:30:00"
  rth_end: "16:00:00"
  eth_start: "16:00:00"
  eth_end: "09:29:00"
  rolling_volume_window: 3
```

The `core` section records execution costs, account assumptions, and the data subset used by the core test:

```yaml
core:
  data_subset:
    start_date: "2022-12-01"
    end_date: "2026-05-29"
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

Do not compare variants unless these assumptions are intentionally identical or intentionally part of the test.

### Step 7: Run Core

Run one exact variant config through the core test:

```bash
VARIANT_CONFIG=configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/tp_2r.yaml
PYTHONPATH=src python3 -m propstack.run_core --config "$VARIANT_CONFIG"
```

The command prints the output folder. It will follow this layout:

```text
data/reports/campaigns/{campaign_id}/{symbol}/{dataset_id}/{variant_id}/
```

For the example above:

```text
data/reports/campaigns/pdh_pdl_sweep/ES/1m_20221201_20260529/tp_2r/
```

### Step 8: Validate Before Interpreting Performance

The core run also writes validation files:

```text
validation/
  cleaned_data.csv
  features_data.csv
  data_quality_report.csv
  missing_bars.csv
  tradingview_comparison.csv
```

Check these first:

```text
data_quality_report.csv
  Confirms row counts, date range, duplicate timestamps, missing values, and basic OHLCV checks.

missing_bars.csv
  Shows expected minute bars that are missing from the cleaned data.

tradingview_comparison.csv
  Gives sample session values to compare against TradingView or your charting platform.
```

Do not trust the test if previous day high/low, RTH boundaries, or timestamps are wrong.

### Step 9: Read The Core Report Files

Core outputs live here:

```text
core/
  trade_log.csv
  daily_results.csv
  metrics.json
  sample_trades_for_tv_validation.csv
```

Use them in this order:

```text
1. sample_trades_for_tv_validation.csv
2. trade_log.csv
3. daily_results.csv
4. metrics.json
```

`sample_trades_for_tv_validation.csv` is for manual chart validation. Confirm:

```text
signal bar
next-bar entry
entry price after slippage
stop price
target price
exit bar
exit reason
```

`trade_log.csv` is one row per trade. Important columns:

```text
entry_timestamp / exit_timestamp
  When the trade opened and closed.

direction
  long or short.

level_type / swept_level
  Which reference level triggered the setup.

entry_price / stop_price / target_price / exit_price
  The simulated prices after configured slippage rules.

exit_reason
  Usually stop, target, or eod_flatten.

gross_pnl
  PnL after slippage-adjusted entry/exit prices, before commission.

net_pnl
  PnL after commission.

slippage_cost
  Estimated cost of the configured entry and exit slippage.

r_multiple
  Trade result divided by initial risk.

max_favorable_excursion / max_adverse_excursion
  How far the trade moved in favor or against before exit.
```

`daily_results.csv` groups trades by session:

```text
session_date
net_pnl
gross_pnl
trades
wins
losses
```

Use it to check prop-firm style behavior:

```text
large losing days
days with too many trades
profit concentration in one or two sessions
whether daily loss limits are realistic
```

`metrics.json` is the main performance summary:

```text
total_trades
  Number of closed trades. Low trade count means weak statistical confidence.

trades_per_year
  Annualized trade frequency across the tested date range.

net_profit
  Sum of all net trade PnL after commission.

profit_factor
  Sum of positive net_pnl divided by absolute sum of negative net_pnl. Above 1.30 is your current minimum target.

expectancy_r
  Average trade result in R. Positive means the average trade makes more than it risks.

win_rate
  Percentage of trades with net_pnl > 0.

max_drawdown
  Worst peak-to-trough equity drawdown in account currency.

max_drawdown_pct
  Worst percentage drawdown from the equity curve all-time high. 0.20 means 20%.

cagr
  Annualized account growth based on initial_balance and ending balance.

mar
  cagr divided by max_drawdown_pct. Higher means better return per drawdown.

worst_day / best_day
  Worst and best session PnL.

best_day_concentration
  best_day divided by total net_profit. High values mean one day dominates results.

max_consecutive_losses
  Longest losing streak.

positive_month_rate
  Fraction of profitable months.

average_trade
  Mean net PnL per trade.
```

### Step 10: Interpret The Result Against Your Benchmarks

Start with the benchmark fields in the variant config:

```yaml
benchmarks:
  min_trades_per_year: 100
  preferred_min_total_trades: 500
  min_profit_factor: 1.30
  max_drawdown_pct: 0.03
  min_cagr: 0.06
  min_mar: 2.0
  min_win_rate: 0.50
```

A baseline core test is more interesting when it passes these checks together:

```text
enough trades
profit factor remains above threshold after slippage and commission
drawdown is within challenge constraints
returns are not dominated by one day
monthly and daily behavior are not fragile
trade examples match the chart
```

Red flags:

```text
very high profit factor with very few trades
large net profit but poor trades_per_year
max_drawdown_pct above your account limit
best_day_concentration above benchmark
many eod_flatten exits when the strategy is supposed to hit stop or target
sample trades do not match TradingView
```

### Step 11: Track Which Config Produced The Report

The variant report folder records the config and input hashes:

```text
variant_config.yaml
variant_summary.json
config_hash.txt
input_data_hash.txt
run_manifest.json
```

Use them like this:

```text
variant_config.yaml
  Snapshot of the exact YAML used for the run.

config_hash.txt
  Changes when the variant config changes.

input_data_hash.txt
  Changes when the selected raw input files or data window changes.

run_manifest.json
  Records which test sections have been run for this variant.

variant_summary.json
  Collects latest summary metrics for core, core grid, monkey, WFA, and Monte Carlo.
```

The dataset-level index compares variants under the same campaign, symbol, and dataset:

```text
data/reports/campaigns/{campaign_id}/{symbol}/{dataset_id}/runs_index.csv
```

Use a new `variant_id` whenever you want to compare a different version side by side. Use a new `dataset_id` whenever the raw data file or date range changes.

## 4. Configure Core Costs And Risk

```yaml
core:
  data_subset:
    start_date: "2022-12-01"
    end_date: "2026-05-29"
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

## 6. Run Data Validation And Core

```bash
VARIANT_CONFIG=configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/baseline.yaml
PYTHONPATH=src python3 -m propstack.run_core --config "$VARIANT_CONFIG"
```

Outputs:

```text
data/reports/campaigns/pdh_pdl_sweep/ES/1m_20221201_20260529/baseline/
  validation/
    cleaned_data.csv
    features_data.csv
    data_quality_report.csv
    missing_bars.csv
    tradingview_comparison.csv
  core/
    trade_log.csv
    daily_results.csv
    metrics.json
    sample_trades_for_tv_validation.csv
```

Before trusting results, manually compare these against TradingView or your charting platform:

```text
validation/tradingview_comparison.csv
core/sample_trades_for_tv_validation.csv
```

Check:

```text
RTH open/high/low/close
overnight high/low
previous RTH high/low
sample trade entry/stop/target/exit bars
timezone and session boundaries
```

To compare a MotiveWave/Rithmic CSV export against the Databento DBN archive:

```bash
PYTHONPATH=src python3 -m propstack.compare_data_sources \
  --csv data/raw/ES/es_1m_20221201-20260529.csv \
  --dbn-dir data/raw/ES/GLBX-20260601-U6S3S4F4GM \
  --continuous-contract explicit_roll_calendar \
  --roll-calendar configs/data/ES/motivewave_rithmic_roll_calendar.csv \
  --out data/reports/data_compare/ES/rithmic_vs_databento_1m_20221201_20260529
```

This writes timestamp coverage, OHLCV mismatch summaries, session-level
differences, missing timestamp segments, selected Databento contracts, and an
alternate-contract diagnostic that flags when the CSV matches a different
Databento contract than the configured continuous-contract rule selected.

## 7. Run Core Grid Search

Configure core grid parameters:

```yaml
core_grid:
  data_subset:
    start_date: "2022-12-01"
    end_date: "2026-05-29"
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
PYTHONPATH=src python3 -m propstack.run_core_grid --config "$VARIANT_CONFIG"
```

Outputs:

```text
core_grid/core_grid_results.csv
core_grid/core_grid_summary.json
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
PYTHONPATH=src python3 -m propstack.run_monkey --config "$VARIANT_CONFIG"
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
PYTHONPATH=src python3 -m propstack.run_wfa --config "$VARIANT_CONFIG"
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

If `trade_log` is blank, Monte Carlo first runs the variant strategy and uses that trade log.

You can also point it at an existing trade log:

```yaml
monte_carlo:
  trade_log: data/reports/campaigns/pdh_pdl_sweep/ES/1m_20221201_20260529/baseline/core/trade_log.csv
```

Run:

```bash
PYTHONPATH=src python3 -m propstack.run_monte_carlo --config "$VARIANT_CONFIG"
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
variant_config.yaml
variant_summary.json
config_hash.txt
input_data_hash.txt
run_manifest.json
```

Use these to answer:

```text
which config was used?
which raw data source was used?
did the config change?
did the input data change?
which sections have been run?
```

The variant summary accumulates results:

```json
{
  "campaign_id": "pdh_pdl_sweep",
  "variant_id": "baseline",
  "strategy_name": "pdh_pdl_sweep",
  "symbol": "ES",
  "dataset_id": "1m_full_history",
  "data_source": "databento_dbn",
  "raw_dir": "data/raw/ES/GLBX-20260601-U6S3S4F4GM",
  "config_hash": "...",
  "input_data_hash": "...",
  "sections": {
    "core": {},
    "core_grid": {},
    "monkey": {},
    "wfa": {},
    "monte_carlo": {}
  }
}
```

The dataset-level index lets you compare variants under the same campaign, symbol, and dataset:

```text
data/reports/campaigns/pdh_pdl_sweep/ES/1m_20221201_20260529/runs_index.csv
```

## Recommended End-To-End Workflow

For a serious strategy test:

```bash
VARIANT_CONFIG=configs/campaigns/pdh_pdl_sweep/variants/ES/1m_20221201_20260529/baseline.yaml

PYTHONPATH=src python3 -m propstack.run_core --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_core_grid --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_monkey --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_wfa --config "$VARIANT_CONFIG"
PYTHONPATH=src python3 -m propstack.run_monte_carlo --config "$VARIANT_CONFIG"
```

Review in this order:

```text
1. validation/data_quality_report.csv
2. validation/tradingview_comparison.csv
3. core/metrics.json
4. core/trade_log.csv
5. core_grid/core_grid_summary.json
6. monkey/monkey_summary.json
7. wfa/wfa_summary.json
8. monte_carlo/monte_carlo_summary.json
9. variant_summary.json
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

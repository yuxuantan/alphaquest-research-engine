# ES/MES Micro-Flow Divergence Data Refresh Retry - 2026-06-17

Decision: FAIL.

## Data Built Locally

- No paid data was downloaded.
- Built MES Sierra active-contract RTH orderflow cache: `data/cache/orderflow/mes_sierra_trade_orderflow_1m_20190506_20260616_full_rth_ny.parquet`.
- MES cache validation: 687,180 full-session RTH minute bars, 1,762 sessions, zero duplicate timestamps, zero invalid OHLC rows, zero missing session segments, minimum side-volume coverage 1.0; 74 sessions dropped by regular/full-session policy.
- Built merged ES/MES feature cache: `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`.
- Merged cache validation: 685,230 aligned ES/MES minute bars, 1,757 sessions, first `2019-05-06 09:30:00`, last `2026-06-09 15:59:00`, zero duplicate timestamps, zero invalid OHLC rows, zero zero-volume ES/MES rows.

## Methodology

- Retried the same five campaign variants using generated refresh configs under `campaigns/es_mes_micro_flow_divergence_reversion/data_refresh_20260617/`.
- Entry mechanics, stop modules, target modules, parameter grids, costs, slippage, tick size, point value, sessions, and flatten rules were unchanged versus the original and existing rescue configs.
- Explicitly used corrected benchmark windows in refresh configs: WFA 48-month IS / 12-month OOS / 12-month step, simulated incubation 48/12, acceptance 24/6.
- Limited core used the benchmark random 10% contiguous window, excluding latest 10% and Covid range; resolved window for all refresh runs was `2021-07-13` through `2022-03-28`.

## Results

- `afternoon_mes_large20_buy_pressure_short` `mes_data_refresh1`: FAIL at `limited_core_grid_test`; profitable_combo_rate=0.2222222222222222; top_net=2395.0; top_pf=1.212511091393079; top_trades=46.
- `afternoon_mes_large20_buy_pressure_short` `mes_data_refresh_rescue1`: FAIL at `limited_core_grid_test`; profitable_combo_rate=0.1111111111111111; top_net=2395.0; top_pf=1.212511091393079; top_trades=46.
- `afternoon_mes_large20_sell_pressure_long` `mes_data_refresh1`: FAIL at `limited_monkey_test`; profitable_combo_rate=0.9722222222222222; top_net=6310.0; top_pf=1.831357048748353; top_trades=38; monkey_net_beat=0.85; monkey_dd_beat=0.9733333333333334.
- `afternoon_mes_large20_sell_pressure_long` `mes_data_refresh_rescue1`: FAIL at `limited_monkey_test`; profitable_combo_rate=0.9444444444444444; top_net=6310.0; top_pf=1.831357048748353; top_trades=38; monkey_net_beat=0.85; monkey_dd_beat=0.9633333333333334.
- `midday_mes_price_richness_fade` `mes_data_refresh1`: FAIL at `limited_monkey_test`; profitable_combo_rate=0.9444444444444444; top_net=16955.0; top_pf=1.7067528136723635; top_trades=89; monkey_net_beat=0.86; monkey_dd_beat=0.9933333333333333.
- `midday_mes_price_richness_fade` `mes_data_refresh_rescue1`: FAIL at `limited_monkey_test`; profitable_combo_rate=1.0; top_net=16955.0; top_pf=1.7067528136723635; top_trades=89; monkey_net_beat=0.83; monkey_dd_beat=0.9.
- `morning_mes_buy_pressure_reversion_short` `mes_data_refresh1`: FAIL at `limited_monkey_test`; profitable_combo_rate=0.8611111111111112; top_net=5977.5; top_pf=1.3837265286470872; top_trades=57; monkey_net_beat=0.8366666666666667; monkey_dd_beat=0.8766666666666667.
- `morning_mes_buy_pressure_reversion_short` `mes_data_refresh_rescue1`: FAIL at `limited_monkey_test`; profitable_combo_rate=0.7777777777777778; top_net=5977.5; top_pf=1.3837265286470872; top_trades=57; monkey_net_beat=0.85; monkey_dd_beat=0.98.
- `morning_mes_sell_pressure_reversion_long` `mes_data_refresh1`: FAIL at `limited_core_grid_test`; profitable_combo_rate=0.0; top_net=-742.5; top_pf=0.8316326530612245; top_trades=11.
- `morning_mes_sell_pressure_reversion_long` `mes_data_refresh_rescue1`: FAIL at `limited_core_grid_test`; profitable_combo_rate=0.0; top_net=-1385.0; top_pf=0.9040526498094908; top_trades=42.

No refreshed original or rescue run reached WFA. The campaign remains rejected under the current methodology.

## Artifacts

- Aggregate summary: `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_test_summary.json`
- Refresh summary copy: `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_test_summary_mes_data_refresh_20260617.json`
- Results CSV: `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_results.csv`
- Refresh results CSV: `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_results_mes_data_refresh_20260617.csv`
- WFA table placeholder: `backtest-campaigns/es_mes_micro_flow_divergence_reversion/wfa_table.csv`
- Monte Carlo placeholder: `backtest-campaigns/es_mes_micro_flow_divergence_reversion/monte_carlo_summary.json`

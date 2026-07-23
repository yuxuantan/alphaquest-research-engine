# Methodology Audit - NQ Nikkei 225 Close Spillover

Verdict: FAIL

## Scope

- Campaign: `nq_nikkei225_close_spillover`
- Symbol: `NQ`
- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Feature file: `data/external/nq_nikkei225_spillover_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_nikkei225_spillover_density_audit_20260701.md`
- Aggregate summary: `backtest-campaigns/nq_nikkei225_close_spillover/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_nikkei225_close_spillover/campaign_results.csv`

## Leakage Controls

- Each NQ session maps to the latest Nikkei 225 close on or before the NQ session date.
- Tokyo cash close is complete before all configured NQ RTH decision times.
- Rolling ranks are computed from completed Nikkei observations before the NQ session join.
- Signals use completed NQ bars and enter no earlier than the next bar open.
- No final U.S. session range, final VWAP, final volume profile, future NQ bar, or post-entry Nikkei state is used.

## Test Discipline

- Five variants and parameter grids were fixed before staged PnL testing.
- Each variant uses a 27-combination grid: one entry rank threshold, one stop, and one target.
- No rescue attempt is authorized.
- Full staged promotion requires core, monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation core/monkey, and acceptance OOS.

## Pre-PnL Density

The density audit passed 45/45 rows. Minimum signal density across all windows and thresholds was 65.00 signals/year.

## Result

Run2 is the valid staged evidence. Run1 is preserved as an infrastructure-error retry because the first authored configs used an unsupported `data.feature_set` CSV path; the valid source configs kept the same entry module, feature CSV, mechanics, and parameter grids with `feature_set: none`.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass Combos | Top Net | Top PF | Monkey Net Beat | Monkey DD Beat |
|---|---:|---:|---:|---:|---:|---:|---:|
| nikkei_1d_strength_long_1000 | limited_core_grid_test | 0.000000 | 0/27 | -195.00 | 0.987004 | skipped | skipped |
| nikkei_1d_weakness_short_1000 | limited_core_grid_test | 0.481481 | 3/27 | 2732.50 | 1.129779 | skipped | skipped |
| nikkei_5d_strength_long_1030 | limited_monkey_test | 0.888889 | 15/27 | 2945.00 | 1.200136 | 0.81975 | 0.87175 |
| nikkei_5d_weakness_short_1030 | limited_monkey_test | 0.777778 | 16/27 | 4105.00 | 1.266299 | 0.946125 | 0.88675 |
| nikkei_1d_volatility_short_1130 | limited_core_grid_test | 0.222222 | 2/27 | 2355.00 | 1.139061 | skipped | skipped |

## Decision

FAIL. Three variants failed limited core. The two five-day variants passed limited core but failed the monkey/randomized-schedule robustness gate, so no branch reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

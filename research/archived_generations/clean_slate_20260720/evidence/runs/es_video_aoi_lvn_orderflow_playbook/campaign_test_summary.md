# ES Video AOI LVN Orderflow Playbook

Decision: FAIL

Latest update: Run7 added true raw Sierra 09:30:00-09:30:30 ET ORB high/low to the exact-video proxy cache. All five run7 variants failed `limited_core_grid_test`: 0/405 profitable combinations, 0 benchmark-pass combinations, 0 Apex rule violating iterations. No run7 variant reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Run7 cache: `data/cache/orderflow/es_video_aoi_exact_developing_vap_large200_orb30_3m_20120103_20260529_rth_ny.parquet`

| Variant | Profitable | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| video_model1_range_midpoint_two_sided_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -7417.5 | 0.490031 | -0.651146 | 143.29 | min_total_net_profit;max_consecutive_losses |
| video_model1_range_opposite_edge_two_sided_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -6887.5 | 0.495144 | -0.665485 | 142.59 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_buyer_trap_short_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -5.0 | 0.999127 | -0.001453 | 65.03 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_seller_trap_long_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -3792.5 | 0.565578 | -0.600371 | 81.63 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_structural_two_sided_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -3707.5 | 0.738862 | -0.528386 | 136.52 | min_total_net_profit;max_consecutive_losses |

Prior run6 quality-filter rescue also remains FAIL: only the short-side branch passed limited core and it then failed the monkey drawdown robustness gate.

<!-- RUN8-RUN10-RESULT-INFORMED-SEARCH-START -->
## Result-Informed Profit Search Runs 8-10

User explicitly requested continued variations until a profitable expression was found. These runs are therefore result-informed searches, not fresh independent tests. They use the exact raw Sierra 30-second ORB cache and remain within the deterministic video AOI/LVN orderflow family unless noted.

### Run8 Profit Search

Short-heavy result-informed variants after run7 exact-ORB failure. Kept video AOI/orderflow family and exact raw Sierra 30-second ORB cache.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Top best-day conc. | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| video_model1_range_vah_buyer_trap_short_quality_orb30_3m_1500 | 0/24 | 0 | 0 | -305.0 | 0.7142857142857143 | -0.4740709180679328 | 12.618453192264612 | 0.0 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
| video_model2_trend_lvn_short_confirmed_orb30_3m_1500 | 16/36 | 0 | 0 | 897.5 | 1.1665893271461716 | 0.3256197273693955 | 48.70318321458919 | 1.2618384401114209 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_quality_orb30_minrr_3m_1500 | 33/54 | 0 | 0 | 897.5 | 1.1665893271461716 | 0.3256197273693955 | 48.70318321458919 | 1.2618384401114209 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_stronger_trend_orb30_3m_1500 | 14/24 | 0 | 0 | 2570.0 | 2.439775910364146 | 4.26268587177114 | 20.162777119198857 | 0.4406614785992218 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_tight_aoi_orb30_3m_1500 | 18/36 | 0 | 0 | 522.5 | 1.1089676746611052 | 0.1703997969714649 | 42.45922585494175 | 2.167464114832536 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |

Run verdict: FAIL. Aggregate result: 81/174 profitable core rows, 0 benchmark-pass rows, 0 Apex-violating rows; no variant completed the staged flow.
Best profitable row by net profit: video_model2_trend_lvn_short_stronger_trend_orb30_3m_1500 run_id 17, net 2570.0, PF 2.439775910364146, MAR 4.26268587177114, trades/year 20.162777119198857. This is not a candidate strategy because it failed the staged gate and did not reach monkey/WFA/Monte Carlo.

### Run9 Multi-Signal Search

Allowed up to two qualified completed AOI signals/trades per session because the video does not impose a one-trade-per-day rule.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Top best-day conc. | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| video_model2_trend_lvn_short_multisignal_confirmed_orb30_3m_1500 | 13/36 | 0 | 0 | 1662.5 | 1.308584686774942 | 0.8757554748598769 | 50.13562977972417 | 0.681203007518797 | max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_multisignal_extended_window_orb30_3m_1500 | 15/24 | 0 | 0 | 1027.5 | 1.169344870210136 | 0.4379650833075086 | 55.14919275769658 | 1.102189781021898 | max_consecutive_losses;max_best_day_concentration |
| video_model2_trend_lvn_short_multisignal_quality_orb30_3m_1500 | 30/54 | 0 | 0 | 1662.5 | 1.308584686774942 | 0.8757554748598769 | 50.13562977972417 | 0.681203007518797 | max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_multisignal_stronger_trend_orb30_3m_1500 | 13/24 | 0 | 0 | 2490.0 | 2.3351206434316354 | 3.5716402083397627 | 20.938268546860343 | 0.4548192771084337 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_multisignal_tight_aoi_orb30_3m_1500 | 17/36 | 0 | 0 | 1007.5 | 1.2066666666666668 | 0.4184211860731126 | 44.6553927095077 | 1.1240694789081886 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |

Run verdict: FAIL. Aggregate result: 88/174 profitable core rows, 0 benchmark-pass rows, 0 Apex-violating rows; no variant completed the staged flow.
Best profitable row by net profit: video_model2_trend_lvn_short_multisignal_stronger_trend_orb30_3m_1500 run_id 17, net 2490.0, PF 2.3351206434316354, MAR 3.5716402083397627, trades/year 20.938268546860343. This is not a candidate strategy because it failed the staged gate and did not reach monkey/WFA/Monte Carlo.

### Run10 First-Target Search

Used a one-contract proxy for target-highs/lows plus runner: structural target usable at 1R or better, otherwise 1.5R-3R fixed-R fallback.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Top best-day conc. | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| video_model2_trend_lvn_short_first_target_confirmed_orb30_3m_1500 | 12/54 | 0 | 0 | 1422.5 | 1.2754114230396902 | 0.7453620079960153 | 52.284299627426634 | 0.6520210896309314 | max_consecutive_losses;max_best_day_concentration |
| video_model2_trend_lvn_short_first_target_quality_orb30_3m_1500 | 26/54 | 0 | 0 | 1422.5 | 1.2754114230396902 | 0.7453620079960153 | 52.284299627426634 | 0.6520210896309314 | max_consecutive_losses;max_best_day_concentration |
| video_model2_trend_lvn_short_first_target_single_signal_quality_orb30_3m_1500 | 14/54 | 0 | 0 | 860.0 | 1.172258387581372 | 0.4049179198880157 | 48.70318321458919 | 0.9825581395348836 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |
| video_model2_trend_lvn_short_first_target_stronger_trend_orb30_3m_1500 | 18/36 | 0 | 0 | 2435.0 | 2.28665785997358 | 3.134355109584278 | 21.715296823852075 | 0.3963039014373716 | min_trades_per_year;preferred_min_total_trades |
| video_model2_trend_lvn_short_first_target_tight_aoi_orb30_3m_1500 | 18/54 | 0 | 0 | 1047.5 | 1.2233475479744136 | 0.5012164186022585 | 46.11950394588501 | 0.8854415274463007 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |

Run verdict: FAIL. Aggregate result: 88/252 profitable core rows, 0 benchmark-pass rows, 0 Apex-violating rows; no variant completed the staged flow.
Best profitable row by net profit: video_model2_trend_lvn_short_first_target_stronger_trend_orb30_3m_1500 run_id 30, net 2435.0, PF 2.28665785997358, MAR 3.134355109584278, trades/year 21.715296823852075. This is not a candidate strategy because it failed the staged gate and did not reach monkey/WFA/Monte Carlo.

Overall run8-run10 verdict: FAIL. The search found profitable core-screen rows, especially short-only Model 2 LVN pullbacks, but every run had 0 benchmark-passing rows and no variant completed the staged flow. No candidate_strategy_report.md was created.
<!-- RUN8-RUN10-RESULT-INFORMED-SEARCH-END -->

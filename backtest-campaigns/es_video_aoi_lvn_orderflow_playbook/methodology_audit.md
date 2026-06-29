# Methodology Audit - ES Video AOI LVN Orderflow Playbook

Final decision: FAIL

## Source Translation

The supplied video notes describe a discretionary orderflow playbook with two models: range re-entry at value-area edges after failed aggressive flow, and trend continuation after pullback into LVN/imbalance areas where countertrend traders become trapped. The original campaign converted those ideas into deterministic ES 1-minute completed-bar rules. User-requested run5 supersedes the earlier video translation for mechanics fidelity by adding the transcript's explicit two-of-four AOI gate, current-session developing VAP, overnight levels, ES large-200 aggregate activity, and delta activity on native 3-minute bars.

## Data Gates

- True ES prints above 200 lots were not available as a validated full-history local field and were not approximated with Sierra large10/large20 proxies.
- The tested footprint file is RTH-only, so overnight high/low variants were not included.
- Prior profile levels are approximate OHLCV-derived levels, not true volume-at-price.
- Corrected user-requested run4 uses Sierra SCID-derived price-level bid/ask volume to build current-session developing VAP fields on native 3-minute bars. This improves LVN measurement over OHLCV-distributed profiles, but remains non-MBO and does not reconstruct queue position or full DOM sequencing.
- Exact-video run5 joins current-session Sierra developing VAP with overnight high/low and ES large-200 aggregate fields. It still does not contain exact 30-second ORB columns, live tape speed, DOM queue behavior, MBO bubble sequencing, partial exits, discretionary add-ons, or dynamic trailing remainder.

## Leakage Controls

- Prior VAH, VAL, POC, and LVNs were computed only from the completed prior RTH session.
- Opening range state was unavailable until the first 30 completed RTH one-minute bars.
- Footprint absorption and trap checks used only the completed signal bar; the engine could enter no earlier than the next one-minute open.
- Corrected run4 developing VAP fields are generated per native 3-minute bar from current RTH price-level volume through that completed bar. The first nine 3-minute bars of each session are blank; the 10th completed bar is the first eligible developing VAP row.
- No final current-session VWAP, final profile, final range, future high/low, or future orderflow was used.

## Stage Result

All five variants failed `limited_core_grid_test`; none reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| range_value_edge_aoi_reentry_1500 | 4/81 | 0 | 0 | 272.5 | 1.029451 | 0.136823 | 73.98 | max_consecutive_losses;max_best_day_concentration |
| trend_lvn_buyer_trap_short_1500 | 0/81 | 0 | 0 | -3210.0 | 0.406928 | -0.634611 | 47.05 | min_total_net_profit;min_trades_per_year;max_consecutive_losses;preferred_min_total_trades |
| trend_lvn_seller_trap_long_1500 | 0/81 | 0 | 0 | -2962.5 | 0.672199 | -0.476692 | 68.61 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_base_1500 | 0/81 | 0 | 0 | -4080.0 | 0.527641 | -0.639681 | 85.60 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_strong_1500 | 0/81 | 0 | 0 | -3300.0 | 0.626274 | -0.595925 | 91.16 | min_total_net_profit;max_consecutive_losses |

## Verdict

FAIL. The video-derived strategy did not produce a candidate strategy under the staged ES methodology. No candidate strategy report was created.

## User-Requested 3-Minute Trend Run2

On 2026-06-24 the supplied video URL was used to run the trend-following model on ES 3-minute bars. A native 3-minute Sierra footprint cache was rebuilt from raw local Sierra price-level bid/ask volume:

- `data/cache/orderflow/es_sierra_footprint_imbalance_3m_20101214_20260610_full_rth_ny.parquet`
- Validation: 496,470 rows, 0 duplicate timestamps, 63,899 long-absorption bars, 59,813 short-absorption bars.

The 3-minute branch tested only deterministic trend-LVN expressions of the same video playbook. Opening range state used 30 elapsed minutes, entry used the next 3-minute open after the completed signal bar, and all variants kept the same `sweep_extreme` stop and `cost_adjusted_fixed_r` target family.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| trend_lvn_buyer_trap_short_3m_1500 | 0/81 | 0 | 0 | -322.5 | 0.936888 | -0.132077 | 44.26 | min_total_net_profit;min_trades_per_year;max_consecutive_losses;preferred_min_total_trades |
| trend_lvn_seller_trap_long_3m_1500 | 0/81 | 0 | 0 | -780.0 | 0.871340 | -0.350637 | 56.20 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_base_3m_1500 | 0/81 | 0 | 0 | -835.0 | 0.903830 | -0.223923 | 82.99 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_delta_shift_3m_1500 | 18/81 | 0 | 0 | 1405.0 | 1.154949 | 0.419992 | 74.48 | max_consecutive_losses;max_best_day_concentration |
| trend_lvn_two_sided_strong_3m_1500 | 3/81 | 0 | 0 | 72.5 | 1.009663 | 0.020968 | 73.84 | max_consecutive_losses;max_best_day_concentration |

Run2 verdict: SUPERSEDED_FAIL. The branch had 21/405 profitable combinations and 0 benchmark-passing combinations, but it used the prior/frozen profile interpretation. The user clarified that the LVN should come from the same-day developing profile, so run2 is not the final interpretation of the requested mechanics.

## Superseded Developing OHLCV Run3

Run3 corrected the profile timing to current-session developing profile but still used the entry module's OHLCV-distributed profile approximation. It was interrupted after four completed variants when the user correctly challenged the approximation and requested the more accurate Sierra tick/price-level data path. Run3 is retained as generated evidence but is superseded by run4 and is not used for the final verdict.

## Corrected Sierra Developing VAP Run4

Run4 uses the generated Sierra developing VAP cache:

- `data/cache/orderflow/es_sierra_footprint_developing_vap_3m_20101214_20260610_full_rth_ny.parquet`
- Validation: 496,470 rows, 0 duplicate timestamps, 462,099 rows with developing VAP populated.
- June 24 spot check: the first nine 3-minute RTH bars are blank; 09:57 has `developing_vap_bars=10`; 10:00 has `developing_vap_bars=11` and `developing_vap_session_yyyymmdd=20240624`.

LVN mechanics in run4:

- The developing profile aggregates raw Sierra price-level `bid_volume + ask_volume` by ES tick from the current RTH session start through the completed signal bar.
- LVN candidates are ticks whose cumulative price-level volume is at or below the configured 20% lower-volume quantile.
- The trend entry uses the cached `developing_vap_lvn_near_close`, the LVN nearest the completed signal bar close.
- Trend state requires price beyond the 30 elapsed-minute opening range and beyond developing VAH/VAL in the trade direction.
- Price reaches the AOI when the completed pullback bar's low/high is within the configured profile-distance band around the developing VAP LVN, with completed-bar absorption/trapped-flow confirmation. Entry remains next 3-minute open.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| trend_lvn_buyer_trap_short_sierra_developing_vap_3m_1500 | 0/81 | 0 | 0 | -5067.5 | 0.461191 | -0.644844 | 62.62 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_seller_trap_long_sierra_developing_vap_3m_1500 | 0/81 | 0 | 0 | -1482.5 | 0.832628 | -0.380076 | 67.95 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_base_sierra_developing_vap_3m_1500 | 0/81 | 0 | 0 | -6722.5 | 0.564605 | -0.637914 | 124.81 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_delta_shift_sierra_developing_vap_3m_1500 | 0/81 | 0 | 0 | -5487.5 | 0.581586 | -0.625569 | 101.11 | min_total_net_profit;max_consecutive_losses |
| trend_lvn_two_sided_strong_sierra_developing_vap_3m_1500 | 0/81 | 0 | 0 | -5365.0 | 0.537001 | -0.627446 | 90.18 | min_total_net_profit;max_consecutive_losses |

Run4 verdict: FAIL. The corrected Sierra developing VAP branch had 0/405 profitable combinations and 0 benchmark-passing combinations. No corrected 3-minute variant reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

## Exact-Video Proxy Run5

Run5 implements the transcript mechanics as far as the historical data and current staged engine allow:

- AOI requires at least two of the video's four criteria: market-generated levels, volume profile/LVN, big trades, and delta activity.
- Market-generated levels include prior RTH high/low and overnight high/low. Exact 30-second ORB is unavailable in the cache and is not approximated.
- Volume profile and LVNs are built from current-session Sierra price-level VAP through the completed 3-minute signal bar, not from the final session profile.
- Big trades use the joined ES `large200_record_max_volume` and `large200_signed_volume` aggregate fields. This is the available historical proxy for the video's 200-lot ES trade criterion, not vendor MBO bubble sequencing.
- Model 1 range variants trade failed breaks at developing VAH/VAL with absorption/trapped-flow confirmation and structural targets at value midpoint or the opposite value edge.
- Model 2 trend variants require acceptance beyond developing value, pullback into an LVN, absorption/trapped-flow confirmation, and trend-direction delta shift, with structural high/low targets where valid.
- Entry is the next 3-minute open after the completed signal bar. Stops are beyond the signal-bar wick/AOI invalidation via `sweep_extreme`. Targets use `signal_price` with fixed-R fallback because the engine does not model partial trims and dynamic trailing.

Run5 cache:

- `data/cache/orderflow/es_video_aoi_exact_developing_vap_large200_3m_20120103_20260529_rth_ny.parquet`
- Validation: 464,230 rows, 0 duplicate timestamps, 432,091 bars with developing VAP, 463,450 bars with overnight levels, and 78,433 bars with large-200 aggregate records.
- Configured full subset: 2012-01-03 through 2026-05-29 RTH.
- Resolved limited-core shortlist subset: 2012-02-22 through 2013-07-31 RTH. This is the repo's seeded limited-core screen, not a full-window WFA/Monte Carlo result.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| video_model1_range_midpoint_two_sided_exact_3m_1500 | 0/81 | 0 | 0 | -7070.0 | 0.500882 | -0.652638 | 141.89 | min_total_net_profit;max_consecutive_losses |
| video_model1_range_opposite_edge_two_sided_exact_3m_1500 | 0/81 | 0 | 0 | -6577.5 | 0.507119 | -0.653812 | 141.20 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_buyer_trap_short_exact_3m_1500 | 0/81 | 0 | 0 | -5.0 | 0.999127 | -0.001453 | 65.03 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_seller_trap_long_exact_3m_1500 | 0/81 | 0 | 0 | -3792.5 | 0.565578 | -0.600371 | 81.63 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_structural_two_sided_exact_3m_1500 | 0/81 | 0 | 0 | -3707.5 | 0.738862 | -0.528386 | 136.52 | min_total_net_profit;max_consecutive_losses |

Run5 verdict: FAIL. The exact-video proxy branch had 0/405 profitable combinations and 0 benchmark-passing combinations on the limited-core shortlist screen. No exact-video proxy variant reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS. No candidate strategy report was created.

## Run5 Failure Investigation

The run5 failure was not caused by missing signals. All five variants generated trades across every grid combination. The failure was caused by poor expectancy after realistic ES costs and weak robustness:

- Model 1 range variants generated about 203-207 trades per fixed-config run, but midpoint targets were often close to entry. Fixed-config midpoint median target distance was 6 ticks while median risk was 7 ticks, so many winners were too small to overcome stops plus commission/slippage.
- Model 1 opposite-edge targets improved reward distance but reduced hit rate. The fixed-config opposite-edge range branch still had 134 stops versus 67 targets and net -7180.0.
- Model 2 long-side trend continuation was structurally weak. The fixed-config long-only trend branch had net -4272.5, PF 0.5054, and only 27.35% win rate.
- Model 2 short-side trend continuation was the only branch close to usable. The best run5 short-only grid row was net -5.0, PF 0.9991, but still failed minimum net profit and max losing streak. In the fixed config, four-confluence short trades were positive, while two-confluence short trades were materially negative.
- Increasing fallback target R helped trend variants in the grid, but did not create benchmark-passing parameter neighborhoods. That suggests the issue is not a single bad stop/target setting; it is signal quality and target-distance fragility.

## Quality-Filter Run6

Run6 was a result-informed rescue branch, not an exact-video proxy. It kept the AOI/LVN/orderflow edge family but tested two diagnostics from run5:

- Require stronger AOI quality through higher `min_aoi_confluences`.
- Avoid unusably close structural targets with `tp.params.min_signal_target_r_multiple`, falling back to a predeclared fixed-R target when the structural target was too close.

Five run6 variants were created under:

- `campaigns/es_video_aoi_lvn_orderflow_playbook/rescue_attempts/user_exact_video_quality_run6`

| Variant | Terminal stage | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| video_model2_trend_lvn_short_high_confluence_minrr_3m_1500 | limited_monkey_test | 40/54 | 0 | 0 | 1150.0 | 1.227048 | 0.459811 | 46.55 | core passed, then monkey failed: drawdown-beat 0.553875 below 0.9; selected core row still failed trade count, losing streak, and best-day concentration |
| video_model2_trend_lvn_two_sided_high_confluence_minrr_3m_1500 | limited_core_grid_test | 0/54 | 0 | 0 | -520.0 | 0.893715 | -0.130458 | 34.47 | min_total_net_profit;min_trades_per_year;max_consecutive_losses;preferred_min_total_trades |
| video_model2_trend_lvn_long_high_confluence_minrr_3m_1500 | limited_core_grid_test | 0/54 | 0 | 0 | -920.0 | 0.677193 | -0.366403 | 20.40 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
| video_model1_range_opposite_edge_quality_minrr_3m_1500 | limited_core_grid_test | 0/54 | 0 | 0 | -50.0 | 0.975309 | -0.033630 | 18.71 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
| video_model1_range_midpoint_quality_minrr_3m_1500 | limited_core_grid_test | 6/54 | 0 | 0 | 162.5 | 1.084088 | 0.127971 | 18.71 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |

Run6 verdict: FAIL. The quality filters improved one narrow short-side branch enough to pass limited core, but it failed the monkey robustness gate and never reached WFA, Monte Carlo, simulated incubation, or acceptance OOS. The result is not a candidate strategy.

## Exact-ORB Run7

Run7 is an exactness-only rerun of run5. It keeps the run5 entry/stop/target mechanics and parameter grid frozen, but replaces the joined cache with a cache that includes raw Sierra 09:30:00-09:30:30 ET ORB high/low for every 3-minute RTH row.

- Cache: `data/cache/orderflow/es_video_aoi_exact_developing_vap_large200_orb30_3m_20120103_20260529_rth_ny.parquet`
- Validation: 464,230 rows, 0 duplicate timestamps, 432,091 bars with developing VAP, 463,450 bars with overnight levels, 78,433 bars with large-200 aggregate records, 464,230 bars with exact 30-second ORB.
- Configured full subset: 2012-01-03 through 2026-05-29 RTH.
- Resolved limited-core shortlist subset: 2012-02-22 through 2013-07-31 RTH.
- Remaining unsupported video mechanics are not approximated: live DOM/tape speed, partial trims, add-ons, and dynamic trailing remainder.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| video_model1_range_midpoint_two_sided_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -7417.5 | 0.490031 | -0.651146 | 143.29 | min_total_net_profit;max_consecutive_losses |
| video_model1_range_opposite_edge_two_sided_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -6887.5 | 0.495144 | -0.665485 | 142.59 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_buyer_trap_short_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -5.0 | 0.999127 | -0.001453 | 65.03 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_seller_trap_long_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -3792.5 | 0.565578 | -0.600371 | 81.63 | min_total_net_profit;max_consecutive_losses |
| video_model2_trend_lvn_structural_two_sided_orb30_exact_3m_1500 | 0/81 | 0 | 0 | -3707.5 | 0.738862 | -0.528386 | 136.52 | min_total_net_profit;max_consecutive_losses |

Run7 verdict: FAIL. Adding exact 30-second ORB market levels improved mechanical fidelity to the video, but all five exact-ORB variants failed limited_core_grid_test with 0/405 profitable combinations and 0 benchmark-passing combinations. No run7 variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

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

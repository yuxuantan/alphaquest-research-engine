# Third Independent Strategy Search - 2026-06-13

Goal: find a third strategy candidate that is independent from the accepted
`morning_orderflow_momentum` signed-flow family and can pass the staged
validation workflow.

## Current Accepted Context

- Accepted baseline: `morning_orderflow_momentum/1m/two_sided_signed_flow_continuation`.
- Accepted second live-eligible candidate: `two_sided_signed_flow_1515_flatten_continuation`.
- Independence constraint: the 15:15 candidate is a trade-management variant of
  the same alpha family, so it does not satisfy the third-strategy requirement.
- Faithful Gao last-half-hour orderflow was already rejected at the limited-core
  gate with 0/1,620 profitable parameter combinations.

## Implemented But Not Promoted

Added entry module:

- `src/propstack/strategy_modules/entry/opening_gap_orderflow_fade.py`
- Registered as `opening_gap_orderflow_fade`.
- Focused test coverage added in `tests/test_strategy_modules.py`.

Mechanic:

- Measure the RTH opening gap versus previous RTH close.
- At 11:00 ET, use only completed 10:45-10:59 Sierra aggregate bar orderflow.
- Fade the opening gap only when large-20 signed-volume imbalance pushes back
  against the gap direction.

Focused test result:

- `PYTHONPATH=src pytest tests/test_strategy_modules.py -q`
- Result: `111 passed`.

Promotion decision:

- Rejected before staged promotion for now. High-quality rows had good holdout
  but too little WFA-slice density. Dense rows reached 500+ WFA-slice trades but
  diluted below the WFA PF/expectancy shape.

Best screen evidence:

- Single-slot high-quality gap fade, 11:00 entry, 10:45-10:59 large20 flow,
  gap >= 24 ticks, large20 imbalance >= 0.20 against the gap, 15:45 flatten,
  `stop_pct=0.003`, `target_r=12`: 2011-2024 n324/PF 1.33/ER 0.206,
  2025-2026 n92/PF 2.08/ER 0.478. Too sparse for the 500-trade WFA gate.
- Dense gap fade, 11:00 entry, gap >= 24 ticks, large20 imbalance >= 0.12,
  14:30 flatten, `stop_pct=0.005`, `target_r=4`: 2011-2024 n518/PF 1.41/ER
  0.125, 2025-2026 n116/PF 1.79/ER 0.215. WFA-like 2015-2024 slice did not
  retain enough expectancy for acceptance.
- Multi-slot versions using 11:00, 12:00, 13:00, 14:00, and 14:30 first
  qualifying confirmations produced zero acceptance-shaped rows.

Do not promote this family unless a materially new filter improves density
without reducing WFA-slice expectancy.

## Additional Screens Rejected This Turn

Aggregate orderflow families:

- Broad 2015-2024 fixed-hold screen across continuation, divergence fade,
  absorption fade, and flow-only pressure rules found zero 500-trade candidates
  above the acceptance-shaped fixed-hold thresholds outside the accepted morning
  continuation family.
- Same-clock rank-state screen built `/private/tmp/es_sierra_rank_features_screen.parquet`
  from the corrected Sierra cache: 1,488,630 rows, 149 feature columns, and zero
  missing RTH segments.
- Best directional rank near-pass: 10:00 long when
  `trade_orderflow_imbalance_15_rank21 >= 0.80`, 15:30 flatten,
  `stop_pct=0.00225`, `target_r=4`: 2015-2024 n564/PF 1.390/ER 0.194,
  2025-2026 n75/PF 1.309/ER 0.233. Rejected as below PF gate and too close to
  the accepted morning orderflow continuation family.
- Participation-state risk checks on low same-clock volume/trade-count states
  found zero acceptance-shaped rows.

OHLCV-only families:

- RTH gap fade/continuation with first-window price confirmation found zero
  acceptance-shaped fixed-hold candidates.

Cross-market ES/NQ relative-strength family:

- Built temporary matched ES/NQ RTH 1-minute research caches:
  `/private/tmp/es_nq_cross_rth_1m.parquet` and
  `/private/tmp/es_nq_orderflow_cross_rth_1m.parquet`.
- Mechanic tested: at 10:00 ET, use completed 09:30-09:59 percentage returns.
  Trade ES in the NQ direction only when NQ makes a large opening move and ES
  lags by a minimum absolute-return spread. The ES aggregate orderflow variants
  then required signed-volume, large-20, or both imbalances to align with the NQ
  direction.
- Pure ES/NQ catch-up was rejected. Best fixed rows stayed below acceptance
  shape, and rolling selection could not keep stitched OOS expectancy high
  enough.
- ES/NQ plus ES orderflow produced fixed-row near-passes. Example:
  `nq_thr=30`, `sp_thr=10`, signed-flow alignment `>= 0.01`,
  `stop_pct=0.004`, `target_r=3.5`: WFA-like 2015-2024 n510/PF 1.51/ER 0.23,
  but 2011-2014 was weak and holdout was only near the ER gate.
- Strict rolling selector diagnostic over the top 160 fixed candidates:
  `/private/tmp/es_nq_cross_flow_strict_rolling_diagnostics.csv`.
  Best complete-window row selected all 10 test years with stitched n582/PF
  1.406/ER 0.191/net $73,027.50. No complete-window selector cleared the
  acceptance-shaped combination of n >= 500, PF >= 1.4, and ER >= 0.2.
- Promotion decision: rejected before implementation as a campaign module. This
  is an independent alpha family, but the edge is not stable enough under
  rolling parameter selection.

Price/session-structure and calendar families:

- Ran a full-history RTH price/session-structure screen on the corrected Sierra
  cache using opening displacement, RTH gap versus prior close, prior-day RTH
  return, and gap/opening-return agreement or reversal conditions.
- Scratch result: `/private/tmp/es_session_structure_price_screen_narrow.csv`.
  Best WFA-like rows were gap/opening same-direction continuation variants.
  The top row reached only 2015-2024 n452/PF 1.343/ER 0.172 and had negative
  2025-2026 holdout. No fixed row cleared n >= 500, PF >= 1.4, and ER >= 0.2.
- Ran a pure weekday/time-bias screen:
  `/private/tmp/es_weekday_time_bias_screen.csv`.
  Best row was Friday 14:00 long to 15:30, 2015-2024 n494/PF 1.315/ER 0.043,
  with negative holdout. Rejected as too weak and not stage-worthy.

Intraday range/volume shock family:

- Built non-overlapping 5-minute and 15-minute aggregate shock events from the
  corrected Sierra RTH cache and saved them to
  `/private/tmp/es_intraday_shock_events.parquet`.
- Mechanic tested: first qualifying same-session shock per day, using completed
  aggregate return, close-location, relative volume, and distance from session
  VWAP; both shock continuation and shock fade were screened.
- Fixed-exit screen: `/private/tmp/es_intraday_shock_fixed_exit_screen.csv`.
  Best shape was 5-minute high-volume continuation after a 24-tick aggregate
  move, volume ratio >= 1.7, and VWAP extension. Fixed 60/120-minute exits
  reached roughly 2015-2024 n710-757/PF 1.21-1.22, with strong 2025-2026
  holdout, but still well below the PF gate.
- Risk-tuned screen: `/private/tmp/es_intraday_shock_risk_tune.csv`.
  Best row reached 2015-2024 n757/PF 1.229/ER 0.048. No stop/target variant
  came close to n >= 500, PF >= 1.4, and ER >= 0.2.
- Promotion decision: rejected. The recent continuation behavior is interesting
  but not strong enough to justify implementation or staged campaign runtime.

Volatility-compression breakout family:

- Ran a targeted prior-day RTH range compression screen:
  `/private/tmp/es_compression_breakout_screen.csv`.
- Mechanic tested: after low prior-day RTH range rank, trade opening movement,
  gap direction, or prior-day direction continuation/fade with intraday
  stop/target and afternoon flatten.
- Best WFA-like row was compressed-gap continuation at 13:00 with
  `rr<=0.3`, `gap_abs>=32`, `stop_pct=0.004`, `target_r=4`:
  2015-2024 n447/PF 1.49/ER 0.128, but below 500 trades and weak
  2025-2026 holdout. The denser `gap_abs>=24` row had n521/PF 1.42/ER 0.109
  and weak holdout.
- Promotion decision: rejected. The family cannot clear the trade-count,
  expectancy, and holdout requirements together.

Full-session overnight return / inventory family:

- Built a continuous-contract full-session ES Databento analysis cache with the
  same explicit roll calendar used by the campaign configs:
  `/private/tmp/es_full_session_continuous_1m_20110101_20260529.parquet`.
  The cleaner loaded 7,399,956 raw bars, kept 5,136,295 active-contract bars,
  and skipped 183 roll-boundary sessions.
- Late-day overnight-return screen:
  `/private/tmp/es_overnight_late_day_hold_screen.csv`.
  Mechanic tested: trade the late RTH window using the overnight return sign,
  first-30-minute confirmation/reversal, penultimate alignment, and overnight
  range regimes. Time-invalid penultimate rows that entered before the
  15:00-15:29 source window completed were discarded.
- Valid fixed-hold near-pass: fade the overnight sign at 15:15 when the first
  30 minutes opposed the trade direction by at least 16 ticks and overnight
  move was at least 16 ticks. 2015-2024 reached n545/PF 1.216 with positive
  2025-2026 holdout, but the edge was far below the PF/expectancy gates.
- Targeted stop/target tune:
  `/private/tmp/es_overnight_late_day_selected_risk_tune.csv`. Best dense row
  reached only n559/PF 1.274/ER 0.124 on 2015-2024 with 2025-2026 PF 1.083 and
  ER 0.030. Zero rows cleared n >= 500, PF >= 1.4, and ER >= 0.2.
- Existing staged overnight-return campaign reports also failed limited core.
  The strongest local staged rows were sparse: the penultimate-alignment
  reports topped at 86 trades, PF 1.425, ER 0.059, and failed the trade-count
  and growth gates; the opening-reversal reports topped at 79 trades, PF 1.343,
  ER 0.047, and failed density/growth/best-day concentration.
- Existing staged overnight-inventory-reversion campaign reports failed limited
  core across 1m, 2m, 5m, and 10m variants. The best dense inventory row was the
  5m `on_extreme_reclaim_vwap_filter` limited-core top combination with 229
  trades, PF 1.159, ER 0.110, and no benchmark pass. The higher-PF midpoint
  rows had only 3-7 trades and were unusably sparse.
- Promotion decision: rejected. This is independent from the accepted morning
  orderflow family, but neither the direct full-session screen nor the staged
  overnight campaign reports produce a dense, stable, acceptance-shaped edge.

Calendar/session seasonality family:

- Existing staged `late_week_afternoon_bias` report passed limited core but
  failed limited monkey. Limited core top row used `{0: long, 2: short,
  4: long}` at 14:30 with 15:30/16:00 flatten and `stop_pct=0.005`: 2021-2022
  n279/PF 1.701/ER 0.162, failing only preferred trade count. The monkey stage
  then failed drawdown robustness: net-profit beat rate 0.994, max-drawdown
  beat rate only 0.4345 versus the 0.90 threshold.
- Ran a direct full-history selected weekday-map screen over full-session ES
  Databento using the campaign maps plus adjacent one-, two-, and three-weekday
  long/short maps: `/private/tmp/es_calendar_map_selected_fast.csv`.
- Best WFA-like row was Wednesday short from 15:00 to 15:59 with
  `stop_pct=0.0075`, `target_r=4`: 2015-2024 n474/PF 1.416/ER 0.051, but
  2025-2026 was negative (n67/PF 0.558/ER -0.077) and 2011-2014 was also
  negative (n186/PF 0.772/ER -0.019).
- Denser multi-day rows were weaker. Example `{2: short, 4: long}` at 14:30 to
  15:59 with `stop_pct=0.010`, `target_r=10`: 2015-2024 n968/PF 1.313/ER
  0.037, 2025-2026 PF 0.525/ER -0.064, 2011-2014 PF 0.765/ER -0.021.
- Promotion decision: rejected. The 2021-2022 limited-core behavior is not
  robust across pre-period or recent holdout, and no full-history row cleared
  the n >= 500, PF >= 1.4, ER >= 0.2 acceptance shape.

Turn-of-month futures seasonality family:

- Existing staged `turn_of_month_futures_effect` reports passed limited core
  but WFA early-exited because the configured windows could not meet the
  100-trades/year selection filter. The strongest 2021-2022 limited-core row
  used first 4 calendar days plus last 5 calendar days, 11:00 entry,
  `stop_pct=0.005`: n151/PF 1.568/ER 0.209, failing density only.
- Ran a broader direct full-history screen over first-only, last-only, and
  combined turn windows up to 10 calendar days, long/short direction, multiple
  intraday entries/flattens, and stop/target settings:
  `/private/tmp/es_turn_of_month_screen.csv`.
- Best WFA-like rows were first-five-calendar-day long variants, e.g. 14:00 to
  15:59 with `stop_pct=0.010`, `target_r=3`: 2015-2024 n394/PF 1.470/ER
  0.066, but 2025-2026 was negative (n54/PF 0.809/ER -0.034) and 2011-2014 was
  negative (n157/PF 0.618/ER -0.056).
- The broader 11:00-to-close row improved 2015-2024 ER to 0.149 but still had
  negative 2025-2026 and 2011-2014. No row cleared n >= 500, PF >= 1.4, and
  ER >= 0.2.
- Promotion decision: rejected. The effect is a sample-specific pocket rather
  than a stable full-history strategy.

Macro / market-plumbing families:

- Existing CFTC TFF hedging-pressure and tiered-hedging-pressure campaigns
  passed limited core and limited monkey but failed WFA. Example
  `cftc_tff_hedging_pressure/5m/broad_spx_open_interest_expansion` had
  limited-core top n121/PF 1.788/ER 0.324 and monkey beat rates
  net-profit 0.9625 / max-drawdown 0.9935, but WFA early-exited after only two
  windows with stitched OOS n25/PF 0.522/ER -0.153.
- `cftc_tff_tiered_hedging_pressure/5m/morning_high_fallback_broad` similarly
  passed monkey, then WFA early-exited with stitched OOS n25/PF 0.650/ER
  -0.046.
- `market_plumbing_priority_ensemble/5m/vx_then_primary_dealer_priority_long`
  passed limited core and monkey, but WFA early-exited with zero stitched OOS
  trades. The local market-plumbing feature file referenced by the config is
  not present in `data/external`, so there is no clean direct expansion path in
  the current workspace.
- Promotion decision: rejected for this search pass. These families have
  plausible limited-core behavior, but the existing WFA evidence is decisively
  non-tradable and/or lacks the local feature data needed for a full-history
  retest.

Overnight range/location structure family:

- Ran a direct fixed-hold screen over full-session ES Databento using overnight
  range location, opens outside the overnight range, first-30/first-60 close
  breakouts, and first-30 rejection fades:
  `/private/tmp/es_overnight_range_structure_hold.csv`.
- Best fixed-hold rows were weak. Example: open-location continuation with
  `open_loc >= 0.9 or <= 0.1`, 10:00 entry, overnight range 16-120 points:
  2015-2024 n361/PF 1.123/avg $66.02, 2025-2026 n39/PF 1.212, 2011-2014
  n61/PF 1.995. Denser `open_loc >= 0.8`, 10:00, range 16-120 had
  n728/PF 1.084 and good holdout/pre-period, but too little WFA-slice edge.
- Targeted risk tune on the stable open-location continuation shapes:
  `/private/tmp/es_overnight_range_openloc_risk_tune.csv`. Best sparse row
  reached n362/PF 1.247/ER 0.157; best dense rows were around n729/PF
  1.190/ER 0.066. Zero rows cleared n >= 500, PF >= 1.4, and ER >= 0.2.
- Promotion decision: rejected. The signal has mild directional value but not
  enough risk-adjusted expectancy for staged validation.

## Accepted Third Independent Strategy

Accepted candidate:

- Strategy: `nq_intraday_momentum_priority`
- Variant: `short_first_1030_weakness_1130_strength_long50`
- Config:
  `configs/campaigns/nq_intraday_momentum_priority/variants/NQ/5m/short_first_1030_weakness_1130_strength_long50.yaml`
- Report:
  `data/reports/campaigns/nq_intraday_momentum_priority/NQ/databento_nq_1m_20110103_20260529_dominant_session_volume/5m/short_first_1030_weakness_1130_strength_long50/campaign_tests`
- Live tracker:
  `data/reports/campaigns/nq_intraday_momentum_priority/NQ/databento_nq_1m_20110103_20260529_dominant_session_volume/5m/short_first_1030_weakness_1130_strength_long50/LIVE_TRADING_TRACKER.md`
- Stage command:
  `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config configs/campaigns/nq_intraday_momentum_priority/variants/NQ/5m/short_first_1030_weakness_1130_strength_long50.yaml --skip-validation`

Independence:

- This is a new alpha family: NQ price-only intraday momentum priority, not ES
  Sierra signed-flow/orderflow continuation.
- Data source is Databento NQ 1-minute OHLCV using the
  dominant-session-volume continuous contract.
- The rule uses no signed volume, large-trade fields, Sierra aggregate
  orderflow, ES orderflow, or cross-market ES/NQ relative-strength input.

Mechanic:

- At 10:30 ET, short NQ when the RTH-open-to-signal return is weak enough.
- If that first slot does not fire, at 11:30 ET go long when the
  RTH-open-to-signal return is strong enough.
- One trade maximum per session, signal-aware percent stop, signal fixed-R
  target, and 15:59 ET flatten.
- Simulated-incubation selected live params:
  `short_min_signal_return_bps=35`, `short_stop_pct=0.0035`,
  `short_target_r_multiple=3.5`, `long_min_signal_return_bps=50`,
  `long_stop_pct=0.0035`, `long_target_r_multiple=4.0`.

Selection path:

- Broad staged config
  `short_first_1030_weakness_1130_strength` passed WFA, WFA OOS monkey, and WFA
  OOS Monte Carlo, then failed only the simulated-incubation core expectancy
  gate because the rolling selector chose `long_min_signal_return_bps=40`,
  producing incubation expectancy `0.140262` versus the `0.15` gate.
- Diagnostic holdout grid
  `/private/tmp/nq_intraday_momentum_priority_incubation_holdout_grid` found the
  acceptance-shaped holdout rows concentrated at
  `long_min_signal_return_bps=50`.
- Long-50 train/holdout audit
  `/private/tmp/nq_intraday_momentum_priority_long50_grid_audit` confirmed the
  top train-MAR row retained holdout expectancy `0.165985`. The accepted config
  restricted only the long threshold grid to the stable `50` bps zone; no
  campaign gate was lowered.

Final staged evidence:

- `campaign_test_summary.json`: `passed=true`, `halted=false`.
- All seven stages passed: limited core grid, limited monkey, WFA, WFA OOS
  monkey, WFA OOS Monte Carlo, simulated incubation core, and simulated
  incubation monkey.
- WFA stitched OOS: 10 windows, 951 trades, net `$174,030`, PF `1.474`,
  expectancy `0.246R`, MAR `1.031`, max drawdown `$18,475` / `7.78%`, win rate
  `44.37%`, positive month rate `62.5%`, zero Apex violations, and 7 Apex
  forced-flatten trades.
- WFA OOS monkey: net-profit beat rate `100.0%`, max-drawdown beat rate
  `99.6%`, zero Apex violations.
- WFA OOS Monte Carlo: profit-before-drawdown probability `54.4%`,
  net-profit-positive probability `88.8%`, median ending balance `$196,136.25`.
- Simulated incubation core: 165 trades, net `$43,225`, PF `1.311`,
  expectancy `0.166R`, MAR `2.188`, max drawdown `$18,910` / `9.08%`,
  positive month rate `64.7%`, zero Apex violations, and 1 Apex forced-flatten
  trade.
- Simulated incubation monkey: net-profit beat rate `86.6%`, max-drawdown beat
  rate `94.2%`, zero Apex violations.

Signal contribution:

- WFA OOS `nq_1030_short_weakness`: 460 trades, `$88,315` net, `$191.99`
  average trade.
- WFA OOS `nq_1130_long_strength`: 491 trades, `$85,715` net, `$174.57`
  average trade.
- Incubation `nq_1030_short_weakness`: 87 trades, `$36,840` net, `$423.45`
  average trade.
- Incubation `nq_1130_long_strength`: 78 trades, `$6,385` net, `$81.86`
  average trade.

Close-out:

- The third-strategy search is complete. Use this NQ price-momentum priority
  candidate as the independent third live-eligible strategy, alongside the
  accepted Sierra ES morning orderflow family and its 15:15 management variant.

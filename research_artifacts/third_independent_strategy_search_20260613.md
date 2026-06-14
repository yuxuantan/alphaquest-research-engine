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
- Corrected the unresolved staged artifact for
  `orderflow_opening_drive/ES/1m/opening_price_flow_divergence_fade`: the prior
  campaign summary had only recorded an `[Errno 1] Operation not permitted`
  runner failure. Rerun command:
  `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config configs/campaigns/orderflow_opening_drive/variants/ES/1m/opening_price_flow_divergence_fade.yaml --skip-validation`.
  Result path:
  `data/reports/campaigns/orderflow_opening_drive/ES/sierra_trade_orderflow_1m_20101229_20260609_full_rth_ny/1m/opening_price_flow_divergence_fade/campaign_tests`.
  The rerun failed `limited_core_grid_test` on evidence: 144/144 combinations
  tested, 62 profitable, profitable-iteration rate `0.4306` versus required
  `0.70`, zero Apex-violating iterations, and zero benchmark-passing rows.
  Best row was `min_open_return_ticks=16`, `max_abs_open_imbalance=0.02`,
  `target_r_multiple=1.0`, `stop_pct=0.0075`: only 25 trades, net `$3,675`,
  PF `2.608`, expectancy `0.214R`, MAR `1.733`, and failure reason
  `min_trades_per_year;preferred_min_total_trades`. Rejected because the
  high-quality rows are too sparse and the parameter neighborhood is not broad
  enough for core robustness.
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

## Passed NQ Momentum Candidate, Not Strict Third Alpha

Passed candidate:

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

Independence classification:

- This is not a strict new alpha family when independence is defined by the
  economic edge. The broad premise is still intraday momentum/continuation,
  overlapping the accepted ES morning momentum/orderflow family.
- It is independent only at the implementation layer: NQ price-only intraday
  momentum priority, not ES Sierra signed-flow/orderflow continuation.
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

## ES Large-Trade Pressure Reversion Follow-up

- User clarified to trade ES, not NQ yet, and asked about liquidity-sweep style
  mechanics. Price-only sweep/reclaim and trade-side sweep/fade families were
  already rejected in the ledger.
- Ran a bounded no-write ES-only screen on the corrected full-history Sierra
  trade-orderflow cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
- Thesis tested: after completed 5/15/30/60-minute aggressive large-20-lot
  buy/sell pressure and price extension, fade the pressure on ES using only
  next-minute entries and same-session flat exits. Academic motivation is
  liquidity-pressure/order-flow information literature, but the test remains
  aggregate trade-side, not quote-depth.
- Result paths:
  `/private/tmp/sierra_large_trade_pressure_reversion_fast_all.csv` and
  `/private/tmp/sierra_large_trade_pressure_reversion_fast_top.csv`.
- Screened 56,854 no-lookahead snapshots and 3,171 positive split rows. Gate
  audit found zero rows with `wfa_n >= 500`, zero rows with
  `wfa_n >= 500` and `wfa_pf >= 1.3`, and zero rows with
  `wfa_n >= 300`, `wfa_pf >= 1.4`, `incubation_n >= 50`, and
  `incubation_pf >= 1.2`.
- Top displayed rows were sparse WFA/core artifacts or failed incubation. For
  example, late-day long-after-sell-pressure rows reached WFA PF above 2.4 with
  only 33-66 WFA trades and negative 2025-2026 incubation; earlier 10:30/11:00
  rows with high PF had 18-28 WFA trades and zero core/incubation coverage.
- Promotion decision: rejected before staged implementation. Do not promote or
  rerun simple Sierra large-trade pressure fade, large-20 imbalance reversion,
  or aggregate trade-side capitulation fade without materially new structure
  such as quote/depth imbalance, book-sweep measures, or a stronger
  point-in-time regime filter.

## ES Liquidity-Sweep Depth Data Gate

- Conclusion on "liquidity sweep": do not rerun another price-only sweep/reclaim
  or trade-side-only sweep/fade. Those families are already rejected locally,
  including PDH/PDL sweep, overnight high/low reclaim, opening-range failed-break
  fade, ICT/SMC liquidity sweep plus FVG retrace, and Databento one-year
  trade-side sweep/reversal.
- The only version still distinct enough to justify a new ES mean-reversion
  branch is quote/depth-confirmed failed liquidity demand: a stop-run through a
  prior high/low or opening-range level where top-of-book or order-book events
  show thin liquidity, depth removal, or aggressive liquidity demand that fails
  and refills/reclaims quickly. This is a different thesis from the accepted
  trend-following/orderflow continuation systems.
- Academic backing:
  - Cont, Kukanov, and Stoikov, "The Price Impact of Order Book Events"
    (`https://arxiv.org/abs/1011.6402`), support measuring supply/demand at the
    best bid/ask through order-flow imbalance and market depth rather than
    price alone.
  - Hendershott and Menkveld, "Price Pressures"
    (`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1411943`), support the
    idea that liquidity-demand shocks can create temporary price pressure that
    mean-reverts as intermediaries manage inventory.
  - Chordia, Roll, and Subrahmanyam, "Order Imbalance, Liquidity, and Market
    Returns"
    (`https://www.cis.upenn.edu/~mkearns/finread/Chordia_buy-sell_orders.pdf`),
    support order imbalance as a liquidity and return state variable.
- Databento metadata probe only; no quote/depth files were downloaded. Dataset
  `GLBX.MDP3`, symbol `ES.FUT`, `stype_in=parent`, RTH sessions. Availability:
  `tbbo`, `mbp-1`, and `mbp-10` begin in 2010; `mbo` begins in 2017 and should
  start requests at UTC midnight to include Databento's synthetic book snapshot.
- Full-history sampled cost estimates, 2011-01-03 through 2026-06-09 unless
  noted:
  - `tbbo`: 4,027 available sessions, 16 sampled, estimated `$2,302` by sample
    average or `$2,456` by nonzero-day average.
  - `mbp-1`: 4,027 available sessions, 16 sampled, estimated `$1,832` by sample
    average or `$1,954` by nonzero-day average.
  - `mbp-10`: 4,027 available sessions, 16 sampled, estimated `$3,527` by
    sample average or `$3,762` by nonzero-day average; rejected for this pilot
    because it adds large data volume without a clear first-pass need.
  - `mbo`: 2,362 available sessions from 2017-05-22 through 2026-06-09, 16
    sampled, estimated `$1,666` by sample average or `$1,777` by nonzero-day
    average.
- One-year pilot sampled cost estimates for 2025-06-09 through 2026-06-09:
  `tbbo` about `$7` by sample average / `$119` by nonzero-day average, `mbp-1`
  about `$10` / `$158`, and `mbo` about `$309` / `$353`.
- Size/processing caution: recent 2026-06-09 billable sizes were about `64 MB`
  for `tbbo`, `1.26 GB` for `mbp-1`, `7.83 GB` for `mbp-10`, and `1.77 GB` for
  midnight-start `mbo`. The recent 2026-05-11 through 2026-06-09 exact probe
  reported `tbbo` at about `664 MB` versus `mbp-1` at about `12.7 GB`.
- Recommendation: if pursuing liquidity sweep, run a bounded one-year `tbbo`
  pilot first. Define the sweep using completed top-of-book/trade events around
  PDH/PDL and opening-range levels, then promote only if the pilot produces
  simple split-stable candidates. Do not buy/download full-history depth, and do
  not start with `mbo` or `mbp-10`, until the `tbbo` pilot shows a real edge that
  specifically needs deeper book reconstruction.

## ES/MES Micro-Flow Divergence Mean-Reversion Lead

- Status: positive limited-sample ES lead, now packaged as a reproducible
  campaign branch, but still not accepted or live eligible.
- Thesis: trade ES against micro-contract flow pressure when MES aggressive-flow
  imbalance diverges from ES. MES is not a pure retail feed, but it is the
  smaller notional contract and can act as a small-participant/liquidity-demand
  proxy. The branch is a mean-reversion/liquidity-pressure thesis, not an
  intraday trend-continuation thesis.
- Academic backing:
  - Kaniel, Saar, and Titman, "Individual Investor Trading and Stock Returns"
    (`https://doi.org/10.1111/j.1540-6261.2008.01316.x`), supports the idea
    that individual-investor trading can be linked to short-horizon liquidity
    provision and subsequent returns.
  - Barber, Odean, and Zhu, "Do Retail Trades Move Markets?"
    (`https://doi.org/10.1093/rfs/hhn035`), supports studying small/retail
    order imbalance as a separate return-pressure state.
  - Hasbrouck-style cross-market price-discovery literature motivates testing
    whether the higher-notional ES contract confirms or rejects the smaller
    MES flow signal.
- Data used:
  - Existing ES Databento trade-side cache:
    `data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv`.
  - Newly built local scratch MES trade-side cache:
    `/private/tmp/mes_trade_orderflow_1m_20250610_20260608.csv`.
  - MES builder command:
    `PYTHONPATH=src python3 -m propstack.build_trade_orderflow_cache --raw-dir data/raw/MES-comparison/databento-mes-trades --out-csv /private/tmp/mes_trade_orderflow_1m_20250610_20260608.csv --monthly-cache-dir /private/tmp/mes_trade_orderflow_monthly_cache --root-symbol MES --contract-symbol-regex '^MES[HMUZ][0-9]$' --complete-session-end 15:59:00`.
  - Reproducible ES/MES merged cache builder added:
    `src/propstack/data/es_mes_flow_divergence.py` and
    `src/propstack/build_es_mes_flow_divergence_cache.py`.
  - Merged ES trading cache written:
    `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv`,
    with 96,330 shared ES/MES RTH minute bars and completed rolling
    ES/MES imbalance, large-trade imbalance, return, and divergence columns.
  - Focused builder test:
    `PYTHONPATH=src pytest -q tests/test_es_mes_flow_divergence.py`
    passed (`1 passed`).
- Screen artifacts:
  `/private/tmp/mes_es_flow_divergence_flat_all.csv`,
  `/private/tmp/mes_es_flow_divergence_flat_top.csv`,
  `/private/tmp/mes_es_flow_divergence_robustness.csv`, and
  `/private/tmp/mes_es_flow_divergence_robustness_trades.csv`.
- Flat screen result: 12,756 positive rows, maximum score 6, 415 rows with
  score >= 5, and 115 rows with score >= 6. Score required at least 50 trades,
  PF >= 1.4, average trade >= `$75`, and positive PF >= 1.2 splits across
  2025 train, 2026-Q1 validation, and 2026-Q2 holdout.
- Distinct top families:
  - `mes_minus_es_sell_div_long`, 30-minute all-flow divergence, enter ES long
    10:00 and exit 11:31 when completed MES imbalance is at least 0.02 more
    sell-pressured than ES: n67, net `$20,827.50`, PF `2.073`, average
    `$310.86`, train PF `1.854`, Q1 PF `1.644`, Q2 PF `4.511`.
  - `mes_buy_price_lte_16_short`, 5-minute MES large-20 buy-pressure fade,
    enter ES short 14:00 and exit 15:31 when completed MES large-20 imbalance
    >= 0.15 and the completed 5-minute ES price move is <= 16 ticks: n50, net
    `$11,200`, PF `2.397`, average `$224.00`, train PF `2.916`, Q1 PF
    `2.679`, Q2 PF `1.554`.
  - `mes_minus_es_sell_div_long`, 3-minute MES large-20 sell-pressure
    divergence, enter ES long 13:00 and exit 14:31 when MES large-20 imbalance
    is at least 0.15 more sell-pressured than ES: n73, net `$11,822.50`, PF
    `1.859`, average `$161.95`, train PF `1.844`, Q1 PF `1.529`, Q2 PF
    `2.498`.
- Narrow stop/target robustness on the top families found 56 flat/managed rows
  with n >= 50, all three splits PF >= 1.2, and PF >= 1.2 after an extra `$25`
  round-turn cost stress.
- Strongest managed row: 14:00 ES short after 5-minute MES large-20 buy
  pressure, `stop_pct=0.0035`, `target_r=1.5`, 15:31 flatten. Metrics: n50,
  net `$11,303.13`, PF `2.450`, average `$226.06`, train PF `2.969`, Q1 PF
  `2.862`, Q2 PF `1.554`; +`$25` cost stress PF `2.201`, +`$50` stress PF
  `1.982`, worst leave-one-month-out PF `2.015`.
- Campaign promotion probe:
  - Campaign metadata:
    `configs/campaigns/mes_es_flow_divergence_reversion/campaign.yaml`.
  - 10:00 variant config:
    `configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/morning_mes_sell_pressure_divergence_long.yaml`.
    Command:
    `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/morning_mes_sell_pressure_divergence_long.yaml --skip-validation`.
    Result path:
    `data/reports/campaigns/mes_es_flow_divergence_reversion/ES/es_mes_trade_orderflow_1m_20250610_20260608/1m/morning_mes_sell_pressure_divergence_long/campaign_tests`.
    It failed `limited_core_grid_test`: 100 combinations tested, 57% profitable
    iterations versus the required 70%, zero Apex-violating iterations. Best
    row was still positive, n67/net `$18,090`/PF `1.814`/MAR `3.450`/
    expectancy `0.161R`, but the parameter neighborhood was not stable enough.
  - 14:00 variant config:
    `configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/afternoon_mes_large20_buy_pressure_short.yaml`.
    Command:
    `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/afternoon_mes_large20_buy_pressure_short.yaml --skip-validation`.
    Result path:
    `data/reports/campaigns/mes_es_flow_divergence_reversion/ES/es_mes_trade_orderflow_1m_20250610_20260608/1m/afternoon_mes_large20_buy_pressure_short/campaign_tests`.
    Limited core passed: 100/100 profitable iterations, zero Apex-violating
    iterations; top row n69/net `$14,248.75`/PF `2.238`/MAR `6.207`/
    expectancy `0.240R`, but full benchmark rows still failed the 500-trade
    preference because the local sample is only one year. Limited monkey also
    passed with net-profit/max-drawdown beat rates `97.6%`/`98.8%`.
  - The 14:00 variant failed `walk_forward_analysis` on density, not on
    stitched economics: early_exit false, 8 windows versus required 10,
    stitched OOS n31 versus required 500, net `$11,007.50`, PF `3.275`, MAR
    `8.659`, expectancy `0.391R`, win rate `67.7%`, zero Apex violations, and
    75% profitable OOS windows. The stage halted there and later stages were
    skipped.
- Engine-timing robustness audit:
  - Scratch script:
    `/private/tmp/es_mes_flow_divergence_primary_robustness.py`.
  - Result paths:
    `/private/tmp/es_mes_flow_divergence_primary_robustness_grid.csv`,
    `/private/tmp/es_mes_flow_divergence_primary_robustness_trades.csv`, and
    `/private/tmp/es_mes_flow_divergence_primary_robustness_summary.json`.
  - The audit used the same 13:59 completed-bar signal, 14:00 entry, 15:31
    flatten convention, 1-tick entry/exit slippage, and `$2.50` commission per
    side as the staged engine. The exact primary row reproduced the staged
    core-grid metrics: n50/net `$11,437.50`/PF `2.4659`/average `0.195R`/max
    drawdown `$2,275`, with 44 flat exits, 5 target exits, and 1 stop.
  - The exact row remained cost-tolerant and not month-singleton-driven: +`$25`
    round-turn stress PF `2.216`, +`$50` stress PF `1.996`, and worst
    leave-one-month-out PF `2.026` when excluding March 2026. The weakness is
    breadth: positive-month rate was only `58.3%`, so it failed the stricter
    scratch `supportive_shape` flag.
  - Two nearby rows passed that stricter scratch split/month/cost flag:
    threshold `0.20`, stop `0.0025`, target `1.0R`; and threshold `0.175`,
    stop `0.0025`, target `1.0R`. Both had 45-47 trades, positive 2025/Q1/Q2
    PF, `75%` positive months, +`$50` cost-stress PF above `1.83`, and worst
    leave-one-month-out PF above `2.04`.
  - Interpretation: supportive evidence only. The primary branch is not a
    single exact-parameter artifact, but the one-year sample is too short and
    month-concentrated for acceptance.
- ES/MES price-dislocation follow-up:
  - Why tested: this kept the same independent ES/MES linked-market
    mean-reversion thesis but used completed return dislocation rather than
    aggressor-flow imbalance. Hasbrouck-style price-discovery literature is the
    direct support; Kaniel/Saar/Titman and Barber/Odean/Zhu remain indirect
    support for smaller-participant pressure.
  - Builder support added `es_minus_mes_return_ticks_*` and
    `mes_minus_es_return_ticks_*` columns to
    `src/propstack/data/es_mes_flow_divergence.py`, with focused coverage in
    `tests/test_es_mes_flow_divergence.py`.
  - Rebuilt separate cache:
    `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`.
  - Scratch screen paths:
    `/private/tmp/es_mes_price_dislocation_reversion_screen_all.csv` and
    `/private/tmp/es_mes_price_dislocation_reversion_screen_top.csv`.
  - Best flat row before staging was two-sided 3-minute MES-minus-ES return
    spread fade, enter 11:00 and exit 14:30, threshold 1 tick: n132, net
    `$40,065`, PF `1.777`, average `$303.52`, train PF `2.101`, 2026-Q1 PF
    `1.621`, and 2026-Q2 PF `1.347`.
  - Added staged config:
    `configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/midday_es_mes_price_dislocation_fade.yaml`.
    Command:
    `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/midday_es_mes_price_dislocation_fade.yaml --skip-validation`.
    Result path:
    `data/reports/campaigns/mes_es_flow_divergence_reversion/ES/es_mes_price_flow_divergence_1m_20250610_20260608/1m/midday_es_mes_price_dislocation_fade/campaign_tests`.
  - Promotion decision: rejected at `limited_core_grid_test`. The run tested
    100 combinations, had 40 profitable iterations (`40%`) versus the required
    `70%`, and had zero Apex-violating iterations. Top rows were attractive but
    too neighborhood-fragile; best row used threshold `0.75` or `1.0`,
    `stop_pct=0.008`, `target_r=1.5`, n132/net `$42,258.75`/PF `1.829`/MAR
    `6.231`/expectancy `0.122R`, failing the full benchmark only on the
    500-trade preference but failing the staged stability gate on the broader
    grid.
  - Do not promote or rerun simple ES/MES completed-return-spread fade,
    MES-rich short, MES-cheap long, or short-window ES/MES price-dislocation
    reversion unless longer 2020-start ES+MES `trades` history first confirms
    the primary 14:00 flow-divergence branch.
- Data/cost gate:
  - Databento metadata cost only, no new trade files downloaded.
  - ES `trades` 2011-01-03 through 2026-06-09 sampled estimate:
    `$1,381` by sample average / `$1,473` by nonzero-day average.
  - MES `trades` did not resolve before 2020 in Databento metadata, so this
    branch cannot support the same 2011-start default WFA history as ES-only
    campaigns.
  - ES+MES `trades` 2020-01-01 through 2026-06-09 sampled estimate:
    ES about `$624` / `$832`; MES about `$424` / `$565`; combined about
    `$1.05k` / `$1.40k`.
  - Fresh dry-run sample estimate on 2026-06-14, using 24 sampled sessions and
    no paid timeseries download, estimated 2020-01-01 through 2026-06-09 at
    `$554.49` for ES plus `$394.85` for MES, combined `$949.34`. Manifests:
    `/private/tmp/databento_es_trades_2020_2026_cost_only_manifest.json` and
    `/private/tmp/databento_mes_trades_2020_2026_cost_only_manifest.json`.
- Predeclared longer-history validation gate, if the paid ES+MES history is
  approved:
  - Download/ingest ES.FUT and MES.FUT `trades` from 2020-01-01 through
    2026-06-09, RTH 09:30-16:00 ET, `GLBX.MDP3`, `stype_in=parent`.
  - Build monthly trade-orderflow caches for ES and MES with
    `propstack.build_trade_orderflow_cache`, then build the merged ES/MES
    divergence cache with `propstack.build_es_mes_flow_divergence_cache`.
  - Rerun `afternoon_mes_large20_buy_pressure_short` first on the 2020-start
    merged cache; keep `morning_mes_sell_pressure_divergence_long` secondary
    because it already failed limited-core parameter stability on the one-year
    sample.
  - Do not mark the branch live eligible unless the 2020-start staged protocol
    is explicitly defined before download, approved before promotion, and passed
    without weakening acceptance gates after seeing the longer-history data.
- Promotion decision: retain as the best current independent mean-reversion
  lead that uses existing non-depth data, but do not mark accepted. The 14:00
  MES large-20 buy-pressure short is now the preferred rerun because it passed
  limited core and monkey before failing WFA density. It needs longer ES+MES
  trade-side history and a predeclared validation protocol appropriate for
  MES's 2020-start history before any live-eligible campaign claim. If longer
  trades are approved, rerun the 14:00 staged config first; keep the 10:00
  divergence long as a secondary branch because it failed limited-core
  parameter-neighborhood stability on the current sample.

## ES Overnight-Return Morning Reversal Follow-up

- Status: rejected before staged implementation.
- Thesis tested: fade a large completed overnight ES move after a same-morning
  RTH reversal confirmation, using only no-lookahead overnight return and
  completed first-5/first-15/first-60-minute RTH confirmation windows. This is
  a mean-reversion expression of overnight/index-futures predictability, but it
  overlaps prior RTH gap-fade, overnight-inventory, and overnight-return
  campaign families.
- Scratch result paths:
  `/private/tmp/es_overnight_return_morning_reversal_flat_no_lookahead_all.csv`
  and
  `/private/tmp/es_overnight_return_morning_reversal_flat_no_lookahead_top.csv`.
- Gate audit over 34,045 rows:
  - zero rows with `wfa_n >= 500`, `wfa_pf >= 1.5`, and `wfa_mar >= 0.5`;
  - zero rows with `wfa_n >= 500`, `wfa_pf >= 1.4`, `core_n >= 75`,
    `incubation_n >= 75`, `core_pf >= 1.2`, and `incubation_pf >= 1.2`;
  - zero rows with `wfa_n >= 300`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`;
  - zero rows with enough early/core/WFA/incubation density and PF >= 1.2
    across the main splits.
- Best score row was 10:30 -> 11:30 after at least 50 overnight ticks with
  first-15-minute reversal confirmation of 20 ticks: early n13/PF 1.161, WFA
  n242/PF 1.418/MAR 0.332, core n80/PF 1.284/MAR 0.495, incubation n82/PF
  1.542/MAR 2.137, and full n337/PF 1.446/MAR 0.332. It is economically
  interesting but far below WFA density and MAR.
- Dense rows diluted badly. The best `wfa_n >= 500` rows had WFA PF only around
  1.14-1.22 and several had weak or negative core behavior.
- Promotion decision: do not stage this branch. It is not strong enough as a
  standalone ES mean-reversion campaign and is too close to already rejected
  gap/overnight-reversal families without a materially new source filter.

## ES Macro-Sentiment State Follow-ups

### Economic Policy Uncertainty

- Status: rejected before staged implementation.
- Source/data:
  - Baker, Bloom, and Davis, "Measuring Economic Policy Uncertainty",
    Quarterly Journal of Economics 131(4), DOI `10.1093/qje/qjw024`.
  - Official daily news-based EPU CSV:
    `https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv`.
  - Raw cache: `/private/tmp/epu_all_daily_policy_data.csv`, covering
    1985-01-01 through 2026-06-12.
- No-lookahead handling: each ES session used only the latest EPU value known
  by the prior business-day cutoff. The screen built level, 5-day mean, daily
  and multi-day changes, rolling ranks, and rolling z-scores.
- Scratch result paths:
  `/private/tmp/epu_policy_uncertainty_es_screen_all.csv` and
  `/private/tmp/epu_policy_uncertainty_es_screen_top.csv`.
- Gate audit over 1,801 positive/interested rows:
  - zero pass-like rows with WFA/core/incubation/early density and PF gates;
  - zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`;
  - zero rows with `wfa_n >= 500`, `wfa_pf >= 1.4`,
    `incubation_n >= 75`, and `incubation_pf >= 1.2`;
  - zero rows with `wfa_n >= 300`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- High-PF rows were sparse and often failed incubation. Dense rows diluted:
  best `wfa_n >= 500` examples reached only WFA PF about 1.10-1.12. The
  highest-scoring dense row, `epu_chg5_z63 >= 0.5`, long 11:00 -> 15:30, had
  WFA n585/PF 1.120/MAR 0.793, core n136/PF 0.945, incubation n83/PF 1.706.
- Promotion decision: do not stage. Daily policy-uncertainty state is
  point-in-time plausible with the conservative lag, but it does not clear WFA
  PF/MAR or core consistency.

### Michigan Consumer Sentiment

- Status: rejected before staged implementation.
- Source/data:
  - Lemmon and Portniaguina, "Consumer Confidence and Asset Prices: Some
    Empirical Evidence", Review of Financial Studies 19(4), DOI
    `10.1093/rfs/hhj038`.
  - FRED CSV for University of Michigan Consumer Sentiment:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=UMCSENT`.
  - Raw cache: `/private/tmp/umcsent_fred.csv`, 672 non-null monthly rows.
- No-lookahead handling: each monthly observation was made tradable only after
  a conservative 45-calendar-day lag. The screen built level, 3-month mean,
  1/3/6/12-month changes, percent changes, rolling ranks, and rolling z-scores.
- Scratch result paths:
  `/private/tmp/umich_consumer_sentiment_es_screen_all.csv` and
  `/private/tmp/umich_consumer_sentiment_es_screen_top.csv`.
- Gate audit over 1,166 positive/interested rows:
  - zero pass-like rows with WFA/core/incubation/early density and PF gates;
  - zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`;
  - zero rows with `wfa_n >= 500`, `wfa_pf >= 1.4`,
    `incubation_n >= 75`, and `incubation_pf >= 1.2`;
  - zero rows with `wfa_n >= 300`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best PF rows were sparse or had no core/incubation coverage. The strongest
  dense enough examples were broad low-sentiment longs around 11:00 -> 15:30:
  `umcsent_z60 <= -0.5` had WFA n894/PF 1.100/MAR 1.822, core n458/PF
  1.038, and incubation n285/PF 1.110.
- Promotion decision: do not stage. Consumer sentiment state is an independent
  academic macro-sentiment branch, but in ES intraday form it is too weak after
  costs and conservative release lag.

### SLOOS C&I Credit-Supply Re-Audit

- Status: rejected before staged implementation as a narrow re-audit of the
  already rejected SLOOS credit-conditions family, not a new source family.
- Source/data:
  - Federal Reserve Senior Loan Officer Opinion Survey C&I tightening and demand
    series via FRED (`DRTSCILM`, `DRTSCIS`, `DRSDCILM`, `DRSDCIS`, and
    `DRTSCLCC`).
  - Credit-cycle/loan-officer-survey academic motivation follows the Lown and
    Morgan SLOOS credit-cycle literature.
  - Conservative availability: each quarterly observation was made tradable only
    after a 45-calendar-day lag.
- Scratch result paths:
  `/private/tmp/sloos_credit_supply_es_screen_all.csv`,
  `/private/tmp/sloos_credit_supply_es_screen_top.csv`,
  `/private/tmp/sloos_credit_supply_path_screen_fast.csv`, and
  `/private/tmp/sloos_credit_supply_path_screen_fast_top.csv`.
- Flat screen summary: 29,077 positive/interested rows; zero pass-like rows.
  Strongest practical cluster was C&I tightening after a prior-down ES session,
  long 11:00 -> 15:30. Example: `ci_tight_avg >= 0`, prior-down long
  11:00 -> 15:30, early n28/PF 1.319, WFA n558/PF 1.465/MAR 10.727, core
  n86/PF 1.371/MAR 2.180, incubation n150/PF 1.331/MAR 2.457, full n736/PF
  1.413/MAR 8.187. It missed the WFA PF gate and early density.
- Focused stop/target path audit summary: 392 rows; zero pass-like rows, zero
  rows with WFA n >= 500/PF >= 1.5 plus incubation PF >= 1.2, and only one
  loose WFA n >= 300/PF >= 1.4 plus incubation n >= 50/PF >= 1.2 row.
  Path management improved the C&I tightening row's WFA PF to 1.520 at
  `stop_pct=0.010`/`target_r=1.25`, but incubation fell to PF 1.136/MAR 0.933
  with expectancy R 0.033, so the improvement was not tradable.
- Promotion decision: do not stage. This confirms the prior broad SLOOS rejection
  rather than reopening it; do not rerun simple bank-lending-standards,
  C&I-tightening, or credit-supply quarterly state screens without materially new
  structure.

## ES EMV News-Volatility State Follow-up

- Status: rejected before staged implementation.
- Source/data:
  - Baker, Bloom, Davis, and Kost, "Policy News and Stock Market Volatility",
    NBER Working Paper 25720, DOI `10.3386/w25720`.
  - Official EMV workbook:
    `https://www.policyuncertainty.com/media/EMV_Data.xlsx`.
- No-lookahead handling: the monthly EMV observation was made tradable only after
  a conservative 45-calendar-day lag from the month label. The screen used the
  official monthly overall, policy, macro, labor, inflation, rates, regulation,
  trade, petroleum, commodity, financial-crisis, and related category trackers.
- Scratch result paths:
  `/private/tmp/emv_news_volatility_features.csv`,
  `/private/tmp/emv_news_volatility_es_screen_all.csv`, and
  `/private/tmp/emv_news_volatility_es_screen_top.csv`.
- Gate audit over 352 derived features and 8,543 positive/interested rows:
  - zero pass-like rows with WFA/core/incubation/early density and PF gates;
  - zero rows with `wfa_n >= 500`, `wfa_pf >= 1.5`, and `wfa_mar >= 0.5`;
  - zero rows with `wfa_n >= 500`, `wfa_pf >= 1.4`,
    `incubation_n >= 75`, and `incubation_pf >= 1.2`;
  - four loose rows with `wfa_n >= 300`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`, none with enough WFA
    density and early/core/incubation shape together.
- Best high-PF row was too sparse and early-history weak: `regulation_mean3`
  high, prior-down long 11:00 -> 15:30 had early n90/PF 0.771, WFA n255/PF
  1.614/MAR 7.458, core n103/PF 1.517, incubation n154/PF 1.425/MAR 4.720,
  and full n499/PF 1.451. The WFA sample is far below 500 and early PF is
  negative.
- Dense rows diluted to weak WFA economics. For example, `policy_pct6 >= -0.1`
  after prior-down ES, long 13:30 -> 15:30, had WFA n673/PF 1.247/MAR 2.004,
  core n120/PF 1.369, and incubation n111/PF 1.491.
- Promotion decision: do not stage. EMV is a clean independent academic
  macro-news-volatility source, but its monthly news-volatility state does not
  produce a robust ES intraday mean-reversion candidate after costs and
  conservative release lag.

## ES Daily News-Risk Ensemble Follow-up

- Status: rejected before staged implementation.
- Source/data:
  - San Francisco Fed Daily News Sentiment Index workbook, motivated by
    Shapiro, Sudhof, and Wilson, "Measuring News Sentiment," and the Buckman,
    Shapiro, Sudhof, and Wilson COVID news-sentiment update.
  - Caldara and Iacoviello daily Geopolitical Risk data, motivated by
    "Measuring Geopolitical Risk," American Economic Review 112(4), DOI
    `10.1257/aer.20191823`.
  - Local source caches:
    `/private/tmp/sf_fed_daily_news_sentiment.xlsx` and
    `/private/tmp/data_gpr_daily_recent.xls`.
- No-lookahead handling: both daily source series were shifted so an ES session
  could use only source dates strictly before that session. Features included
  daily levels, changes, rolling means, rolling ranks, and rolling z-scores for
  news sentiment, GPR level, GPR threat, GPR acts, and article counts.
- Scratch result paths:
  `/private/tmp/news_risk_ensemble_features.csv`,
  `/private/tmp/news_risk_ensemble_es_screen_all.csv`,
  `/private/tmp/news_risk_ensemble_es_screen_top.csv`,
  `/private/tmp/news_risk_ensemble_path_screen_all.csv`, and
  `/private/tmp/news_risk_ensemble_path_screen_top.csv`.
- Flat-hold screen summary: 1,456 bounded rows over news-only, GPR-only,
  source-diverse AND, score, and priority conditions; 197 positive/interested
  rows; zero pass-like rows; zero dense near rows; seven loose near rows. There
  were zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`, one row with
  `wfa_n >= 500` and `wfa_pf >= 1.4`, and four rows with `wfa_n >= 300`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best flat dense row was a source-priority low-sentiment-or-high-GPR long:
  `priority_sent10_or_n10d90`, no filter, long 09:35 -> 15:59, with early
  n112/PF 0.823, WFA n513/PF 1.443/MAR 0.659, core n98/PF 1.639, incubation
  n64/PF 1.594/MAR 2.024, and full n689/PF 1.411. It missed WFA PF and
  incubation density. The higher-WFA-PF priority row
  `priority_sent15_or_gpractdrop`, prior-down long 09:35 -> 15:59, had WFA
  n385/PF 1.521 but missed WFA density, incubation density, and early PF.
- Focused stop-first path-management audit over the seven loose near rows plus
  the strongest sparse source-diverse AND rows evaluated 756 rows across
  `stop_pct` and fixed-R targets. It again found zero pass-like rows and zero
  dense near rows. The best path row,
  `priority_sent15_or_gpractdrop`, prior-down long 09:35 -> 15:59 with
  `stop_pct=0.010` and `target_r=4.0`, had early n127/PF 0.698, WFA
  n385/PF 1.468/MAR 0.561, core n77/PF 1.486, incubation n52/PF 1.850/MAR
  1.775, and full n564/PF 1.435. Path management did not solve WFA density,
  WFA PF, early-history weakness, or incubation density together.
- Source-diverse AND rows were too sparse. The strongest WFA PF path examples
  reached about WFA PF 1.89 but only around 112 WFA trades and failed
  incubation PF or density.
- Promotion decision: do not stage. Combining daily news sentiment with daily
  geopolitical risk keeps the independent public-news thesis, but the edge is
  still the same low-news-sentiment contrarian ES long cluster and does not
  satisfy WFA PF/density, early-history, and incubation coverage together. Do
  not rerun simple low-news-sentiment/high-GPR priority, AND, or score
  ensembles without a materially new source structure or a distinct execution
  signal.

## ES Daily RRP Liquidity-State Data-Gate Follow-up

- Status: rejected at the data-access gate before ES screening.
- Why tested: the ledger's prior H.4.1 liquidity-state audit noted that the
  official daily RRP series was not included because the FRED endpoint timed
  out. Daily RRP would be a materially different, higher-frequency liquidity
  state than the already rejected weekly H.4.1 reserves/TGA balance-sheet
  variables.
- Source/data attempted:
  - FRED series page for `RRPONTSYD`, Overnight Reverse Repurchase Agreements:
    Treasury Securities Sold by the Federal Reserve in Temporary Open Market
    Operations (`https://fred.stlouisfed.org/series/RRPONTSYD`).
  - NY Fed Markets API-style reverse-repo and rates endpoints under
    `https://markets.newyorkfed.org/api/`.
- Metadata result:
  - The FRED series page was reachable and confirmed daily observations from
    2003-02-07 through 2026-06-12, latest displayed value `0.454` billion
    dollars on 2026-06-12, updated 2026-06-12 1:04 PM CDT, with next release
    date 2026-06-15.
  - Local metadata cache: `/private/tmp/fred_RRPONTSYD_meta.txt`.
- Historical-download result:
  - FRED bulk CSV routes timed out or failed with zero bytes:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=RRPONTSYD`,
    the same URL with explicit observation bounds,
    `https://alfred.stlouisfed.org/graph/fredgraph.csv?id=RRPONTSYD`, and
    `https://fred.stlouisfed.org/data/RRPONTSYD`.
  - The no-key FRED observations API probe did not yield data from this
    environment.
  - NY Fed Markets API probes for reverse-repo propositions/results and a known
    rates endpoint returned a generic `www.newyorkfed.org/errors/500` HTML page
    instead of JSON, including recent narrow date ranges.
- Promotion decision: no ES screen was run. Do not reopen daily RRP liquidity
  state, RRP-drain/risk-appetite, or RRP-liquidity-release ES timing unless a
  reliable historical observation path is added, such as a working FRED API key,
  a working NY Fed Markets API route from this environment, or an approved
  official archive.

## ES CP Funding-State Opening Reversal Follow-up

- Status: rejected before staged implementation.
- Why tested: this was a materially different execution structure from the
  prior simple commercial-paper funding-stress flat hold. It kept the official
  high commercial-paper issuance-count state, but only traded ES long after a
  completed same-session RTH selloff from the open and optional reclaim from
  the source-window low.
- Source/data:
  - Official Federal Reserve Commercial Paper Rates and Outstanding Summary
    package:
    `https://www.federalreserve.gov/datadownload/Output.aspx?rel=CP&filetype=zip`.
  - Parsed target series `MKT.10_20.MKT.VOL`, the number of total-market
    10-20-day commercial-paper issues, matching the prior CP near-miss source.
  - Active ES RTH 1-minute panel rebuilt from local Databento monthly OHLCV
    cache and explicit ES roll calendar into
    `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`: 1,502,288 rows
    across 3,913 sessions from 2010-06-07 through 2026-05-29 after dropping
    sessions adjacent to roll changes.
- No-lookahead handling: because the Fed CP data are generally released around
  1:00 p.m. ET with a one-day lag, morning entries used a two-business-day CP
  eligibility lag. Post-13:00 entries used a one-business-day post-release lag.
- Screen mechanics: CP rank63 thresholds `0.65/0.70/0.75/0.80`, completed
  RTH-open-to-entry weakness filters from -4 to -32 ticks, reclaim-from-low
  filters from 0 to 16 ticks, morning entries at 10:00/10:30/11:00, post-release
  entries at 13:30/14:00/14:30, 15:30/15:59 exits, and flat or stop-first
  managed exits with `stop_pct` 0.006-0.018 and fixed-R targets 1/2/4.
- Scratch result paths:
  `/private/tmp/cp_opening_reversal_state_screen_all.csv`,
  `/private/tmp/cp_opening_reversal_state_screen_top.csv`, and
  `/private/tmp/cp_opening_reversal_state_screen_top_trades.csv`.
- Result summary: 578,994 no-lookahead trade outcomes across 3,773 ES sessions,
  18,720 screened rows, zero pass-like rows, zero near-like rows, zero rows with
  `wfa_n >= 500` and `wfa_pf >= 1.4`, and zero rows with
  `wfa_n >= 300`, `wfa_pf >= 1.4`, `incubation_n >= 50`, and
  `incubation_pf >= 1.2`. Maximum WFA density after the opening-weakness filter
  was only 390 trades.
- Best high-PF rows were sparse artifacts. The top-ranked row was morning
  two-business-day-lag CP rank63 >= 0.80, 10:00 -> 15:30, -32-tick opening
  weakness, 12-tick reclaim, `stop_pct=0.006`, `target_r=4.0`: full n57/PF
  2.10, WFA n44/PF 2.13/MAR 0.473, core n23/PF 2.89, incubation n11/PF 1.91,
  and early n2.
- Dense rows were weak. The most WFA-dense practical row was 11:00 -> 15:30
  with CP rank63 >= 0.65 and -4-tick opening weakness: full n579/PF 1.08, WFA
  n390/PF 1.02/MAR 0.018, core n106/PF 1.10, incubation n57/PF 1.40, and early
  n127/PF 0.90. Post-release rows were also weak; the best post-release row
  by score had WFA n360/PF about 1.01 and incubation PF below 0.90.
- Promotion decision: do not stage. Adding a true opening-reversal trigger to
  the CP funding-state near-miss removes the WFA/incubation density and does not
  improve robustness. Do not rerun high CP issuance-count plus same-session
  opening weakness/reclaim fade, morning two-business-day CP lag, or
  post-release one-business-day CP lag variants without a materially different
  source variable or execution structure.

## ES Shiller CAPE Valuation-State Screen

- Status: rejected before staged implementation.
- Why tested: this is a genuinely different slow-moving valuation/mean-reversion
  thesis, not an intraday price/orderflow continuation branch. Academic support
  comes from Campbell-Shiller valuation-ratio return-predictability work and
  Shiller's CAPE/Irrational Exuberance data framework.
- Source/data:
  - Official Shiller data page: `https://shillerdata.com/`.
  - Exact linked workbook downloaded from the page:
    `https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/c9b8cf0f-f01a-49f5-9ea5-d19443390ab2/ie_data.xls?ver=1780495520681`.
  - Local workbook cache:
    `/private/tmp/shiller_ie_data_current_linked.xls`.
  - Parsed monthly feature cache:
    `/private/tmp/shiller_cape_features.csv`.
- Coverage/no-lookahead handling: workbook covered monthly rows from 1871-01
  through 2026-06. ES testing used only values made eligible after month-end
  plus 15 calendar days, then forward-filled to later ES sessions.
- Screen mechanics: bounded flat-hold ES RTH screen over CAPE, total-return
  CAPE, excess CAPE yield, dividend yield, earnings yield, real earnings yield,
  real dividend yield, and 10-year yield fields. Features included levels,
  one-month changes, 12-month changes, and 60/120/240-month rolling ranks and
  z-scores. Tested long/short entries at 09:35/10:30/11:00/13:30 and exits at
  12:00/15:30/15:59 with current ES round-turn costs.
- Scratch result paths:
  `/private/tmp/shiller_cape_valuation_es_screen_all.csv` and
  `/private/tmp/shiller_cape_valuation_es_screen_top.csv`.
- Result summary: 82,500 no-lookahead trade outcomes across 3,773 ES sessions,
  7,106 screened rows, zero pass-like rows, zero near-like rows, zero rows with
  `wfa_n >= 500` and `wfa_pf >= 1.5`, zero rows with `wfa_n >= 500` and
  `wfa_pf >= 1.4`, and zero rows with `wfa_n >= 500`, `wfa_pf >= 1.35`,
  `incubation_n >= 75`, and `incubation_pf >= 1.2`.
- High-PF rows were sparse valuation-regime slices. For example, high
  120-month earnings-yield z-score longs at 13:30 -> 15:59 had WFA n17/PF
  2.82 and incubation n22/PF 4.74, but early n541/PF 0.76 and far too little
  WFA/core density.
- Dense rows were weak. The best WFA-density rows were improving valuation
  measures, but still around WFA PF 1.20-1.23 and missing incubation coverage.
  For example, 12-month dividend-yield increase, long 13:30 -> 15:30, had full
  n735/PF 1.17, WFA n515/PF 1.23/MAR 0.497, core n130/PF 1.35, incubation n0,
  and early n220/PF 0.79. Rows with positive 2025-2026 incubation, such as
  rising one-month earnings yield, had incubation PF around 1.6-1.75 but WFA PF
  only about 1.08-1.11 and weak early history.
- Promotion decision: do not stage. Shiller valuation state is academically
  clean and independent, but it is too slow-moving and weak in same-day ES RTH
  execution after costs. Do not rerun simple CAPE, total-return CAPE, excess
  CAPE yield, dividend yield, earnings yield, real-earnings yield, or Shiller
  valuation rank/z-score variants without materially different timing or source
  structure.

## ES French Industry Dispersion/Breadth Screen

- Status: rejected before staged implementation.
- Why tested: this was a distinct daily cross-sectional market-state thesis,
  separate from ES/NQ trend following and from prior sector-ETF leader/laggard
  rotation. It used aggregate industry participation, dispersion, and tail
  breadth as a prior-day equity-market stress/participation state for same-day
  ES RTH trades.
- Source/data: Kenneth French 49 industry daily value-weighted returns,
  downloaded from
  `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_daily_CSV.zip`.
  The source file identified itself as created from the 202604 CRSP database;
  parsed industry dates covered 2009-01-02 through 2026-04-30.
- No-lookahead handling: each industry observation was shifted to the next
  business day before becoming eligible for an ES session. The ES test used the
  active RTH 1-minute cache at
  `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Screen mechanics: built prior-day industry features including mean/median
  industry return, dispersion, IQR, range, upside/downside breadth, 1% tail
  breadth, tail spread, cross-sectional skew, rolling means, rolling changes,
  ranks, and z-scores. Tested long/short ES flat holds at 09:35/10:30/11:00/13:30
  entries and 12:00/15:30/15:59 exits.
- Scratch result paths:
  `/private/tmp/french_industry_dispersion_breadth_features.csv`,
  `/private/tmp/french_industry_dispersion_breadth_es_screen_all.csv`, and
  `/private/tmp/french_industry_dispersion_breadth_es_screen_top.csv`.
- Result summary: 82,500 no-lookahead ES outcomes across 3,773 sessions and
  11,396 screened rows. The screen found zero pass-like rows, zero near-like
  rows, zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`, zero rows with
  `wfa_n >= 500` and `wfa_pf >= 1.4`, and zero rows with `wfa_n >= 400`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Dense WFA rows were too weak. The best WFA-density row by PF was low
  `tail_spread_rank126`, short 09:35 -> 12:00, with full n785/PF 1.14, WFA
  n525/PF 1.29/MAR 0.33, core n108/PF 1.58, but incubation n48/PF 0.78 and
  early n204/PF 0.78. High-dispersion long rows had better 2025-2026 incubation
  but WFA PF stayed around 1.21-1.25 and early history remained weak.
- Promotion decision: do not stage. The French industry dispersion/breadth
  source is independent and academically plausible, but the ES translation is
  an incubation-skewed market-state pocket rather than a robust WFA candidate.
  Do not rerun simple industry dispersion, breadth, tail-spread, or industry
  cross-sectional rank/z-score variants without materially different timing,
  execution, or source structure.

## ES Treasury-Curve Risk-State Screen

- Status: rejected before staged implementation.
- Why tested: this was a public macro/risk-appetite state, distinct from
  price/orderflow continuation, NQ, or sector/industry breadth. The thesis was
  that completed Treasury-yield and curve shocks can proxy for flight-to-quality
  or changing stock-bond covariance regimes, then condition short-horizon ES
  mean-reversion/risk-on exposure.
- Academic backing:
  - Baele, Bekaert, Inghelbrecht, and Wei, "Flights to Safety," Review of
    Financial Studies 33(2), DOI `10.1093/rfs/hhz055`.
  - Campbell, Sunderam, and Viceira, "Inflation Bets or Deflation Hedges? The
    Changing Risks of Nominal Bonds," Critical Finance Review 6.
- Source/data: Federal Reserve H.15 Data Download Program Treasury constant
  maturity package:
  `https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&series=bf17364827e38702b42a58cf8eaa3f78&lastobs=&from=&to=&filetype=csv&label=include&layout=seriescolumn&type=package`.
  Local cache: `/private/tmp/frb_h15_treasury_curve.csv`.
- Coverage/no-lookahead handling: parsed daily H.15 Treasury yields from
  2009-01-01 through 2026-06-11. Each daily observation was made eligible only
  for the next business-day ES session. ES testing used
  `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Screen mechanics: built 3-month, 2-year, 5-year, 10-year, and 30-year yield
  levels; one-day and five-day changes; 10y-2y, 10y-3m, 30y-5y, and 2s5s10s
  belly terms; parallel and curve shocks; and rolling 21/63/126/252-day ranks
  and z-scores. Tested long/short ES flat holds at 09:35/10:30/11:00/13:30
  entries and 12:00/15:30/15:59 exits.
- Flat result paths:
  `/private/tmp/frb_h15_treasury_curve_features.csv`,
  `/private/tmp/frb_h15_treasury_curve_es_screen_all.csv`, and
  `/private/tmp/frb_h15_treasury_curve_es_screen_top.csv`.
- Flat result summary: 83,314 no-lookahead ES outcomes across 3,787 sessions,
  272 valid features, 2,298 threshold specs, and 14,329 retained diagnostic rows.
  The screen found zero pass-like rows, zero near-like rows, zero rows with
  `wfa_n >= 500` and `wfa_pf >= 1.5`, zero rows with `wfa_n >= 500` and
  `wfa_pf >= 1.4`, and zero rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
  `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best practical flat cluster was long ES after a prior 3-month yield drop of at
  least 1 bp. The broad 09:35 -> 15:59 flat row had full n738/PF 1.37, WFA
  n578/PF 1.29/MAR 4.32/expectancy 0.134, core n82/PF 1.57, incubation
  n75/PF 2.05, but early n85/PF 0.82. Other rows had the same pattern: strong
  2025-2026 incubation, but sub-gate WFA PF and weak early history.
- Focused path audit: because the 3-month yield-drop cluster had enough density,
  a narrow stop-first path screen tested the flat-screen leaders with long-only
  entries at 09:35/10:30/11:00, flat times 15:30/15:59, stops from 0.25% to
  1.00%, and fixed-R targets from 1R to 4R. Scratch paths:
  `/private/tmp/frb_h15_treasury_curve_path_screen_all.csv` and
  `/private/tmp/frb_h15_treasury_curve_path_screen_top.csv`.
- Path result summary: 750 managed rows, zero pass-like rows, zero near-like rows,
  zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`, zero rows with
  `wfa_n >= 500` and `wfa_pf >= 1.4`, zero rows with `wfa_n >= 400`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`, and zero
  rows with early n >= 75, early PF >= 1.0, WFA n >= 500, WFA PF >= 1.3,
  incubation n >= 75, and incubation PF >= 1.2.
- Best managed 3-month-yield-drop row was 10:30 entry, 15:59 flat,
  `stop_pct=0.0100`, `target_r=4.0`: full n852/PF 1.31, WFA n626/PF 1.24/MAR
  3.84/expectancy 0.115, core n101/PF 1.49, incubation n75/PF 2.04, and early
  n151/PF 0.97. That is a useful diagnostic but not a staged candidate.
- Promotion decision: do not stage. Treasury-curve risk state is independent and
  academically clean, but the ES execution is incubation-skewed and does not
  clear WFA PF or early-history gates. Do not rerun simple H.15 Treasury yield
  level, curve slope, curve-change, rank, or z-score variants without materially
  different timing, source structure, or an explicit event-based rate-shock
  design.

## ES Chicago Fed NFCI Financial-Conditions Screen

- Status: rejected before staged implementation.
- Why tested: this was a public weekly financial-conditions/liquidity-state
  thesis, distinct from price/orderflow continuation, NQ, H.15 Treasury-yield
  shocks, and sector/industry breadth. The mean-reversion idea was to buy ES
  after prior-session weakness when Chicago Fed credit/financial conditions are
  not tightening aggressively, on the premise that intermediary balance-sheet
  and credit conditions can affect short-horizon risk-taking capacity.
- Academic/source backing:
  - Chicago Fed NFCI/ANFCI framework: the NFCI summarizes 105 weekly financial
    indicators across money markets, debt/equity markets, and traditional and
    shadow banking; ANFCI adjusts for economic activity and inflation.
  - Brave and Kelley, "Introducing the Chicago Fed's New Adjusted National
    Financial Conditions Index," Chicago Fed Letter No. 386.
  - Adrian, Etula, and Muir, "Financial Intermediaries and the Cross-Section of
    Asset Returns," Journal of Finance 69(6), motivates intermediary-state
    variables as asset-pricing/risk-bearing state variables.
- Source/data:
  - Chicago Fed current NFCI page:
    `https://www.chicagofed.org/research/data/nfci/current-data`.
  - Chicago Fed dynamic data endpoint:
    `https://data.chicagofed.org/cfed-drm-chicago/NFCI`.
  - Official CSV used:
    `https://api.data.chicagofed.org/NFCI/nfci-data-series-csv.csv`.
  - Local cache: `/private/tmp/chicagofed_nfci_data_series.csv`.
- Coverage/no-lookahead handling: parsed weekly Friday observations from
  2009-01-02 through 2026-06-05. Because the index is normally published the
  following Wednesday at 08:30 ET, or Thursday around holidays, each Friday
  observation was made tradable only from the following Friday ES session, then
  forward-filled until the next eligible observation.
- Screen mechanics: built NFCI, ANFCI, Risk, Credit, Leverage, and
  Nonfinancial_Leverage levels; one-week and four-week changes; four-week
  means; risk-credit, risk-leverage, ANFCI-NFCI, broad tightening, and broad
  easing scores; and rolling 13/26/52/104-week ranks and z-scores. Tested
  long/short ES flat holds at 09:35/10:30/11:00/13:30 entries and
  12:00/15:30/15:59 exits, with optional prior-ES-up/down filters.
- Flat result paths:
  `/private/tmp/chicagofed_nfci_features.csv`,
  `/private/tmp/chicagofed_nfci_es_screen_all.csv`, and
  `/private/tmp/chicagofed_nfci_es_screen_top.csv`.
- Flat result summary: 83,226 no-lookahead ES outcomes across 3,783 sessions,
  263 valid features, 6,228 threshold/filter specs, and 46,516 retained
  diagnostic rows. The screen found zero pass-like rows and 14 near-like rows;
  zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`; 27 rows with
  `wfa_n >= 500` and `wfa_pf >= 1.4`; and 28 rows with `wfa_n >= 400`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best flat row was `credit_chg1_rank52 <= 0.70` with prior ES down day, long
  11:00 -> 15:59: full n960/PF 1.44, WFA n666/PF 1.45/MAR
  7.75/expectancy 0.190, core n94/PF 1.38, incubation n77/PF 1.54/MAR 2.36,
  and early n217/PF 1.25. It missed the WFA PF 1.5 hard gate.
- Focused path audit: tested the 14 flat near-like rows' nine unique conditions
  with stop-first long-only management, entries 10:30/11:00/13:30, flat times
  15:30/15:59, stops 0.25%-1.50%, and 1R-6R targets. Scratch paths:
  `/private/tmp/chicagofed_nfci_path_screen_all.csv` and
  `/private/tmp/chicagofed_nfci_path_screen_top.csv`.
- Path result summary: 1,944 managed rows, zero pass-like rows, 140 near-like
  rows, zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`, 184 rows with
  `wfa_n >= 500` and `wfa_pf >= 1.4`, and 107 rows with `wfa_n >= 400`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best managed row stayed below the hard WFA PF gate: `credit_chg1_rank52 <=
  0.70`, prior ES down day, long 11:00 -> 15:30, `stop_pct=0.0100`,
  `target_r=1.5`: full n957/PF 1.41, WFA n664/PF 1.46/MAR
  10.32/expectancy 0.192, core n94/PF 1.70, incubation n77/PF 1.38/MAR 2.31,
  and early n216/PF 1.16.
- Promotion decision: do not stage. NFCI credit-condition easing/non-tightening
  after a prior ES down day is one of the cleaner independent mean-reversion
  near-misses found so far, but both flat and managed forms remain below the
  WFA PF 1.5 gate. Do not rerun simple NFCI/ANFCI level, change, subindex,
  rank, or z-score variants without materially different timing, event
  conditioning, or a predeclared risk module.

## ES Chicago Fed CFNAI Real-Activity Screen

- Status: rejected before staged implementation.
- Why tested: this was a public macro real-activity state follow-up after the
  earlier monthly real-activity screen could not fetch CFNAI. The thesis was
  mean-reversion/risk-premium timing from broad economic-activity weakness,
  distinct from ES/NQ trend following, trade-side orderflow continuation, H.15
  Treasury shocks, and NFCI financial-conditions state.
- Academic/source backing: Chicago Fed CFNAI summarizes 85 monthly indicators
  of national activity; the broader academic framing follows macro-factor and
  output-gap return-predictability work such as Cooper and Priestley (2009) and
  macro-condition state-variable literature.
- Source/data: official Chicago Fed CFNAI workbook
  `https://www.chicagofed.org/~/media/publications/cfnai/cfnai-data-series-xlsx.xlsx`,
  cached at `/private/tmp/chicagofed_cfnai_data_series.xlsx`.
- No-lookahead handling: the public workbook is a current-history file rather
  than a vintage matrix, so the screen used a deliberately conservative
  month-end plus 45-calendar-day eligibility lag. Any future pass would still
  require a point-in-time CFNAI release/vintage audit before promotion.
- Screen mechanics: parsed monthly rows from 1967-03 through 2026-04 and built
  227 usable features from CFNAI, CFNAI-MA3, diffusion, and component indexes
  including level, one-/three-/six-month changes, three-/six-month means, and
  12/24/60/120-month ranks and z-scores. Tested long/short ES flat holds at
  09:35/10:30/11:00/13:30 entries and 12:00/15:30/15:59 exits, with optional
  prior-ES-up/down filters.
- Flat result paths:
  `/private/tmp/chicagofed_cfnai_features.csv`,
  `/private/tmp/chicagofed_cfnai_es_screen_all.csv`, and
  `/private/tmp/chicagofed_cfnai_es_screen_top.csv`.
- Flat result summary: 83,314 no-lookahead ES outcomes across 3,787 sessions,
  85,403 retained diagnostic rows, zero pass-like rows, and one near-like row.
  Gate counts were zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`, one row
  with `wfa_n >= 500` and `wfa_pf >= 1.4`, five rows with `wfa_n >= 400`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`, and seven
  loose rows with early n >= 75, early PF >= 1.0, WFA n >= 400, WFA PF >= 1.3,
  incubation n >= 50, and incubation PF >= 1.2.
- Best flat row was low 60-month CFNAI rank after a prior ES down day
  (`cfnai_rank60 <= 0.375`), long 11:00 -> 15:59: full n553/PF 1.37/MAR
  0.36/expectancy 0.292, WFA n408/PF 1.41/MAR 0.45/expectancy 0.311, core
  n68/PF 1.62, incubation n80/PF 1.41/MAR 1.98, but early n65/PF 0.68.
- Focused path audit: tested the 10 strongest flat conditions with stop-first
  long-only management, entries 10:30/11:00/13:30, flat times 15:30/15:59,
  stops 0.35%-1.60%, and 0.75R-4R targets. Scratch paths:
  `/private/tmp/chicagofed_cfnai_path_screen_all.csv` and
  `/private/tmp/chicagofed_cfnai_path_screen_top.csv`.
- Path result summary: 2,480 managed rows, zero pass-like rows, one near-like
  row, zero rows with `wfa_n >= 500` and `wfa_pf >= 1.5`, one row with
  `wfa_n >= 500` and `wfa_pf >= 1.4`, one row with `wfa_n >= 400`,
  `wfa_pf >= 1.4`, `incubation_n >= 50`, and `incubation_pf >= 1.2`, and zero
  rows with early n >= 75, early PF >= 1.0, WFA n >= 400, WFA PF >= 1.3,
  incubation n >= 50, and incubation PF >= 1.2.
- Best managed row stayed below the hard WFA PF and early-history gates:
  production/income component weakness (`P_I <= -0.05`) after a prior ES down
  day, long 11:00 -> 15:59, `stop_pct=0.010`, `target_r=1.25`: full n683/PF
  1.29/MAR 0.25, WFA n498/PF 1.41/MAR 0.53/expectancy 0.241, core n75/PF
  2.20, incubation n87/PF 1.21/MAR 0.82, and early n98/PF 0.64.
- Promotion decision: do not stage. CFNAI weakness after a prior ES down day has
  a recognizable contrarian shape, but both flat and managed forms miss WFA PF
  and early-history robustness. Do not rerun simple CFNAI, CFNAI-MA3, diffusion,
  CFNAI component, rank, z-score, or component-change variants without a
  materially different execution structure and point-in-time release
  reconstruction.

Close-out:

- The NQ price-momentum priority candidate is a valid full-stage momentum pass
  and can be tracked as a correlated live-eligible momentum implementation, but
  it is not the next ES campaign to trade.
- The strict third-strategy search is not complete if the requirement is a
  genuinely independent ES economic edge.
- Current ES recommendation: keep quote/depth liquidity sweep as a bounded
  one-year `tbbo` pilot only, but prioritize ES/MES micro-flow divergence as the
  best non-depth mean-reversion validation lead if the longer 2020-start
  trade-history download is approved.

2026-06-14 continuation checkpoint:

- Duplicate-source audit after the liquidity-sweep question found no fresh
  no-cost public source family that is both untested and stronger than the
  current ES/MES lead. Recently checked or already rejected/data-gated families
  include price-only and trade-side-only sweep/reclaim, overnight/gap/VWAP
  reversion, Fama-French and short-term-reversal factors, Cboe option sentiment,
  VIX/VRP/MOVE/cross-asset volatility, commodity and CFTC positioning, Treasury
  auctions/TIC/H.15, OFR/H.4.1/RRP plumbing, CP funding stress, FOMC text,
  GDPNow, SLOOS, NFCI, CFNAI, EPU/EMV/news/GPR, weather/cloud-cover, 52-week
  anchoring, and local OHLCV technical mean-reversion variants.
- Added a durable predeclared protocol for the only current packaged ES
  independent mean-reversion candidate:
  `research_artifacts/es_mes_flow_divergence_validation_protocol_20260614.md`.
  The protocol keeps `afternoon_mes_large20_buy_pressure_short` as the first
  rerun after approved longer ES+MES `trades` history, forbids post-download
  gate weakening, and preserves the rule that the branch is not live eligible
  until the staged WFA/monkey/Monte Carlo/incubation path passes.

## ES Wikimedia Investor-Attention Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost, non-orderflow, non-macro-release public
  attention source distinct from the already rejected AAII/NAAIM, Michigan
  sentiment, SF Fed news sentiment, EPU/EMV/news/GPR, and Baker-Wurgler data
  gates. The mean-reversion thesis was that spikes or troughs in public market
  attention can proxy for retail/investor attention pressure and subsequent
  contrarian ES behavior.
- Academic/source backing:
  - Da, Engelberg, and Gao, "In Search of Attention," Journal of Finance 2011,
    supports search-attention proxies as investor-attention measures.
  - Moat et al., "Quantifying Wikipedia Usage Patterns Before Stock Market
    Moves," Scientific Reports 2013, supports Wikipedia pageview behavior as a
    financial attention signal.
  - Wikimedia REST Pageviews API supplied daily per-article pageviews.
- Source/data:
  - API endpoint family:
    `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/`.
  - Raw cache:
    `/private/tmp/wikimedia_investor_attention_pageviews_core.csv`.
  - Feature cache:
    `/private/tmp/wikimedia_investor_attention_features_core.csv`.
  - Pages tested after a rate-limited broader attempt: `S&P_500`,
    `Stock_market`, `Recession`, `Inflation`, `VIX`, and `Bear_market`.
  - Daily pageview coverage was 2015-07-01 through 2026-05-29.
- No-lookahead handling: each ES session used only the latest completed
  pageview source date strictly before the ES session date. Same-day pageviews
  were never used for same-day ES entries.
- Screen mechanics:
  - Built log pageviews, 1-day and 5-day log changes, rolling 21/63/126/252-day
    z-scores and ranks, plus composite risk-attention, market-attention,
    risk-minus-market, and risk-share features.
  - Tested bounded long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59 with optional prior-ES-up/down filters.
  - ES source cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Result paths: `/private/tmp/wikimedia_attention_es_screen_all.csv` and
    `/private/tmp/wikimedia_attention_es_screen_top.csv`.
  - Split windows: early 2016-2018, WFA-like 2019-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 160 retained attention features after the source-valid warmup.
  - Retained 380 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best row:
  - Low 5-day inflation-page attention change rank, `inflation_chg5_rank126 <=
    0.2`, no prior-session filter, long 09:35 -> 15:59.
  - early n77/PF 1.10, WFA n201/PF 1.65/MAR 5.85/avg `$264.84`, core
    n80/PF 2.21, incubation n56/PF 1.63, and full n334/PF 1.56.
  - Rejection reason: the WFA evidence is only 201 trades, far below the
    500-trade default gate, and the source starts in 2015 so it cannot provide
    the standard 2011-start ES early-history proof.
- Best dense examples were weaker:
  - `inflation_z21 <= -0.5`, long 11:00 -> 15:59, had WFA n306/PF 1.57 and
    incubation n77/PF 1.31, still under the WFA trade-count gate.
  - `inflation_z63 <= -0.5`, long 11:00 -> 15:59, had WFA n355/PF 1.41 and
    incubation n90/PF 1.41, below the WFA PF and density gates.
- Promotion decision: do not stage. Wikimedia market-attention data is a
  distinct and academically defensible public source, but the observed ES
  intraday mean-reversion signal is either too sparse or too weak. Do not rerun
  simple Wikipedia/pageview attention level, rank, z-score, change, risk
  attention, market attention, or risk-minus-market attention variants without a
  materially richer attention source and a predeclared short-history validation
  policy.

## ES 5-Year Breakeven Inflation-Risk Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public inflation-risk repricing source
  distinct from ES/NQ price/orderflow continuation, liquidity sweep, consumer
  sentiment, NFCI/CFNAI, and the prior nominal Treasury-curve/H.15 screen. The
  mean-reversion thesis was that sharp changes or low/high regimes in market
  inflation compensation can proxy for macro risk repricing, with ES buying
  after inflation-risk/risk-off pressure or fading stretched inflation-risk
  states.
- Academic/source backing:
  - Campbell, Sunderam, and Viceira, "Inflation Bets or Deflation Hedges?",
    motivates inflation-risk and nominal-bond-risk state variables for equity
    risk-premium timing.
  - Federal Reserve/FRED 5-Year Breakeven Inflation Rate (`T5YIE`) supplies a
    daily market-implied inflation-compensation series.
- Source/data:
  - FRED graph CSV:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=T5YIE`.
  - Raw cache: `/private/tmp/fred_T5YIE.csv`.
  - Feature cache: `/private/tmp/fred_t5yie_breakeven_features.csv`.
  - Coverage parsed: 2003-01-02 through 2026-06-12; ES screen used active-roll
    RTH cache `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- No-lookahead handling: each daily breakeven observation was made eligible only
  from the next business-day ES session. Same-day FRED values were not used for
  same-day ES entries.
- Screen mechanics:
  - Built `T5YIE` level, 1/5/21/63-day changes, and rolling
    21/63/126/252-day ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional prior-ES-up/down filters and current ES
    round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_t5yie_breakeven_es_screen_all.csv` and
    `/private/tmp/fred_t5yie_breakeven_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 10,230 retained diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best broad row:
  - `t5yie_rank252 <= 0.70` after a prior ES down session, long 11:00 ->
    15:59.
  - early n258/PF 0.900, WFA n710/PF 1.350/MAR 0.701/average `$117.31`, core
    n79/PF 1.321, incubation n79/PF 1.683/MAR 2.246, and full n1047/PF
    1.323/net `$107,415`.
  - Rejection reason: misses WFA PF >= 1.5 and early-history PF >= 1.0 despite
    attractive incubation behavior.
- Promotion decision: do not stage. Five-year breakeven inflation state has a
  recognizable contrarian/risk-repricing shape after prior ES weakness, but it
  is not strong enough in WFA or early history under current costs. Do not rerun
  simple `T5YIE` breakeven level, rank, z-score, change, or prior-down
  breakeven-risk ES mean-reversion variants without materially different
  inflation-risk source structure or a stronger point-in-time event filter.

## ES Daily RRP Liquidity-State Screen

- Status: rejected before staged implementation.
- Why tested: this reopened the earlier daily RRP data gate after the official
  FRED graph CSV route began working from this environment. The thesis was a
  public funding-liquidity/risk-capacity state distinct from price/orderflow
  continuation, NQ momentum, and the already rejected H.4.1/OFR/NFCI/CP
  liquidity branches: large changes or high/low regimes in overnight reverse
  repo usage can proxy for liquidity absorption/release and short-horizon ES
  risk-appetite pressure.
- Academic/source backing:
  - Brunnermeier and Pedersen, "Market Liquidity and Funding Liquidity,"
    motivates funding-liquidity constraints and risk-capacity state variables.
  - Federal Reserve/FRED Overnight Reverse Repurchase Agreements:
    Treasury Securities Sold by the Federal Reserve in Temporary Open Market
    Operations (`RRPONTSYD`) supplies the official daily RRP series.
- Source/data:
  - FRED graph CSV:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=RRPONTSYD`.
  - Raw cache: `/private/tmp/fred_RRPONTSYD_retry.csv`.
  - Feature cache: `/private/tmp/fred_rrp_liquidity_features.csv`.
  - Coverage parsed: 3,262 non-null daily observations from 2003-02-07 through
    2026-06-12; ES screen used active-roll RTH cache
    `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- No-lookahead handling: each daily RRP observation was made eligible only from
  the next business-day ES session. Same-day RRP values were not used for
  same-day ES entries. The scratch screen initially exposed and corrected a
  prior-session filter bug before results were used; the retained result uses
  only the previous completed ES session return for `prior_up`/`prior_down`.
- Screen mechanics:
  - Built RRP level, `log1p` level, 1/5/21/63-day changes, absolute changes,
    21/63-day means, and rolling 21/63/126/252-day ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down
    filters and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_rrp_liquidity_state_fast_all.csv` and
    `/private/tmp/fred_rrp_liquidity_state_fast_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 7,862 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best sparse row:
  - `rrp_abs_chg1_rank21 >= 0.952381` after a prior ES down session, long
    11:00 -> 15:59.
  - early n165/PF 0.671, WFA n111/PF 2.189/MAR 9.895/average `$300.18`, core
    n26/PF 2.875, incubation n16/PF 2.249, and full n292/PF 1.518.
  - Rejection reason: WFA, core, and incubation samples are far below the
    default density gates, and early-history PF is below 1.0.
- Best dense row:
  - `rrp_chg5 <= -11.206`, no prior-session filter, long 11:00 -> 15:30.
  - early n143/PF 0.949, WFA n764/PF 1.328/MAR 3.917/average `$98.66`, core
    n137/PF 1.500, incubation n92/PF 1.768, and full n1135/PF 1.351.
  - Rejection reason: WFA PF is far below 1.5 and early-history PF is below
    1.0 despite adequate WFA/incubation density.
- Promotion decision: do not stage. Daily RRP liquidity state is now no longer
  just data-gated, but the official series does not produce a robust
  independent ES intraday mean-reversion candidate under the current flat-hold
  screen. Do not rerun simple RRP level, RRP change, RRP rank/z-score,
  liquidity-drain/release, or prior-down RRP shock variants without materially
  different source structure or a stronger execution signal.

## ES NFIB Small-Business Sentiment Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public small-business sentiment and
  real-activity survey source distinct from Michigan consumer sentiment,
  AAII/NAAIM investor sentiment, SLOOS/NFCI/CFNAI credit and activity state,
  daily news sentiment, RRP liquidity state, and ES/NQ price/orderflow
  continuation. The mean-reversion thesis was that weak or deteriorating
  small-business optimism, sales, credit, hiring, or inventory expectations can
  proxy for Main Street pessimism and macro-risk pressure, with ES buying after
  pessimistic states or fading over-optimistic states.
- Academic/source backing:
  - NFIB Small Business Economic Trends supplies monthly small-business survey
    indicators; its public page says monthly surveys begin in 1986 and the
    report is released on the second Tuesday of each month.
  - Bachmann, Elstner, and Sims business-survey uncertainty evidence supports
    business survey states as economic-activity/uncertainty variables.
  - Lemmon and Portniaguina-style sentiment/asset-pricing evidence supports
    survey sentiment as an independent risk-premium state, though this screen
    used small-business survey data rather than consumer confidence.
- Source/data:
  - NFIB SBET API documentation:
    `https://www.nfib-sbet.org/Developers.html`.
  - API endpoint:
    `https://api.nfib-sbet.org:443/rest/sbetdb/_proc/getIndicators2`.
  - Raw cache: `/private/tmp/nfib_sbet_indicators_raw.csv`.
  - Feature cache: `/private/tmp/nfib_sbet_features.csv`.
  - Coverage parsed: 485 monthly rows from 1986-01 through 2026-05.
  - Fields tested: Small Business Optimism Index plus the public frontend
    component fields for plans to hire, plans for capital outlays, plans to
    increase inventories, expected economy improvement, expected real sales,
    current inventories, current job openings, expected credit conditions,
    good time to expand, and earnings trends.
- No-lookahead handling: each survey month was made eligible only from the
  business day after the second Tuesday of the following month. This is
  conservative relative to same-day release trading and avoids using the
  current-month survey in same-month ES entries. Because the API serves current
  history, any future pass would still require a release/vintage audit for
  seasonal-adjustment or historical revision risk before staged promotion.
- Screen mechanics:
  - Built levels, 1/3/6/12-month changes, 3/6-month means, and rolling
    12/24/60/120-month ranks and z-scores for each field.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down
    filters and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/nfib_sbet_state_screen_all.csv` and
    `/private/tmp/nfib_sbet_state_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 7,998 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best sparse row:
  - Low 24-month z-score of inventory plans, `plans_inventory_z24 <= -0.825210`,
    after a prior ES down session, long 11:00 -> 15:59.
  - early n38/PF 0.977, WFA n288/PF 1.653/MAR 7.339/average `$238.97`, core
    n83/PF 1.365, incubation n23/PF 2.548, and full n349/PF 1.679.
  - Rejection reason: WFA and incubation density are far below the default
    gates, and early-history evidence is too small and below PF 1.0.
- Best dense row:
  - Flat or falling three-month expected-economy-improvement component,
    `expect_economy_improve_chg3 <= 0`, after a prior ES down session, long
    11:00 -> 15:30.
  - early n212/PF 0.827, WFA n582/PF 1.293/MAR 4.384/average `$96.27`, core
    n153/PF 1.217, incubation n66/PF 2.236, and full n888/PF 1.345.
  - Rejection reason: WFA PF is far below 1.5 and early-history PF is below
    1.0 despite acceptable WFA density.
- Promotion decision: do not stage. NFIB small-business sentiment is a clean
  independent public survey source, but the simple ES intraday translation is
  either too sparse or too weak across WFA/early-history gates. Do not rerun
  simple NFIB optimism, small-business uncertainty/sentiment, inventory-plan,
  hiring-plan, sales-expectation, credit-condition, good-time-to-expand, or
  earnings-trend variants without materially different source structure,
  release-vintage validation, or a stronger execution signal.

## ES Federal Reserve G.19 Consumer-Credit Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public household-credit cycle source distinct
  from H.8 bank credit, SLOOS/NFCI/CFNAI, CP funding stress, RRP plumbing,
  business/consumer/investor sentiment, and ES/NQ price/orderflow continuation.
  The mean-reversion thesis was that rapid consumer-credit contraction,
  revolving-credit stress, or weak nonrevolving-credit growth can proxy for
  household balance-sheet pressure and transient equity-index risk aversion,
  making ES upside mean reversion after pessimistic credit states plausible.
- Academic/source backing:
  - Federal Reserve G.19 Consumer Credit is the official monthly consumer-credit
    release; the Federal Reserve says it is generally issued on the fifth
    business day of each month and the Data Download Program exposes Consumer
    Credit Outstanding packages.
  - Household-credit and intermediary/credit-cycle asset-pricing literature
    supports credit growth and household balance-sheet stress as macro-risk
    state variables, though this screen used only the official current G.19
    history and did not reconstruct historical vintages.
- Source/data:
  - Current release: `https://www.federalreserve.gov/releases/g19/current/`.
  - Data Download Program:
    `https://www.federalreserve.gov/datadownload/Choose.aspx?rel=g19`.
  - CSV package used:
    `https://www.federalreserve.gov/datadownload/Output.aspx?rel=G19&series=696245eb361e0a8bc89b8e5b01cc971b&lastObs=&from=&to=&filetype=csv&label=include&layout=seriescolumn&type=package`.
  - Raw cache: `/private/tmp/fed_g19_consumer_credit_sa_raw.csv`.
  - Feature cache: `/private/tmp/fed_g19_consumer_credit_features.csv`.
  - Coverage parsed: 1,000 monthly rows from 1943-01 through 2026-04.
  - Fields tested: seasonally adjusted total, revolving, and nonrevolving
    consumer-credit annualized percent changes, levels, monthly flows, revolving
    and nonrevolving shares, flow shares, and revolving-minus-nonrevolving
    growth/flow spreads.
- No-lookahead handling: each source month was made eligible only from the
  business day after the estimated fifth business day of the following month.
  This is conservative relative to same-day release trading. Because the package
  is current-history CSV, any future pass would still need a point-in-time
  vintage/revision audit before staged promotion.
- Screen mechanics:
  - Built levels, 1/3/6/12-month changes, 3/6-month means, and rolling
    12/24/60/120-month ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fed_g19_consumer_credit_screen_all.csv` and
    `/private/tmp/fed_g19_consumer_credit_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 10,426 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best sparse row:
  - Falling six-month nonrevolving-credit growth,
    `nonrevolving_pct_ann_chg6 <= -3.11`, after a prior ES down session, long
    11:00 -> 15:30.
  - early n53/PF 0.452, WFA n99/PF 2.480/MAR 8.658/average `$353.08`, core
    n10/PF 1.497, incubation n10/PF 2.342, and full n173/PF 1.887.
  - Rejection reason: far below WFA/core/incubation density, and early-history
    PF is materially below 1.0.
- Best dense row:
  - Low 12-month z-score of revolving-credit level,
    `revolving_level_z12 <= 1.610539`, after a prior ES down session, long
    11:00 -> 15:59.
  - early n321/PF 0.804, WFA n700/PF 1.274/MAR 4.916/average `$100.25`, core
    n104/PF 1.162, incubation n108/PF 1.271, and full n1184/PF 1.196.
  - Rejection reason: enough density, but WFA PF is far below 1.5 and
    early/core robustness are weak.
- Promotion decision: do not stage. G.19 consumer credit is independent and
  academically plausible, but the simple ES intraday translation is either too
  sparse or too weak across WFA, early-history, and core gates. Do not rerun
  simple consumer-credit growth, revolving/nonrevolving credit, credit-flow,
  credit-share, or G.19 household-credit stress variants without materially
  different source structure, point-in-time vintage validation, or a stronger
  execution signal.

## ES Census Retail-Sales Real-Demand Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public real-consumption-demand source distinct
  from G.19 consumer credit, NFIB small-business sentiment, GDPNow nowcast
  components, CFNAI/NFCI, and price/orderflow continuation. The mean-reversion
  thesis was that weak or compositionally poor retail spending can proxy for
  consumer-demand stress and transient equity-index risk aversion, while strong
  spending/food-services mix can proxy for crowded optimism that may fade.
- Academic/source backing:
  - Census Advance Monthly Retail Trade Survey supplies official monthly
    advance retail and food-services sales and release schedules.
  - Consumption-risk and consumption-wealth literature, including
    Parker-Julliard-style long-run consumption-risk evidence and
    Lettau-Ludvigson-style consumption/wealth return-predictability evidence,
    supports consumer demand and household balance-sheet state as plausible
    macro-risk variables.
- Source/data:
  - Census release schedule:
    `https://www.census.gov/retail/release_schedule.html`.
  - Historical MARTS release-date workbook:
    `https://www.census.gov/retail/marts/www/MARTSreleasedates.xls`.
  - FRED graph CSVs used as current-vintage data mirrors for Census series:
    `RSAFS`, `RSXFS`, `RRSFS`, and `MRTSSM44X72USS`.
  - Raw cache: `/private/tmp/fred_census_retail_sales_raw.csv`.
  - Release-date cache: `/private/tmp/MARTSreleasedates.xls`.
  - Feature cache: `/private/tmp/census_retail_sales_features.csv`.
  - Coverage parsed: 412 monthly rows from 1992-01 through 2026-04.
  - Fields tested: advance retail and food-services sales, advance retail-trade
    sales, real retail and food-services sales, revised retail and food-services
    sales, retail-trade share, real-to-nominal ratio, and a food-services proxy.
- No-lookahead handling:
  - Each retail-sales source month was made eligible only from the business day
    after its official Census release date.
  - Normal historical months used the MARTS release-date workbook; delayed
    2025-2026 current schedule rows were parsed from the Census schedule page;
    the 2018-2019 federal-funding-lapse months were explicitly shifted to the
    delayed release dates visible in the official historical schedule pattern.
  - The data values came from FRED current-vintage graph CSVs, so any future
    pass would still require Census vintage/revision validation before staged
    promotion.
- Screen mechanics:
  - Built levels, 1/3/6/12-month changes and percentage changes, 3/6-month
    means, and rolling 12/24/60/120-month ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/census_retail_sales_es_screen_all.csv` and
    `/private/tmp/census_retail_sales_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 6,110 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 3.
- Best sparse row:
  - Weak 12-month food-services-proxy growth, `food_services_proxy_pct12 <=
    0.030286`, after a prior ES down session, long 10:30 -> 15:30.
  - early n31/PF 0.980, WFA n106/PF 1.723/MAR 3.689/average `$244.41`, core
    n27/PF 2.084, incubation n11/PF 4.225, and full n158/PF 1.707.
  - Rejection reason: far below WFA/core/incubation density and insufficient
    early-history evidence.
- Best loose dense row:
  - High food-services-proxy rank condition,
    `food_services_proxy_rank24 <= 0.958333`, after a prior ES down session,
    long 11:00 -> 15:30.
  - early n153/PF 0.719, WFA n417/PF 1.425/MAR 3.896/average `$141.07`, core
    n105/PF 1.040, incubation n50/PF 1.343, and full n635/PF 1.304.
  - Rejection reason: this is the best WFA >= 400 plus incubation >= 50 shape,
    but it misses the WFA 500-trade and PF 1.5 gates, has weak early/core PF,
    and is only a loose diagnostic row rather than a staged candidate.
- Best WFA-density row:
  - Six-month real retail-sales change no higher than 2,016 units,
    `real_retail_food_services_chg6 <= 2016`, after a prior ES down session,
    long 11:00 -> 15:59.
  - early n177/PF 0.725, WFA n596/PF 1.284/MAR 4.204/average `$114.40`, core
    n90/PF 0.923, incubation n70/PF 1.257, and full n856/PF 1.217.
  - Rejection reason: adequate WFA density, but WFA PF is far below 1.5 and
    early/core robustness are poor.
- Promotion decision: do not stage. Retail-sales state is independent and has a
  cleaner release-date path than most current-vintage monthly data, but the
  simple ES intraday translation is either sparse or diluted below WFA PF and
  early/core robustness gates. Do not rerun simple retail-sales level,
  retail-sales growth, real retail sales, retail-trade share, food-services
  proxy, or Census/FRED retail-demand variants without materially different
  source structure, vintage validation, or a stronger execution signal.

## ES JOLTS Labor-Demand / Worker-Confidence Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public labor-demand and worker-confidence
  source distinct from weekly jobless claims, payroll/unemployment macro-state,
  NFIB hiring/job-openings sentiment, retail sales, consumer credit, and
  price/orderflow continuation. The mean-reversion thesis was that deteriorating
  openings, quits, hires, or rising layoffs can proxy for labor-market stress
  and transient risk aversion, while extreme tightness/quit confidence can proxy
  for macro optimism that may fade.
- Academic/source backing:
  - BLS JOLTS supplies official monthly job openings, hires, quits, and
    layoffs/discharges measures.
  - Labor-market tightness and labor-flow literature treats vacancies,
    separations, and quits as state variables for real activity and worker
    bargaining/confidence.
  - Unemployment-news and macro-risk-premium evidence, including
    Boyd-Hu-Jagannathan-style labor-news stock-reaction work, supports testing
    labor-market state as an equity-index risk variable.
- Source/data:
  - FRED graph CSVs used as current-vintage mirrors for BLS JOLTS series:
    `JTSJOL`, `JTSJOR`, `JTSQUL`, `JTSQUR`, `JTSHIL`, `JTSHIR`, `JTSLDL`, and
    `JTSLDR`.
  - BLS JOLTS schedule page was blocked from shell access during this run, so
    the screen used a conservative release lag instead of exact BLS release
    dates.
  - Raw cache: `/private/tmp/fred_jolts_labor_demand_raw.csv`.
  - Feature cache: `/private/tmp/fred_jolts_labor_demand_features.csv`.
  - Coverage parsed: 305 monthly rows from 2000-12 through 2026-04.
  - Fields tested: openings level/rate, quits level/rate, hires level/rate,
    layoffs/discharges level/rate, openings-minus-hires, quits-minus-layoffs,
    openings-to-layoffs proxy, quits-to-layoffs ratio, labor-tightness rate,
    and worker-confidence rate.
- No-lookahead handling: each source month was made eligible only from the next
  business day after month-end plus 45 calendar days. This is conservative
  relative to actual JOLTS release timing. Because the values came from FRED
  current-vintage graph CSVs, any future pass would still require BLS
  release/vintage validation before staged promotion.
- Screen mechanics:
  - Built levels, 1/3/6/12-month changes and percentage changes, 3/6-month
    means, and rolling 12/24/60/120-month ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_jolts_labor_demand_es_screen_all.csv` and
    `/private/tmp/fred_jolts_labor_demand_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 13,266 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best sparse row:
  - High 12-month z-score of labor-tightness rate,
    `labor_tightness_rate_z12 >= 1.782266`, after a prior ES up session, long
    09:35 -> 15:59.
  - early n111/PF 1.134, WFA n95/PF 2.483/MAR 7.776/average `$185.39`, core
    n37/PF 3.610, incubation n11/PF 1.666, and full n227/PF 1.671.
  - Rejection reason: WFA/core/incubation density is far below default gates.
- Best WFA-density row:
  - High 12-month rank of quits level, `quits_level_rank12 >= 0.916667`, after a
    prior ES up session, long 09:35 -> 15:30.
  - early n302/PF 1.085, WFA n506/PF 1.291/MAR 3.935/average `$81.07`, core
    n133/PF 1.416, incubation n12/PF 2.105, and full n842/PF 1.258.
  - Rejection reason: WFA density is adequate, but WFA PF is far below 1.5 and
    incubation density is unusably small.
- Best loose dense row:
  - Rising openings-to-layoffs proxy over three months,
    `openings_to_unemployed_proxy_pct3 >= 0.106582`, no prior-session filter,
    long 09:35 -> 15:30.
  - early n187/PF 1.158, WFA n441/PF 1.358/MAR 3.684/average `$122.83`, core
    n191/PF 1.519, incubation n59/PF 0.750, and full n757/PF 1.162.
  - Rejection reason: misses WFA PF, WFA trade density, and incubation PF.
- Promotion decision: do not stage. JOLTS labor-demand state is independent and
  academically plausible, but the simple ES intraday translation is either too
  sparse or diluted below WFA PF and incubation robustness gates. Do not rerun
  simple JOLTS job-openings, quits, hires, layoffs/discharges, labor-tightness,
  worker-confidence, or labor-demand rank/z-score variants without exact BLS
  release/vintage validation and materially different execution structure.

## ES Housing-Cycle / Residential-Construction Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public housing-cycle and residential-real-
  economy source distinct from consumer credit, retail sales, JOLTS labor
  demand, SLOOS mortgage/consumer credit standards, and price/orderflow
  continuation. The mean-reversion thesis was that weak housing activity,
  excess supply, or high mortgage-rate pressure can proxy for cyclical stress
  and transient equity-index risk aversion, while very strong starts/permits may
  proxy for overheated optimism that fades.
- Academic/source backing:
  - Housing starts, permits, new-home sales, months' supply, and mortgage rates
    are standard housing-cycle indicators.
  - Leamer-style housing-cycle evidence supports residential construction as a
    leading business-cycle variable, and housing/credit-cycle literature treats
    housing activity and mortgage-rate pressure as macro-risk state variables.
- Source/data:
  - FRED graph CSVs used as current-vintage mirrors for `HOUST`, `PERMIT`,
    `HSN1F`, `MSACSR`, and `MORTGAGE30US`.
  - Raw cache: `/private/tmp/fred_housing_cycle_raw.csv`.
  - Feature cache: `/private/tmp/fred_housing_cycle_features.csv`.
  - Coverage parsed: 810 monthly rows from 1959-01 through 2026-06; core
    housing fields are available through 2026-04 in the ES sample, while the
    mortgage-rate monthly average extends farther.
  - Fields tested: housing starts, building permits, new-home sales, months'
    supply of new homes, monthly averaged 30-year mortgage rates,
    permits-minus-starts, permits-to-starts, sales-to-starts, supply pressure,
    and starts-minus-sales.
- No-lookahead handling: each source month was made eligible only from the next
  business day after month-end plus 45 calendar days. This is conservative
  relative to several housing releases. Because the values came from FRED
  current-vintage graph CSVs, any future pass would still require release and
  revision validation before staged promotion.
- Screen mechanics:
  - Built levels, 1/3/6/12-month changes and percentage changes, 3/6-month
    means, and rolling 12/24/60/120-month ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_housing_cycle_es_screen_all.csv` and
    `/private/tmp/fred_housing_cycle_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 11,408 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best WFA-density row:
  - Flat-to-rising permits-to-starts ratio over 12 months,
    `permits_to_starts_chg12 >= -0.054125`, after a prior ES down session, long
    11:00 -> 15:30.
  - early n286/PF 0.767, WFA n759/PF 1.282/MAR 6.313/average `$83.80`, core
    n167/PF 1.331, incubation n98/PF 1.906, and full n1173/PF 1.318.
  - Rejection reason: enough density and incubation, but WFA PF is far below
    1.5 and early-history PF is poor.
- Best sparse row:
  - One-month housing-starts jump, `housing_starts_pct1 >= 0.116775`, after a
    prior ES up session, short 09:35 -> 15:30.
  - early n72/PF 0.848, WFA n114/PF 1.689/MAR 3.529/average `$200.92`, core
    n10/PF 5.195, incubation n13/PF 3.462, and full n199/PF 1.716.
  - Rejection reason: WFA/core/incubation density is far too low and early PF is
    below 1.0.
- Best loose housing-supply row:
  - High 24-month rank of permits-minus-starts,
    `permits_minus_starts_rank24 >= 0.541667`, after a prior ES down session,
    long 11:00 -> 15:30.
  - early n225/PF 0.693, WFA n531/PF 1.305/MAR 5.451/average `$82.92`, core
    n121/PF 1.398, incubation n81/PF 1.611, and full n856/PF 1.274.
  - Rejection reason: adequate density, but WFA PF and early-history robustness
    are too weak.
- Promotion decision: do not stage. Housing-cycle state is independent and
  academically plausible, but the simple ES intraday translation is diluted
  below WFA PF and early-history robustness gates. Do not rerun simple housing
  starts, permits, new-home sales, months' supply, mortgage-rate, permits/spread,
  or housing-cycle rank/z-score variants without materially different source
  structure, release/vintage validation, or a stronger execution signal.

## ES Consumer-Credit Delinquency Stress Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost public realized-credit-stress source distinct
  from G.19 consumer-credit balances, SLOOS lending standards, retail demand,
  housing activity, labor demand, and price/orderflow continuation. The
  mean-reversion thesis was that rising credit-card, consumer-loan, mortgage, or
  broad-loan delinquencies can proxy for household balance-sheet stress and
  transient equity-index risk aversion, making ES upside mean reversion after
  credit-stress states plausible.
- Academic/source backing:
  - Credit-cycle and household-balance-sheet literature treats consumer credit
    distress and delinquencies as macro-risk state variables.
  - Consumption-risk and financial-accelerator evidence supports realized
    household credit stress as an equity-risk-premium state.
- Source/data:
  - FRED graph CSVs used as current-vintage mirrors for Federal Reserve
    delinquency-rate series: `DRCLACBS`, `DRCCLACBS`, `DRSFRMACBS`, `DRALACBN`,
    and `DRCCLACBN`.
  - Raw cache: `/private/tmp/fred_credit_delinquency_stress_raw.csv`.
  - Feature cache: `/private/tmp/fred_credit_delinquency_stress_features.csv`.
  - Coverage parsed: 165 quarterly rows from 1985-Q1 through 2026-Q1.
  - Fields tested: consumer-loan delinquency, credit-card delinquency,
    single-family mortgage delinquency, broad all-loan delinquency,
    credit-card-minus-consumer spread, consumer-minus-mortgage spread,
    seasonally-adjusted-minus-not-seasonally-adjusted card spread, and a
    three-series stress average.
- No-lookahead handling: each source quarter was made eligible only from the
  next business day after quarter-end plus 60 calendar days. This is
  conservative relative to many bank-data releases. Because the values came from
  FRED current-vintage graph CSVs, any future pass would still require release
  and revision validation before staged promotion.
- Screen mechanics:
  - Built levels, 1/2/4/8-quarter changes and percentage changes, 2/4-quarter
    means, and rolling 8/20/40-quarter ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_credit_delinquency_stress_es_screen_all.csv`
    and `/private/tmp/fred_credit_delinquency_stress_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 5,019 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best WFA-density row:
  - Two-quarter broad-loan delinquency change at least `-0.11`,
    `all_loan_delinquency_nsa_chg2 >= -0.11`, after a prior ES down session,
    long 11:00 -> 15:30.
  - early n0, WFA n694/PF 1.233/MAR 3.296/average `$81.65`, core n140/PF 1.262,
    incubation n122/PF 1.519, and full n843/PF 1.297.
  - Rejection reason: enough WFA/incubation density, but no early-history
    coverage and WFA PF is far below 1.5.
- Best sparse row:
  - High mortgage-delinquency rank, `mortgage_delinquency_sa_rank8 >= 0.75`,
    after a prior ES down session, long 10:30 -> 15:30.
  - early n40/PF 1.894, WFA n84/PF 1.753/MAR 4.924/average `$226.25`, core
    n65/PF 1.718, incubation n144/PF 1.370, and full n323/PF 1.422.
  - Rejection reason: WFA density is far below the default gate and incubation
    PF is below 1.5.
- Best high-PF diagnostic row:
  - Low 20-quarter rank of card SA-minus-NSA spread,
    `card_sa_minus_nsa_rank20 <= 0.25`, after a prior ES down session, long
    11:00 -> 15:59.
  - early n0, WFA n265/PF 1.504/MAR 5.237/average `$169.15`, core n27/PF
    0.959, incubation n51/PF 1.708, and full n343/PF 1.549.
  - Rejection reason: WFA density, early coverage, and core robustness are
    inadequate despite attractive PF.
- Promotion decision: do not stage. Consumer-credit delinquency stress is
  independent and academically plausible, but the simple ES intraday translation
  is either sparse, missing early coverage, or diluted below WFA PF. Do not
  rerun simple delinquency-rate, credit-card delinquency, mortgage delinquency,
  all-loan delinquency, delinquency-spread, or household-credit-distress
  rank/z-score variants without materially different source structure,
  release/vintage validation, or a stronger execution signal.

## ES Primary-Dealer Funding-Stress Follow-up

- Status: rejected before staged implementation.
- Why tested: duplicate-source audit after the run found older NY Fed/OFR
  primary-dealer securities-lending/fails rejections in the ledger. This
  follow-up is therefore not a fresh independent family; it is a bounded
  confirmation focused on aggregate, Treasury, corporate, and agency
  fails/repo/reverse-repo pressure from the same official OFR `nypd` dataset.
  The branch remains distinct from price/orderflow continuation, price-only
  liquidity sweeps, RRP reserve-plumbing state, and household/real-activity
  macro screens, but it should be grouped with the already rejected
  primary-dealer market-plumbing family.
- Academic/source backing:
  - Brunnermeier and Pedersen funding-liquidity logic supports market-liquidity
    and funding-liquidity stress as risk-capacity state variables.
  - Intermediary asset-pricing and dealer-balance-sheet literature supports
    dealer constraints as a state variable for risky-asset expected returns.
  - The OFR Short-Term Funding Monitor API supplies official New York Fed
    Primary Dealer Statistics series.
- Source/data:
  - API endpoint:
    `https://data.financialresearch.gov/v1/series/dataset?dataset=nypd`.
  - Raw cache: `/private/tmp/ofr_primary_dealer_stress_raw.csv`.
  - Metadata cache: `/private/tmp/ofr_primary_dealer_stress_metadata.csv`.
  - Feature cache: `/private/tmp/ofr_primary_dealer_stress_features.csv`.
  - Parsed 106 primary-dealer fails/repo/reverse-repo series into 596 weekly
    observations from 2015-01-07 through 2026-06-03.
  - Fields tested: aggregate, Treasury, corporate, and agency fails to deliver
    and receive; dealer repo and reverse-repo totals; fails-deliver-minus-receive
    spreads; repo-minus-reverse-repo pressure; and deliver/receive ratios.
- No-lookahead handling: each weekly source date was made eligible only from the
  next business day after source date plus seven calendar days. This is
  deliberately conservative relative to likely weekly publication timing. The
  OFR API reports current-vintage data, so any future pass would still require a
  release/vintage audit before promotion.
- Screen mechanics:
  - Built levels, 1/2/4/13/26-week changes and percentage changes, 4/13/26-week
    means, and rolling 13/26/52/104-week ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/ofr_primary_dealer_stress_es_screen_all.csv`
    and `/private/tmp/ofr_primary_dealer_stress_es_screen_top.csv`.
  - Split windows were adjusted to the 2015-start source: early 2015-2017,
    WFA-like 2018-2024, core 2021-2022, and incubation 2025-01-01 through
    2026-05-29.
- Result summary:
  - Evaluated 29,985 no-lookahead outcomes across 2,795 ES sessions.
  - Retained 37,429 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best WFA-density row:
  - Four-week agency fails-to-receive percentage change,
    `agency_fails_to_receive_pct4 >= 0.337902`, no prior-session filter, long
    11:00 -> 12:00.
  - early n174/PF 0.710, WFA n562/PF 1.379/MAR 3.362/average `$66.55`, core
    n177/PF 1.205, incubation n93/PF 1.077, and full n829/PF 1.247.
  - Rejection reason: enough density, but WFA PF is below 1.4/1.5, early PF is
    poor, and incubation PF is too weak.
- Best loose density/incubation row:
  - Four-week agency fails-to-receive change,
    `agency_fails_to_receive_chg4 >= 593000000`, after a prior ES down session,
    long 11:00 -> 15:30.
  - early n164/PF 0.949, WFA n361/PF 1.477/MAR 7.346/average `$183.30`, core
    n114/PF 1.546, incubation n71/PF 2.423, and full n596/PF 1.528.
  - Rejection reason: attractive WFA/incubation economics, but WFA density is
    below 400/500 and early PF is below 1.0.
- Best sparse row:
  - Thirteen-week increase in dealer fails-deliver-minus-receive,
    `dealer_fails_deliver_minus_receive_total_chg13 >= 15699000000`, after a
    prior ES down session, long 10:30 -> 15:59.
  - early n12/PF 2.136, WFA n82/PF 2.657/MAR 4.985/average `$508.41`, core
    n19/PF 1.544, incubation n17/PF 3.191, and full n111/PF 2.731.
  - Rejection reason: high PF but far too sparse across every validation split.
- Promotion decision: do not stage. This confirms the prior primary-dealer
  market-plumbing rejection: the ES intraday translation is either too sparse or
  diluted below the WFA PF and early-history gates. Do not rerun simple NYPD
  primary-dealer fails, securities lending, repo/reverse-repo totals, Treasury
  or corporate fails, deliver/receive ratios, or dealer-funding-pressure
  rank/z-score variants without materially different source structure or a
  stronger execution signal.

## ES Fed Financial-Stress Composite Follow-up

- Status: rejected before staged implementation.
- Why tested: duplicate-source audit after the run found an older official
  financial-stress / Fed-liquidity rejection in the ledger using `STLFSI4`,
  `WALCL`, and `WRESBAL`. This follow-up is therefore not a fresh independent
  family; it is a bounded confirmation that adds Kansas City's `KCFSI`, refreshes
  current source data, and checks whether a simple two-Fed stress composite
  changes the prior rejection. It remains distinct from price/orderflow
  continuation, price-only liquidity sweeps, primary-dealer fails/repo plumbing,
  and daily RRP reserve-plumbing state, but it should be grouped with the
  already rejected official financial-stress source family.
- Mean-reversion thesis: high or rapidly changing market-wide financial stress
  can proxy for temporary risk aversion, funding constraints, or forced
  de-risking, creating possible same-day ES contrarian opportunities after
  completed prior-session weakness.
- Academic/source backing:
  - STLFSI4 documentation says the St. Louis Fed Financial Stress Index is built
    from 18 weekly series covering interest rates, yield spreads, and other
    stress indicators, and that values above zero indicate above-average
    financial-market stress.
  - KCFSI documentation describes the Kansas City Financial Stress Index as a
    monthly financial-stress index, with methodology support in "Financial
    Stress: What Is It, How Can It Be Measured, and Why Does It Matter?"
  - Funding-liquidity/intermediary-risk literature motivates financial stress
    as a risk-capacity state variable.
- Source/data:
  - FRED `STLFSI4`, St. Louis Fed Financial Stress Index:
    `https://fred.stlouisfed.org/series/STLFSI4`.
  - FRED `KCFSI`, Kansas City Financial Stress Index:
    `https://fred.stlouisfed.org/series/KCFSI`.
  - Raw cache: `/private/tmp/fred_financial_stress_composite_raw.csv`.
  - Feature cache: `/private/tmp/fred_financial_stress_composite_features.csv`.
  - Coverage parsed: 2,073 source rows; `STLFSI4` has 1,693 weekly values and
    `KCFSI` has 436 monthly values. The latest parsed STLFSI4 observation was
    2026-06-05 at `-0.8681`; the latest parsed KCFSI observation was May 2026
    at `-0.884374`.
- No-lookahead handling:
  - Weekly STLFSI4 observations were made eligible only from source date plus
    seven calendar days plus one business day.
  - Monthly KCFSI observations were made eligible only from month-end plus five
    calendar days plus one business day.
  - Because FRED graph CSVs are current-vintage mirrors, any future pass would
    still require release/vintage validation before staged promotion.
- Screen mechanics:
  - Built STLFSI4, KCFSI, average stress, max/min stress, and St. Louis-minus-KC
    stress spread.
  - Built 1/2/4/13/26-period changes and percentage changes, 4/13/26-period
    means, and rolling 13/26/52/104-period ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_financial_stress_composite_es_screen_all.csv`
    and `/private/tmp/fred_financial_stress_composite_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 8,600 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best WFA-density row:
  - Two-period STLFSI percentage increase, `stl_fsi_pct2 >= 0.348645`, no prior
    filter, long 11:00 -> 15:30.
  - early n145/PF 0.845, WFA n523/PF 1.342/MAR 2.836/average `$94.21`, core
    n83/PF 1.840, incubation n54/PF 1.884, and full n758/PF 1.367.
  - Rejection reason: enough WFA density and positive incubation, but WFA PF is
    well below 1.4/1.5, early PF is poor, and incubation n is below 75.
- Best WFA400 row:
  - Low 104-period rank of stress minimum, `stress_min_rank104 <= 0.432692`,
    after a prior ES down session, short 13:30 -> 15:59.
  - early n309/PF 0.771, WFA n436/PF 1.440/MAR 5.161/average `$108.90`, core
    n103/PF 1.672, incubation n56/PF 0.475, and full n848/PF 1.105.
  - Rejection reason: WFA PF is near the loose threshold, but incubation fails
    hard and early-history PF is poor.
- Best sparse row:
  - Four-period STLFSI change lower than `-0.3472`, after a prior ES down
    session, long 11:00 -> 15:59.
  - early n19/PF 1.468, WFA n113/PF 2.407/MAR 9.890/average `$371.33`, core
    n25/PF 1.776, incubation n13/PF 2.299, and full n161/PF 2.224.
  - Rejection reason: high PF but far too sparse across every validation split.
- Promotion decision: do not stage. This confirms the prior official
  financial-stress rejection: Fed financial-stress composites are either sparse,
  incubation-failed, or diluted below WFA PF and early-history robustness in
  simple ES intraday translation. Do not rerun simple STLFSI4/KCFSI financial
  stress level, change, percentage-change, rank, z-score, stress-average,
  stress-spread, WALCL, or reserve-balance variants without materially different
  execution structure or a stronger point-in-time event filter.

## ES NY Fed Survey of Consumer Expectations Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost official household-expectations survey source
  distinct from Michigan consumer sentiment, NFIB small-business sentiment,
  AAII/NAAIM investor sentiment, household credit/delinquency realized-data
  screens, and price/orderflow continuation. The mean-reversion thesis was that
  pessimistic or stressed household expectations around labor, credit, debt
  delinquency, household finances, inflation uncertainty, or stock returns can
  proxy for transient risk aversion and subsequent ES upside reversion after
  prior-session weakness.
- Academic/source backing:
  - NY Fed Survey of Consumer Expectations supplies monthly household
    expectations about inflation, labor markets, household finance, credit, and
    stock prices.
  - Survey-expectation and sentiment asset-pricing literature supports
    household expectations as a risk-premium and investor-attention/state
    variable.
  - The source is official and public, but the downloaded chart-data workbook is
    current history rather than a point-in-time vintage archive.
- Source/data:
  - Official SCE page: `https://www.newyorkfed.org/microeconomics/sce`.
  - Chart-data workbook:
    `https://www.newyorkfed.org/medialibrary/interactives/sce/sce/downloads/data/frbny-sce-data.xlsx?sc_lang=en`.
  - Raw workbook cache: `/private/tmp/frbny-sce-data.xlsx`.
  - Parsed raw cache: `/private/tmp/nyfed_sce_expectations_raw.csv`.
  - Feature cache: `/private/tmp/nyfed_sce_expectations_features.csv`.
  - Coverage parsed: 156 monthly rows from 2013-06 through 2026-05. The latest
    parsed headline values for 2026-05 were one-year inflation expectations
    `3.462475`, higher-unemployment probability `43.170620`, and stock-price-up
    probability `37.991848`.
- No-lookahead handling:
  - Each source month was made eligible only from month-end plus 15 calendar
    days plus one business day.
  - The latest 2026-05 SCE row therefore becomes eligible on 2026-06-16 and is
    outside the current ES cache ending 2026-05-29.
  - Because the workbook is current history, any future pass would still require
    exact release/vintage validation before staged promotion.
- Screen mechanics:
  - Parsed XLSX XML directly, without adding workbook dependencies.
  - Built headline features for one-/three-/five-year inflation expectations,
    inflation uncertainty, expected earnings, job-loss probability, job-finding
    probability, unemployment expectations, household income/spending
    expectations, debt-delinquency probability, interest-rate expectations,
    stock-price expectations, credit harder-minus-easier, household-finance
    worse-minus-better, and household-risk pressure composites.
  - Built 1/3/6/12-month changes and percentage changes, 3/6/12-month means,
    and rolling 12/24/60/120-month ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/nyfed_sce_expectations_es_screen_all.csv` and
    `/private/tmp/nyfed_sce_expectations_es_screen_top.csv`.
  - Split windows were adjusted to the 2013-start source: early 2014-2016,
    WFA-like 2017-2024, core 2021-2022, and incubation 2025-01-01 through
    2026-05-29.
- Result summary:
  - Evaluated 33,856 no-lookahead outcomes across 3,152 ES sessions.
  - Retained 38,401 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 1.
- Best WFA-density row:
  - Three-month mean household-risk pressure at least `20.677006`, after a prior
    ES down session, long 11:00 -> 15:30.
  - early n259/PF 1.062, WFA n519/PF 1.320/MAR 5.240/average `$105.93`, core
    n81/PF 1.195, incubation n125/PF 1.262, and full n943/PF 1.254.
  - Rejection reason: adequate density, early PF, and incubation, but WFA PF is
    far below the 1.5 acceptance gate and core PF misses 1.2.
- Only loose diagnostic row:
  - 60-month rank of household-risk pressure at least `0.483333`, after a prior
    ES down session, long 11:00 -> 15:30.
  - early n80/PF 0.772, WFA n443/PF 1.411/MAR 8.253/average `$150.47`, core
    n103/PF 1.331, incubation n121/PF 1.257, and full n644/PF 1.327.
  - Rejection reason: interesting WFA/incubation shape, but early-history PF is
    poor and WFA PF/density remain below the formal acceptance gate.
- Best sparse row:
  - 60-month z-score of household-risk pressure at least `0.522454`, after a
    prior ES down session, long 13:30 -> 15:59.
  - early n27/PF 0.313, WFA n105/PF 2.675/MAR 9.466/average `$307.86`, core
    n18/PF 2.397, incubation n113/PF 1.239, and full n245/PF 1.578.
  - Rejection reason: high WFA PF but far too sparse and early-history behavior
    is unusable.
- Promotion decision: do not stage. SCE household expectations are independent
  and academically plausible, but the simple ES intraday translation is either
  WFA-diluted, early-history-failed, or sparse. Do not rerun simple SCE
  inflation-expectations, labor-expectations, credit-access, household-finance,
  delinquency-expectations, stock-expectations, or household-risk-pressure
  rank/z-score variants without exact release/vintage validation and materially
  different execution structure.

## ES Weekly Economic Index Real-Activity Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost official weekly real-activity source distinct
  from GDPNow nowcast updates, Philadelphia Fed ADS real-time business
  conditions, Chicago CFNAI monthly activity, JOLTS labor-flow data, retail
  sales, and price/orderflow continuation. The mean-reversion thesis was that
  broad high-frequency economic weakness, acceleration, or volatility can proxy
  for macro-risk pressure and transient ES risk aversion.
- Academic/source backing:
  - The NY Fed/Dallas Fed Weekly Economic Index follows Lewis, Mertens, and
    Stock's high-frequency real-activity measurement framework.
  - Weekly real-activity state is a plausible macro-risk-premium variable, but
    it is not a direct intraday execution signal.
- Source/data:
  - FRED `WEI` graph CSV: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=WEI`.
  - Raw cache: `/private/tmp/fred_wei_weekly_economic_index_raw.csv`.
  - Feature cache: `/private/tmp/fred_wei_weekly_economic_index_features.csv`.
  - Coverage parsed: 962 weekly observations from 2008-01-05 through
    2026-06-06.
- No-lookahead handling:
  - Each weekly source date was made eligible only from source date plus seven
    calendar days plus one business day.
  - The latest 2026-06-06 observation therefore becomes eligible on 2026-06-15
    and is outside the current ES cache ending 2026-05-29.
  - Because the FRED graph CSV is a current-history mirror, any future pass
    would still require release/vintage validation before staged promotion.
- Screen mechanics:
  - Built WEI level, positive/negative state, 1/2/4/13/26-week changes,
    4/13/26-week means and volatility, 13/26/52/104-week ranks and z-scores,
    and a one-week-change-times-level interaction.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_wei_weekly_economic_index_es_screen_all.csv`
    and `/private/tmp/fred_wei_weekly_economic_index_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 1,334 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best WFA-density row:
  - Low 26-week WEI rank, `wei_rank26 <= 0.115385`, no prior filter, long
    13:30 -> 15:30.
  - early n185/PF 0.668, WFA n535/PF 1.297/MAR 4.288/average `$66.29`, core
    n176/PF 1.509, incubation n20/PF 0.448, and full n783/PF 1.143.
  - Rejection reason: adequate WFA density and decent core PF, but WFA PF is far
    below 1.5, early PF is poor, and incubation fails.
- Best WFA400 row:
  - Four-week WEI volatility at least `0.242126`, after a prior ES down session,
    long 11:00 -> 12:00.
  - early n80/PF 0.562, WFA n401/PF 1.350/MAR 2.924/average `$65.54`, core
    n141/PF 1.148, incubation n33/PF 2.115, and full n530/PF 1.327.
  - Rejection reason: WFA PF and density are below acceptance, early PF is very
    weak, and incubation is too sparse.
- Best sparse row:
  - High 104-week WEI rank, `wei_rank104 >= 0.831731`, after a prior ES up
    session, long 10:30 -> 15:30.
  - early n99/PF 0.731, WFA n225/PF 1.695/MAR 5.900/average `$106.00`, core
    n60/PF 1.638, incubation n84/PF 0.802, and full n434/PF 1.071.
  - Rejection reason: attractive WFA PF but too sparse, early PF is poor, and
    incubation fails.
- Promotion decision: do not stage. WEI is a clean official weekly real-activity
  source, but the simple ES intraday translation is too weak, holdout-failed, or
  sparse. Do not rerun simple WEI level, WEI change, WEI rank/z-score, WEI
  volatility, or weekly real-activity state variants without release/vintage
  validation and materially different execution structure.

## ES Atlanta Fed Wage Growth Tracker Labor-Cost Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost official labor-cost pressure source distinct
  from JOLTS labor-demand/worker-confidence, weekly claims, payroll/unemployment
  macro-state, NFIB hiring/job-openings sentiment, SCE household labor
  expectations, retail demand, and price/orderflow continuation. The
  mean-reversion thesis was that elevated or shifting wage pressure can proxy
  for inflation/labor-cost risk, crowded macro pessimism, or transient ES risk
  aversion.
- Academic/source backing:
  - Atlanta Fed Wage Growth Tracker measures wage growth of continuously
    employed individuals from CPS microdata and provides category splits such as
    job switchers/stayers, wage quartiles, paid-hourly workers, and industries.
  - Labor-income, wage-growth, and inflation-risk literature motivates labor
    cost pressure as a macro risk-premium state, but it is not a direct intraday
    execution signal.
- Source/data:
  - Official workbook:
    `https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/datafiles/chcs/wage-growth-tracker/wage-growth-data.xlsx`.
  - Raw workbook cache: `/private/tmp/atlanta_fed_wage_growth_data.xlsx`.
  - Parsed raw cache: `/private/tmp/atlanta_wage_growth_tracker_raw.csv`.
  - Feature cache: `/private/tmp/atlanta_wage_growth_tracker_features.csv`.
  - Scratch script: `/private/tmp/atlanta_wage_growth_tracker_screen.py`.
  - Parsed coverage: 521 monthly rows from 1983-01 through 2026-05. Latest
    2026-05 headline values: overall wage growth `3.5`, job stayer `3.3`, job
    switcher `3.7`, median `3.5`, zero-wage-change share `13.3`, and 12-month
    overall `3.8`.
- No-lookahead handling:
  - Each monthly source row was made eligible only from source month-end plus 45
    calendar days plus one business day.
  - Because the workbook is current history, any future pass would still require
    exact release/vintage validation before staged promotion.
- Screen mechanics:
  - Parsed XLSX XML directly, without adding workbook dependencies.
  - Focused on headline wage pressure, non-smoothed overall, mean/median,
    wage-growth IQR, zero-wage-change share, 1983 overall extension,
    switcher-minus-stayer pressure, low-minus-high wage quartile pressure,
    hourly-minus-nonhourly pressure, service-minus-manufacturing pressure, and
    12-month overall wage growth.
  - Built 1/3/12-month changes and percentage changes, 3/12-month means, and
    24/60/120-month ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths:
    `/private/tmp/atlanta_wage_growth_tracker_es_screen_all.csv` and
    `/private/tmp/atlanta_wage_growth_tracker_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,791 no-lookahead outcomes across 3,877 ES sessions.
  - Retained 7,356 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.3: 0.
- Best WFA-density row:
  - Twelve-month percentage change in service-minus-manufacturing wage pressure
    no greater than `1.25`, no prior filter, long 11:00 -> 15:30.
  - early n564/PF 0.888, WFA n2017/PF 1.083/MAR 2.464/average `$25.39`, core
    n399/PF 1.150, incubation n235/PF 1.057, and full n2892/PF 1.060.
  - Rejection reason: strong density but too close to random after costs, with
    failed early and incubation economics.
- Best WFA PF with at least 500 WFA trades:
  - Low-minus-high wage-quartile 60-month rank no greater than `0.925`, after a
    prior ES down session, long 11:00 -> 15:30.
  - early n418/PF 0.832, WFA n573/PF 1.268/MAR 3.629/average `$79.51`, core
    n68/PF 1.466, incubation n136/PF 1.408, and full n1182/PF 1.210.
  - Rejection reason: incubation is acceptable, but WFA PF is far below 1.5 and
    early-history PF fails.
- Best WFA400/incubation diagnostic row:
  - One-month percentage change in service-minus-manufacturing wage pressure at
    least `0.0`, after a prior ES down session, long 13:30 -> 15:30.
  - early n289/PF 0.718, WFA n482/PF 1.348/MAR 3.807/average `$68.39`, core
    n122/PF 1.331, incubation n57/PF 1.840, and full n874/PF 1.236.
  - Rejection reason: below WFA PF and WFA density gates, with unusable early
    history.
- Best sparse high-PF row:
  - 60-month rank of 12-month overall wage growth no greater than `0.55`, after
    a prior ES down session, long 10:30 -> 12:00.
  - early n239/PF 0.659, WFA n81/PF 1.753/MAR 3.977/average `$161.05`, core
    n76/PF 1.565, incubation n142/PF 1.073, and full n517/PF 1.054.
  - Rejection reason: high WFA PF is too sparse, early PF fails, and incubation
    PF is below 1.2.
- Promotion decision: do not stage. Atlanta Fed Wage Growth Tracker labor-cost
  pressure is independent and academically plausible, but the simple ES intraday
  translation is too weak, early-history-failed, or sparse. Do not rerun simple
  WGT headline wage-growth, switcher/stayer spread, wage-dispersion,
  zero-wage-change, wage-quartile, hourly/nonhourly, industry wage-pressure, or
  12-month wage-growth rank/z-score variants without exact release/vintage
  validation and materially different execution structure.

## ES Fed Financial Accounts Household Balance-Sheet Screen

- Status: rejected before staged implementation.
- Why tested: this was a no-cost official household balance-sheet source
  distinct from Shiller valuation state, Fed H.4.1 liquidity plumbing, SLOOS
  credit standards, delinquency stress, consumer credit balances, housing-cycle
  activity, JOLTS/claims labor data, and price/orderflow continuation. The
  mean-reversion thesis was that household wealth/leverage and debt-service
  pressure can proxy for slow-moving risk-premium or balance-sheet constraints
  that may condition ES reversals after risk-off sessions.
- Academic/source backing:
  - Lettau-Ludvigson-style consumption/wealth return-predictability evidence
    motivates household wealth balance-sheet ratios as state variables.
  - Household leverage and debt-service stress literature motivates debt burden
    as a macro risk-capacity variable, but it is not a direct intraday execution
    signal.
- Source/data:
  - FRED graph CSV mirrors of Federal Reserve Financial Accounts / household
    debt-service series:
    `TNWBSHNO`, `TFAABSHNO`, `TLBSHNO`, `HNONWPDPI`, `CMDEBT`, `FODSP`,
    `TDSP`, `MDSP`, and `CDSP`.
  - Example official CSV routes:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=TNWBSHNO` and
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=FODSP`.
  - Raw cache: `/private/tmp/fred_financial_accounts_household_raw.csv`.
  - Feature cache:
    `/private/tmp/fred_financial_accounts_household_features.csv`.
  - Scratch script:
    `/private/tmp/fred_financial_accounts_household_screen.py`.
  - Parsed coverage: 322 quarterly rows from 1945-Q4 through 2026-Q1. Debt
    service subseries have shorter starts and some latest-quarter missing
    values; for example, 2026-Q1 had household net worth `182979889`, total
    financial assets `141605209`, total liabilities `21560050`, household net
    worth to DPI `781.343836`, and mortgage debt `21069282`.
- No-lookahead handling:
  - Each quarterly source row was made eligible only from quarter-end plus 90
    calendar days plus one business day.
  - Because the FRED graph CSVs are current-history mirrors, any future pass
    would still require Federal Reserve release/vintage validation before
    staged promotion.
- Screen mechanics:
  - Built household net worth, total financial assets, total liabilities, net
    worth to disposable personal income, mortgage debt, financial-obligations
    ratio, total/mortgage/consumer debt-service ratios, liabilities-to-assets,
    liabilities-to-net-worth, mortgage-debt-to-net-worth, mortgage-debt-to-assets,
    net-worth-to-assets, financial-obligations-minus-debt-service, and
    mortgage-minus-consumer debt-service pressure.
  - Built 1/2/4/8-quarter changes and percentage changes, 2/4-quarter means,
    and 8/20/40-quarter ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths:
    `/private/tmp/fred_financial_accounts_household_es_screen_all.csv` and
    `/private/tmp/fred_financial_accounts_household_es_screen_top.csv`.
  - Split windows: early 2011-2014, WFA-like 2015-2024, core 2021-2022, and
    incubation 2025-01-01 through 2026-05-29.
- Result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 7,982 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.3: 0.
- Best WFA-density row:
  - One-quarter percentage change in household net worth to DPI no greater than
    `0.021496`, no prior filter, long 11:00 -> 15:30.
  - early n649/PF 0.920, WFA n2018/PF 1.054/MAR 1.273/average `$16.34`, core
    n181/PF 1.185, incubation n275/PF 1.086, and full n3076/PF 1.043.
  - Rejection reason: excellent density but economically too close to random,
    with failed early and incubation PF.
- Best WFA PF with at least 500 WFA trades:
  - Household net-worth 20-quarter z-score no greater than `1.668429`, after a
    prior ES down session, long 11:00 -> 15:59.
  - early n221/PF 0.744, WFA n513/PF 1.256/MAR 3.906/average `$91.49`, core
    n37/PF 1.018, incubation n74/PF 1.548, and full n863/PF 1.217.
  - Rejection reason: WFA density is barely adequate but PF is far below 1.5,
    core density is too low, and early-history behavior fails.
- Best WFA400/incubation diagnostic row:
  - Eight-quarter z-score of household debt-service ratio at least `0.748441`,
    after a prior ES down session, long 11:00 -> 15:59.
  - early n0, WFA n443/PF 1.265/MAR 2.194/average `$100.42`, core n71/PF
    1.286, incubation n95/PF 1.525, and full n538/PF 1.340.
  - Rejection reason: source coverage creates no early-history representation,
    while WFA PF remains below acceptance.
- Best sparse high-PF row:
  - One-quarter change in mortgage-minus-consumer debt-service pressure at least
    `0.116310`, after a prior ES down session, long 11:00 -> 15:30.
  - early n31/PF 0.516, WFA n124/PF 1.831/MAR 3.805/average `$201.75`, core
    n34/PF 1.916, incubation n28/PF 0.902, and full n183/PF 1.379.
  - Rejection reason: attractive WFA PF is far too sparse, early-history behavior
    is unusable, and incubation fails.
- Promotion decision: do not stage. Federal Reserve household balance-sheet
  state is independent and academically plausible, but the simple ES intraday
  translation is either diluted, early-history-failed, or sparse. Do not rerun
  simple Financial Accounts/Z.1 household net-worth, household assets/liabilities,
  net-worth-to-DPI, mortgage-debt, debt-service, financial-obligations,
  liabilities-to-net-worth, or household balance-sheet rank/z-score variants
  without release/vintage validation and materially different execution
  structure.

## ES BEA/FRED Corporate Profit-Margin Screen

- Status: rejected before staged implementation after flat-hold and focused
  managed-exit audits.
- Why tested: this was a no-cost official corporate-profit / profit-margin
  source distinct from Shiller valuation ratios, GDPNow nowcasts, monthly
  real-activity state, household balance sheets, labor-cost pressure, credit
  conditions, and price/orderflow continuation. The mean-reversion thesis was
  that weak or falling corporate profit margins can proxy for a macro risk
  premium or crowded risk-off state, while elevated margins can represent a
  valuation/profitability state that may mean-revert.
- Academic/source backing:
  - Corporate profit share and profitability/valuation literature motivates
    profit margins as slow-moving expected-return and mean-reversion state
    variables.
  - BEA NIPA corporate-profit series are official macro source data, but current
    FRED mirrors are not point-in-time vintages.
- Source/data:
  - FRED graph CSV mirrors of BEA NIPA series:
    `CPATAX`, `CPROFIT`, `CP`, `GDP`, and `GDI`.
  - Example official CSV routes:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPATAX`,
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPROFIT`, and
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=CP`.
  - Raw cache: `/private/tmp/fred_corporate_profit_margin_raw.csv`.
  - Feature cache: `/private/tmp/fred_corporate_profit_margin_features.csv`.
  - Flat scratch results:
    `/private/tmp/fred_corporate_profit_margin_es_screen_all.csv` and
    `/private/tmp/fred_corporate_profit_margin_es_screen_top.csv`.
  - Managed-exit scratch results:
    `/private/tmp/fred_corporate_profit_margin_path_es_screen_all.csv` and
    `/private/tmp/fred_corporate_profit_margin_path_es_screen_top.csv`.
  - Scratch scripts:
    `/private/tmp/fred_corporate_profit_margin_screen.py` and
    `/private/tmp/fred_corporate_profit_margin_path_audit.py`.
  - Parsed coverage: 317 quarterly rows from 1947-Q1 through 2026-Q1. Latest
    2026-Q1 values: after-tax profits with IVA/CCAdj `3590.004`, corporate
    profits with IVA/CCAdj `4392.490`, after-tax profits without IVA/CCAdj
    `3917.196`, GDP `31819.464`, and GDI `31539.380`.
- No-lookahead handling:
  - Each quarterly source row was made eligible only from quarter-end plus 90
    calendar days plus one business day.
  - Because the FRED graph CSVs are current-history mirrors, any future pass
    would still require BEA release/vintage validation before staged promotion.
- Flat screen mechanics:
  - Built corporate profits after tax with IVA/CCAdj, corporate profits with
    IVA/CCAdj, after-tax profits without IVA/CCAdj, GDP, GDI,
    pretax/after-tax profit-to-GDP and profit-to-GDI ratios, tax-wedge profit,
    IVA/CCAdj after-tax spread, and profit-margin pressure composites.
  - Built 1/2/4/8-quarter changes and percentage changes, 2/4-quarter means,
    and 8/20/40-quarter ranks and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
- Flat result summary:
  - Evaluated 41,981 no-lookahead outcomes across 3,895 ES sessions.
  - Retained 11,236 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 1.
- Best flat loose diagnostic:
  - Eight-quarter rank of corporate profits with IVA/CCAdj no greater than
    `0.875`, after a prior ES down session, long 11:00 -> 15:30.
  - early n233/PF 0.928, WFA n482/PF 1.457/MAR 4.672/average `$95.10`, core
    n58/PF 1.891, incubation n75/PF 1.538, and full n790/PF 1.366.
  - Rejection reason: interesting WFA/incubation/core shape, but it fails
    early-history PF and misses the 500 WFA-trade gate.
- Best flat WFA-density row:
  - Two-quarter mean of after-tax profit-to-GDP no greater than `0.108947`, no
    prior filter, long 11:00 -> 15:30.
  - early n942/PF 0.893, WFA n2135/PF 1.056/MAR 1.059, core n298/PF 1.171,
    incubation n234/PF 0.963, and full n3447/PF 1.014.
  - Rejection reason: dense but economically too weak after costs.
- Managed-exit audit:
  - Took the strongest 76 flat specs and tested stop-first paths with stop_pct
    `0.003`/`0.004`/`0.006`/`0.008`/`0.010`/`0.012` and target R
    `1.0`/`1.5`/`2.0`/`3.0`/`4.0`.
  - Result rows: 2,097.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 20.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 17.
- Best managed score row:
  - Twenty-quarter z-score of after-tax profit-to-GDI no greater than
    `0.560372`, after a prior ES down session, long 11:00 -> 15:30,
    `stop_pct=0.012`, `target_r=1.5`.
  - early n127/PF 0.832, WFA n650/PF 1.348/MAR 3.674/average `$77.29`, core
    n59/PF 1.910, incubation n77/PF 1.521, and full n854/PF 1.328.
  - Rejection reason: density and incubation are acceptable, but WFA PF is below
    1.5 and early-history PF fails.
- Best managed WFA400/incubation row:
  - Eight-quarter rank of corporate profits with IVA/CCAdj no greater than
    `0.875`, after a prior ES down session, long 11:00 -> 15:30,
    `stop_pct=0.012`, `target_r=1.0`.
  - early n239/PF 0.944, WFA n493/PF 1.483/MAR 7.086/average `$97.78`, core
    n59/PF 1.819, incubation n77/PF 1.506, and full n809/PF 1.376.
  - Rejection reason: still misses early-history PF and the WFA 500-trade gate.
- Best early-qualified managed row:
  - Eight-quarter z-score of GDP no greater than `1.501756`, after a prior ES
    down session, long 11:00 -> 15:30, `stop_pct=0.012`, `target_r=1.0`.
  - early n186/PF 1.043, WFA n570/PF 1.364/MAR 5.936, core n111/PF 1.550,
    incubation n78/PF 1.357, and full n868/PF 1.314.
  - Rejection reason: this is effectively a broad GDP/real-activity state rather
    than the profit-margin thesis, and still misses WFA PF.
- Promotion decision: do not stage. Corporate profit-margin state is an
  independent academically plausible source, and the best rows are closer than
  many public macro screens, but both flat and managed versions fail the formal
  WFA PF/density plus early-history gates. Do not rerun simple BEA/FRED
  corporate profits, after-tax profits, profit-to-GDP/GDI, profit-margin
  pressure, tax-wedge, or profit-rank/z-score variants without BEA vintage
  validation and a materially different execution or regime structure.

## ES BEA/FRED Personal Saving and Consumption-Pressure Screen

- Why tested: this is a no-cost official household-flow source distinct from
  household balance-sheet stocks, Michigan/SCE/NFIB sentiment, labor-cost
  pressure, GDPNow component nowcasts, corporate profit margins, and ES/NQ
  price/orderflow continuation. The thesis was contrarian/mean-reversion:
  strained or improving saving-versus-consumption conditions may proxy for
  marginal-utility, precautionary-saving, or consumption-risk regimes after a
  completed ES down session.
- Academic framing:
  - Campbell and Cochrane, "By Force of Habit: A Consumption-Based Explanation
    of Aggregate Stock Market Behavior" (`https://www.nber.org/papers/w4995`),
    motivate slow-moving consumption/habit state as a risk-premium driver.
  - Lettau and Ludvigson, "Consumption, Aggregate Wealth, and Expected Stock
    Returns" (`https://www.newyorkfed.org/research/staff_reports/sr77.html`),
    motivate consumption/income/wealth trend deviations as return-predictive
    state variables.
  - Parker and Julliard, "Consumption Risk and the Cross Section of Expected
    Returns" (`https://www.nber.org/papers/w9538`), motivate consumption-risk
    measurement over delayed horizons rather than only contemporaneous returns.
- Source/data:
  - FRED graph CSV mirrors of BEA NIPA monthly series `PSAVERT`, `PI`, `DSPI`,
    `DSPIC96`, `PCE`, `PCEC96`, `PCEDG`, `PCEND`, and `PCES`.
  - Raw cache: `/private/tmp/fred_personal_saving_pce_raw.csv`.
  - Feature cache: `/private/tmp/fred_personal_saving_pce_features.csv`.
  - Scratch scripts: `/private/tmp/fred_personal_saving_pce_screen.py` and
    `/private/tmp/fred_personal_saving_pce_path_audit.py`.
  - Flat result paths:
    `/private/tmp/fred_personal_saving_pce_es_screen_all.csv` and
    `/private/tmp/fred_personal_saving_pce_es_screen_top.csv`.
  - Managed-exit result paths:
    `/private/tmp/fred_personal_saving_pce_path_es_screen_all.csv` and
    `/private/tmp/fred_personal_saving_pce_path_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage and no-lookahead handling:
  - Parsed 808 monthly rows from 1959-01-31 through 2026-04-30.
  - Latest parsed 2026-04 values: personal saving rate `2.6`, personal income
    `26722.5`, disposable personal income `23472.2`, real DPI `17932.6`, PCE
    `21979.4`, real PCE `16792.1`, durable-goods PCE `2372.5`, nondurable-goods
    PCE `4480.7`, and services PCE `15126.3`.
  - Used a conservative month-end plus 45 calendar days plus one business day
    availability lag. The 2026-04 row becomes eligible on 2026-06-15, outside
    the current ES cache ending 2026-05-29. Because FRED graph CSVs are current
    history, any future pass would still require BEA release/vintage validation.
- Feature set:
  - Saving rate, personal income, disposable income, real disposable income,
    nominal/real PCE, durable/nondurable/services PCE, PCE-to-DPI,
    real-PCE-to-real-DPI, PCE-to-personal-income, DPI-to-personal-income,
    nominal/real saving buffers, durable/nondurable/services/goods shares,
    durable-to-services and goods-to-services pressure, saving-versus-consumption
    pressure, real income-minus-consumption growth, and goods/services growth
    spreads.
  - Derived 1/3/6/12-month changes and percentage changes, 3/6/12-month means,
    and 12/24/60/120-month ranks/z-scores.
- Flat screen:
  - Built 41,981 no-lookahead ES outcomes across 3,895 sessions and retained
    21,892 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 2.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 2.
- Best flat WFA-density row:
  - Twelve-month z-score of three-month real-DPI-minus-real-PCE growth at least
    `0.017194`, after a prior ES down session, long 11:00 -> 15:30.
  - early n237/PF 0.809, WFA n520/PF 1.440/MAR 5.358/average `$132.43`, core
    n105/PF 1.328, incubation n50/PF 1.438, and full n845/PF 1.330.
  - Rejection reason: good WFA/incubation shape, but early-history PF fails and
    WFA PF remains below 1.5.
- Best flat early-qualified row:
  - Three-month percentage change in durable-minus-services growth no greater
    than `-2.189166`, after a prior ES down session, long 11:00 -> 15:30.
  - early n82/PF 1.431, WFA n197/PF 2.139/MAR 9.686/average `$210.93`, core
    n40/PF 2.187, incubation n24/PF 1.238, and full n315/PF 1.796.
  - Rejection reason: too sparse for WFA, core, and incubation density.
- Managed-exit audit:
  - Took 47 loose flat specs and tested stop-first paths with stop_pct
    `0.003`/`0.004`/`0.006`/`0.008`/`0.010`/`0.012` and target R
    `1.0`/`1.5`/`2.0`/`3.0`/`4.0`.
  - Result rows: 1,392.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 5.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 106.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 37.
- Best managed WFA500/PF1.5 row:
  - Same `real_dpi_minus_pce_growth_3m_z12 >= 0.017194` prior-down long
    11:00 -> 15:30 condition, with `stop_pct=0.004` and `target_r=3.0`.
  - early n241/PF 0.860, WFA n530/PF 1.555/MAR 7.035/average `$131.81`, core
    n106/PF 1.710, incubation n52/PF 1.449, and full n862/PF 1.399.
  - Rejection reason: despite clearing WFA PF, the early-history PF gate fails
    decisively and incubation density remains below the 75-trade acceptance gate.
- Best managed early-qualified row:
  - Three-month percentage change in durable-minus-services growth no greater
    than `-2.189166`, no prior-session filter, long 11:00 -> 15:30, with
    `stop_pct=0.004` and `target_r=4.0`.
  - early n218/PF 1.201, WFA n466/PF 1.328/MAR 5.479/average `$67.97`, core
    n83/PF 1.498, incubation n74/PF 1.271, and full n790/PF 1.289.
  - Rejection reason: it repairs early history, but misses WFA PF, WFA 500-trade
    density, WFA average trade, and incubation density by one trade.
- Promotion decision: do not stage. Personal saving and consumption-pressure
  state is academically plausible and independent, but the robust-looking rows
  trade off early-history robustness against WFA PF/density. Managed exits do
  not close that gap. Do not rerun simple BEA/FRED personal saving rate, PCE,
  DPI, real DPI/PCE, PCE-to-income, durable/services consumption mix,
  saving-buffer, or consumption-pressure rank/z-score variants without BEA
  vintage validation and a materially different execution or regime structure.

## ES FRED/Z.1 Corporate Equity-Supply and Net-Payout Screen

- Why tested: this was a clean independent corporate-finance branch distinct
  from corporate profit margins, household flow/balance-sheet screens, Treasury
  curve state, NFCI/CFNAI, liquidity sweep, ES/MES flow divergence, and
  price/orderflow continuation. The thesis was equity-supply/repurchase
  pressure rather than operating profitability: high net equity issuance or weak
  net payout can proxy for unfavorable aggregate equity supply / market-timing
  pressure, while repurchases/net payout can proxy for supportive corporate
  demand. The ES translation tested contrarian long exposure after prior ES down
  sessions when equity-supply pressure states were extreme.
- Academic/source backing:
  - Boudoukh, Michaely, Richardson, and Roberts, "On the Importance of Measuring
    Payout Yield: Implications for Empirical Asset Pricing"
    (`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=480171`), supports
    measuring payout yield with repurchases as well as dividends.
  - Pontiff and Woodgate, "Share Issuance and Cross-Sectional Returns"
    (`https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2008.01335.x`),
    supports share issuance as return-relevant information.
  - Baker and Wurgler, "Market Timing and Capital Structure"
    (`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=267327`), motivates
    equity issuance as a market-timing / financing-condition state.
- Source/data:
  - FRED graph CSV mirrors of Federal Reserve Financial Accounts/Z.1 series:
    `NCBCEBQ027S` net equity issuance, `NCBEILQ027S` equity market value,
    `BOGZ1FU106121075Q` net dividends paid, `NCBDSLQ027S` debt-securities
    issuance, and `BOGZ1FA104104005Q` debt-and-loans issuance.
  - Raw cache: `/private/tmp/fred_corporate_equity_supply_raw.csv`.
  - Feature cache: `/private/tmp/fred_corporate_equity_supply_features.csv`.
  - Flat scratch paths:
    `/private/tmp/fred_corporate_equity_supply_es_screen_all.csv` and
    `/private/tmp/fred_corporate_equity_supply_es_screen_top.csv`.
  - Managed-exit scratch paths:
    `/private/tmp/fred_corporate_equity_supply_path_es_screen_all.csv` and
    `/private/tmp/fred_corporate_equity_supply_path_es_screen_top.csv`.
  - Multislot density audit paths:
    `/private/tmp/fred_corporate_equity_supply_multislot_path_es_screen_all.csv`
    and
    `/private/tmp/fred_corporate_equity_supply_multislot_path_es_screen_top.csv`.
  - Scratch scripts:
    `/private/tmp/fred_corporate_equity_supply_screen.py`,
    `/private/tmp/fred_corporate_equity_supply_path_audit.py`, and
    `/private/tmp/fred_corporate_equity_supply_multislot_audit.py`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage and no-lookahead handling:
  - Parsed 322 quarterly rows from 1945-12-31 through 2026-03-31.
  - Used a conservative quarter-end plus 90 calendar days plus one business day
    availability lag. Because FRED graph CSVs are current-history mirrors, any
    future pass would require Financial Accounts/Z.1 release-vintage validation.
- Feature set:
  - Net equity issuance, equity market value, net dividends paid,
    debt-securities issuance, debt-and-loans issuance, equity issuance to market
    value, net repurchase to market value, dividends to market value, net payout
    to market value, repurchase-to-dividends, debt-minus-equity issuance to
    market value, debt-securities-minus-equity issuance to market value,
    equity-issuance and repurchase supply shares, net payout supply share, and
    an equity-supply pressure rank composite.
  - Derived 1/2/4/8-quarter changes and percentage changes, 2/4-quarter means,
    and 8/20/40-quarter ranks/z-scores.
- Flat screen:
  - Built 41,981 no-lookahead ES outcomes across 3,895 sessions and retained
    13,774 positive/interesting diagnostic rows.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 1.
- Best flat early-qualified cluster:
  - Eight-quarter z-score of net equity issuance at least `0.538836`, after a
    prior ES down session, long 10:30 -> 15:30.
  - early n76/PF 1.016, WFA n315/PF 1.568/MAR not material enough for density,
    WFA average `$150.87`, core n96/PF 1.524, incubation n80/PF 1.656, and full
    n471/PF 1.564.
  - Rejection reason: strong split economics, but WFA density is only 315 trades
    versus the 500-trade default gate.
- Focused managed-exit audit:
  - Took 120 strongest flat specs and tested stop-first paths with stop_pct
    `0.003`/`0.004`/`0.006`/`0.008`/`0.010`/`0.012` and target R
    `1.0`/`1.5`/`2.0`/`3.0`/`4.0`.
  - Result rows: 3,115.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 16.
- Best managed row:
  - Same `net_equity_issuance_z8 >= 0.538836` prior-down long 11:00 -> 15:30
    condition, with `stop_pct=0.010` and `target_r=4.0`.
  - early n77/PF 0.973, WFA n323/PF 1.706/MAR 12.914/average `$152.88`, core
    n98/PF 1.552, incubation n83/PF 1.582, and full n483/PF 1.593.
  - Rejection reason: excellent WFA/core/incubation economics, but still below
    the 500-trade WFA density gate and slightly below early PF 1.0.
- Best managed early-qualified row:
  - Same `net_equity_issuance_z8 >= 0.538836` prior-down long 10:30 -> 15:30
    condition, with `stop_pct=0.012` and `target_r=4.0`.
  - early n77/PF 1.004, WFA n323/PF 1.535/MAR 9.120/average `$139.20`, core
    n98/PF 1.529, incubation n83/PF 1.873, and full n483/PF 1.610.
  - Rejection reason: early history is repaired and WFA PF clears 1.5, but WFA
    density remains far below 500 trades.
- Multislot density audit:
  - Tested one or two non-overlapping same-day macro-state slots over the
    strongest base conditions, with stop_pct `0.006`/`0.008`/`0.010`/`0.012`
    and target R `1.5`/`2.0`/`3.0`/`4.0`.
  - Result rows: 901.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Best multislot row used `equity_issuance_abs_supply_share_pct4 <=
    -0.369452`, prior-down long, slots `10:30-12:00` and `13:30-15:30`,
    `stop_pct=0.010`, `target_r=4.0`: early n194/PF 0.907, WFA n646/PF
    1.183/MAR 2.938/average `$50.06`, core n404/PF 1.158, incubation n95/PF
    2.225, and full n991/PF 1.274.
  - Rejection reason: density repair diluted the edge well below the WFA PF and
    WFA average-trade gates.
- Promotion decision: do not stage. Corporate equity-supply/net-payout state is
  academically clean and independent, and the single-slot prior-down
  net-equity-issuance cluster is one of the better sparse public-data
  diagnostics. It still cannot satisfy both WFA density and WFA PF after current
  ES costs. Do not rerun simple Z.1/FRED net equity issuance, repurchase,
  dividend/net-payout yield, debt-versus-equity issuance, or equity-supply
  rank/z-score variants without point-in-time Z.1 validation and a materially
  different execution signal.

## ES ICI Fund-Flow Data-Horizon Gate

- Status: rejected at the public-data horizon gate; no ES screen promoted.
- Why checked: this was a distinct investor-flow / flow-induced price-pressure
  thesis from the accepted ES/NQ trend-following systems, NAAIM/AAII survey
  sentiment, buyback calendar proxies, leveraged-ETF rebalancing, and
  macro/credit state screens. The intended mean-reversion thesis was that
  unusual equity-fund or ETF flow pressure can create temporary index-demand
  pressure that later fades.
- Academic/source backing:
  - Frazzini and Lamont, "Dumb Money: Mutual Fund Flows and the Cross-Section
    of Stock Returns" (`https://doi.org/10.1016/j.jfineco.2008.04.001`),
    supports fund-flow state as an investor-demand/sentiment variable.
  - Coval and Stafford, "Asset Fire Sales (and Purchases) in Equity Markets"
    (`https://doi.org/10.1016/j.jfineco.2006.09.007`), supports flow-induced
    price pressure and reversal logic.
  - Official ICI weekly flow pages:
    `https://www.ici.org/research/stats/flows`,
    `https://www.ici.org/research/stats/combined_flows`, and
    `https://www.ici.org/research/stats/etf_flows`.
- Data audit:
  - Current short URLs such as `https://www.ici.org/flows_data_2025.xls` redirect
    to the current 2026 workbook, so they are unsafe as historical source paths.
  - Year-specific public paths under `/system/files/YYYY-01/` were reachable for
    2022-2026, but only exposed a handful of estimated weekly rows per year:
    mutual-fund rows totaled 28 dates, combined mutual-fund/ETF rows 26 dates,
    and ETF rows 22 dates.
  - Scratch cache: `/private/tmp/ici_weekly_flow_raw_2022_2026.csv`, with only
    76 total kind/date rows from 2022-07-06 through 2026-06-03.
- Promotion decision: do not screen or stage from this public route. The source
  family is academically clean, but the accessible official ICI weekly files are
  not a continuous enough historical panel for ES WFA/core/incubation testing.
  Do not reopen as simple ICI equity-fund flow, ETF issuance flow, combined
  equity-flow, bond-vs-equity flow, or fund-flow pressure unless a continuous
  point-in-time historical ICI feed or licensed equivalent is available.

## ES NAAIM Active-Manager Exposure Screen

- Status: rejected before staged implementation.
- Why tested: this was a public weekly active-manager positioning/crowding
  source distinct from AAII retail survey, Michigan/SCE/NFIB sentiment,
  Wikimedia attention, Cboe option-volume sentiment, FINRA short-sale pressure,
  ICI flow data, and price/orderflow continuation. The mean-reversion thesis was
  that unusually high or fast-changing active-manager equity exposure may proxy
  for crowded risk-on positioning, while unusually low exposure may proxy for
  de-risking pressure and future relief.
- Academic/source backing:
  - Brown and Cliff, "Investor Sentiment and the Near-Term Stock Market"
    (`https://doi.org/10.1016/j.jempfin.2002.12.001`), supports survey
    sentiment as a market-timing state.
  - Baker and Wurgler, "Investor Sentiment and the Cross-Section of Stock
    Returns" (`https://doi.org/10.1111/j.1540-6261.2006.00885.x`), supports
    investor sentiment/crowding variables.
  - Source page and workbook:
    `https://naaim.org/programs/naaim-exposure-index/` and
    `https://naaim.org/wp-content/uploads/2026/06/USE_Data-since-Inception_2026-06-10.xlsx`.
- Source/data:
  - Downloaded workbook:
    `/private/tmp/naaim_use_data_since_inception_20260610.xlsx`.
  - Parsed raw cache:
    `/private/tmp/naaim_exposure_since_inception_20260610.csv`.
  - Parsed 1,042 rows from 2006-07-05 through 2026-06-10, with one duplicate
    first date; feature build used 1,040 date rows.
  - Feature cache: `/private/tmp/naaim_exposure_features.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - No-lookahead handling made each NAAIM row eligible from the next business
    day after the survey date; any future pass would still require a release
    timestamp audit.
- Flat screen:
  - Built mean exposure, NAAIM number, bearish/bullish extremes, quartiles,
    survey dispersion, interquartile spreads, mean-minus-median pressure, and
    1/2/4/8/13/26-week changes plus 4/13/26-week means and 13/26/52/104-week
    ranks/z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/naaim_exposure_es_screen_all.csv` and
    `/private/tmp/naaim_exposure_es_screen_top.csv`.
  - Outcomes: 41,981 no-lookahead rows across 3,895 ES sessions.
  - Retained result rows: 17,594.
  - Pass-like rows: 0.
  - Near-like rows: 2.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 2.
- Best flat diagnostic:
  - High 13-week NAAIM exposure z-score, `mean_average_z13 >= 1.096252`, long
    10:30 -> 15:59 with no prior-session filter.
  - early n172/PF 1.255, WFA n484/PF 1.401/MAR 7.871/average `$106.80`, core
    n88/PF 1.273, incubation n64/PF 1.278, and full n756/PF 1.364/net
    `$64,795`.
  - Rejection reason: it is a loose near row but misses the hard 500-trade WFA
    density gate and the 75-trade incubation gate; it is also risk-on
    continuation-shaped rather than the desired mean-reversion expression.
- Focused path audit:
  - Took the two loose near rows plus density-qualified rows with early n >= 75,
    WFA n >= 500, core n >= 50, incubation n >= 75, and WFA PF >= 1.15.
  - Tested stop-first paths with stop_pct
    `0.003`/`0.004`/`0.006`/`0.008`/`0.010`/`0.012` and target R
    `1.0`/`1.5`/`2.0`/`3.0`/`4.0`.
  - Result paths: `/private/tmp/naaim_exposure_path_es_screen_all.csv` and
    `/private/tmp/naaim_exposure_path_es_screen_top.csv`.
  - Candidate specs: 90; retained path rows: 2,147.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Best path row was `q3_minus_q1_chg26 >= -0.25`, prior-down long
    10:30 -> 15:30, `stop_pct=0.012`, `target_r=4.0`: early n216/PF 1.044,
    WFA n542/PF 1.200/MAR 2.813/average `$81.16`, core n132/PF 1.294,
    incubation n78/PF 2.059, and full n860/PF 1.313/net `$95,091.25`.
- Promotion decision: do not stage. NAAIM exposure state is a clean
  investor-positioning source and produced a useful loose diagnostic, but it
  cannot clear WFA PF/density and incubation gates after current ES costs.
  Stop/target management diluted the strongest flat rows. Do not rerun simple
  NAAIM mean exposure, NAAIM number, quartile/dispersion, exposure change,
  exposure rank/z-score, or active-manager crowding variants without materially
  different source structure or an execution signal that is not just a weekly
  survey state.

## ES Monetary-Liquidity / Bank-Credit Creation Screen

- Why tested: after the quote/depth liquidity-sweep branch remained data-gated,
  this was the next no-cost public liquidity-supply source that was still
  meaningfully different from ES/NQ trend continuation, price-only reversion,
  investor-positioning surveys, Fed financial-stress indexes, RRP plumbing, and
  corporate/household balance-sheet screens. The edge thesis was that monetary
  expansion/contraction, deposit funding, and bank-credit creation can proxy for
  intermediary balance-sheet capacity and risk-taking state; after adverse ES
  movement, easier liquidity/credit conditions might support intraday
  mean-reversion.
- Academic backing:
  - Adrian and Shin, "Liquidity and Leverage", support broker/dealer and
    intermediary balance-sheet liquidity as a risk-capacity state variable.
  - Adrian, Etula, and Muir, "Financial Intermediaries and the Cross-Section of
    Asset Returns", support intermediary leverage/capital as an asset-pricing
    state.
  - Brunnermeier and Pedersen, "Market Liquidity and Funding Liquidity",
    motivate funding-liquidity constraints as a driver of temporary price
    pressure and risk capacity.
- Source/data:
  - FRED current-history graph CSV mirrors:
    `WM2NS`, `M2SL`, `DPSACBW027SBOG`, `TOTLL`, `BUSLOANS`, `CONSUMER`, and
    `CCLACBW027SBOG`.
  - Raw cache: `/private/tmp/fred_monetary_liquidity_raw.csv`.
  - Feature cache: `/private/tmp/fred_monetary_liquidity_features.csv`.
  - Scratch scripts: `/private/tmp/fred_monetary_liquidity_screen.py` and
    `/private/tmp/fred_monetary_liquidity_path_audit.py`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Parsed source coverage:
    - `WM2NS`: 2,366 weekly rows, 1981-01-05 through 2026-05-04.
    - `M2SL`: 808 monthly rows, 1959-01-01 through 2026-04-01.
    - `DPSACBW027SBOG`: 2,788 weekly rows, 1973-01-03 through 2026-06-03.
    - `TOTLL`: 2,788 weekly rows, 1973-01-03 through 2026-06-03.
    - `BUSLOANS`: 953 rows, 1947-01-01 through 2026-05-01.
    - `CONSUMER`: 953 rows, 1947-01-01 through 2026-05-01.
    - `CCLACBW027SBOG`: 1,354 weekly rows, 2000-06-28 through 2026-06-03.
  - No-lookahead handling used source date plus seven calendar days plus one
    business day for weekly/bank series, and month-end plus 45 calendar days
    plus one business day for monthly M2. Because the data came from FRED
    current-history mirrors, any future pass would still require
    release/vintage validation.
- Flat screen:
  - Built M2 weekly/monthly, deposits, total loans and leases, business loans,
    consumer loans, credit-card loans, bank liquidity gap, loan/deposit ratio,
    loan-share features, M2/deposit ratio, M2-minus-bank-credit, and
    1/4/13/26/52-period changes, pct changes, means, ranks, and z-scores.
  - Tested long/short ES flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59, with optional previous-completed-session up/down
    filters and current ES round-turn cost assumptions.
  - Result paths: `/private/tmp/fred_monetary_liquidity_es_screen_all.csv` and
    `/private/tmp/fred_monetary_liquidity_es_screen_top.csv`.
  - Outcomes: 41,981 no-lookahead rows across 3,895 ES sessions.
  - Retained result rows: 19,570.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 1.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best flat diagnostics:
  - Only WFA500/PF1.4 row: `m2_minus_bank_credit_chg4 <= -61.5918`, no prior
    filter, long 13:30 -> 15:30. It had early n149/PF 0.523, WFA n516/PF
    1.414/MAR 6.984/average `$86.25`, core n128/PF 1.711, incubation n90/PF
    1.154, and full n759/PF 1.269/net `$39,930`. Rejected because early history
    and incubation PF fail.
  - Best early-qualified managed-shape flat row was
    `loan_deposit_ratio_chg4 >= 0.002976`, no prior filter, long
    11:00 -> 15:30: early n86/PF 1.223, WFA n272/PF 1.624/MAR 5.105/average
    `$227.35`, core n102/PF 1.739, incubation n17/PF 2.081, and full n383/PF
    1.625/net `$72,772.50`. Rejected because 2025-2026 density is far too low.
- Focused path audit:
  - Took the strongest 61 flat specs across WFA-density, WFA/incubation shape,
    and early-qualified rows.
  - Tested stop-first paths with stop_pct
    `0.003`/`0.004`/`0.006`/`0.008`/`0.010`/`0.012` and target R
    `1.0`/`1.5`/`2.0`/`3.0`/`4.0`.
  - Result paths:
    `/private/tmp/fred_monetary_liquidity_path_es_screen_all.csv` and
    `/private/tmp/fred_monetary_liquidity_path_es_screen_top.csv`.
  - Retained path rows: 1,677.
  - Pass-like rows: 0.
  - Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 9, all with early PF below 1.0.
  - Best WFA/incubation-shaped path row was
    `consumer_loan_share_chg26 <= -0.000729`, no prior filter, long
    13:30 -> 15:59, `stop_pct=0.012`, `target_r=4.0`: early n410/PF 0.720,
    WFA n417/PF 1.431/MAR 4.935/average `$105.03`, core n71/PF 2.417,
    incubation n231/PF 1.211, and full n1,138/PF 1.202/net `$49,705.80`.
    Rejected because early history is materially loss-making.
  - Best early-qualified managed row was `loan_deposit_ratio_chg4 >= 0.002976`,
    no prior filter, long 11:00 -> 15:59, `stop_pct=0.004`, `target_r=3.0`:
    early n89/PF 1.127, WFA n280/PF 1.521/MAR 4.858/average `$166.30`,
    core n105/PF 1.805, incubation n17/PF 2.339, and full n394/PF 1.550/net
    `$59,889.20`. Rejected because WFA density and incubation density are both
    too low.
- Promotion decision: do not stage. Monetary-liquidity and bank-credit creation
  are academically defensible and distinct, but the simple ES intraday
  translation trades off early-history robustness against WFA/incubation
  density. Managed exits do not close the gap. Do not rerun simple M2, deposit,
  bank-credit, loan/deposit, M2-minus-credit, consumer-loan-share, credit-card
  loan, or bank-liquidity rank/z-score variants without release/vintage
  validation and a materially different execution signal.

## ES House-Price / Collateral-Cycle Screen

- Status: rejected before staged implementation after flat-hold and focused
  managed-exit audits.
- Why tested: this was a no-cost public housing-wealth/collateral-cycle source
  distinct from the earlier housing-activity screen based on starts, permits,
  sales, months supply, and mortgage rates, and distinct from household
  balance-sheet stocks. The mean-reversion thesis was that weak or stretched
  house-price/collateral states can alter household risk capacity and create
  transient equity-index risk premia after adverse ES moves.
- Academic/source backing:
  - Housing collateral and household balance-sheet research, including
    Mian-Sufi style household leverage/collateral-cycle evidence and Case-Shiller
    housing-market literature, motivates house-price state as a risk-capacity
    and wealth-effect variable.
  - FRED current-history graph CSV mirrors were used for S&P CoreLogic
    Case-Shiller, FHFA, and Census new-home price series:
    `CSUSHPINSA`, `CSUSHPISA`, `HPIPONM226S`, `USPHCI`, `USSTHPI`, `MSPUS`,
    and `ASPUS`.
- Source/data:
  - Scratch script: `/private/tmp/fred_house_price_collateral_screen.py`.
  - Raw cache: `/private/tmp/fred_house_price_collateral_raw.csv`.
  - Feature cache: `/private/tmp/fred_house_price_collateral_features.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Monthly coverage included Case-Shiller national NSA/SA from 1987-01 through
    2026-03, FHFA purchase-only from 1991-01 through 2026-03, and FHFA
    conventional-mortgage price data from 1979-01 through 2026-04. Quarterly
    coverage included FHFA all-transactions from 1975-Q1 through 2026-Q1 and
    Census median/average new-home sale prices from 1963-Q1 through 2026-Q1.
  - No-lookahead handling used month-end plus 45 calendar days plus one
    business day for monthly series, and quarter-end plus 90 calendar days plus
    one business day for quarterly series. Because the inputs are FRED
    current-history mirrors, any future pass would still require release/vintage
    validation from the original publishers.
- Flat screen:
  - Built levels, drawdown-from-high, 1/3/6/12-month or 1/2/4/8-quarter changes,
    percentage changes, accelerations, mean deviations, ranks, momentum ranks,
    and z-scores, then tested ES long/short flat holds from
    09:35/10:30/11:00/13:30 to 12:00/15:30/15:59 with optional prior-session
    direction filters.
  - Result paths:
    `/private/tmp/fred_house_price_collateral_es_screen_all.csv` and
    `/private/tmp/fred_house_price_collateral_es_screen_top.csv`.
  - Raw rows: 2,644. No-lookahead outcomes: 41,981. Retained diagnostic rows:
    22,371.
  - Pass-like rows: 0. Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 1.
- Best flat diagnostics:
  - Best WFA-density row: `case_shiller_us_nsa_chg6 <= 7.99`, prior-down long
    11:00 -> 15:59, had early n327/PF 0.881/net `-$7,410`, WFA n662/PF
    1.278/MAR 3.043/average `$89.52`, core n19/PF 1.272, incubation n135/PF
    1.366, and full n1,179/PF 1.226/net `$85,767.50`. Rejected because early
    history and core density fail.
  - Best early-qualified flat row: `case_shiller_us_nsa_chg1 <= -0.262`,
    prior-down long 13:30 -> 15:59, had early n104/PF 1.281, WFA n140/PF
    1.518/MAR 1.761, core n45/PF 1.091, incubation n85/PF 1.494, and full
    n345/PF 1.463. Rejected because WFA and core density are too low.
  - The only loose WFA/incubation-shaped flat row,
    `case_shiller_us_nsa_pct6 <= 0.023815`, prior-down long 11:00 -> 15:59,
    had early n229/PF 0.732/net `-$11,632.50`, WFA n433/PF 1.439/average
    `$147.14`, core n19/PF 1.272, incubation n125/PF 1.395, and full n842/PF
    1.302. Rejected because early history is loss-making and core density fails.
- Focused path audit:
  - Scratch script: `/private/tmp/fred_house_price_collateral_path_audit.py`.
  - Result paths:
    `/private/tmp/fred_house_price_collateral_path_es_screen_all.csv` and
    `/private/tmp/fred_house_price_collateral_path_es_screen_top.csv`.
  - Took 90 strongest flat specs and tested stop-first paths with stop_pct
    `0.003`/`0.004`/`0.006`/`0.008`/`0.010`/`0.012` and target R
    `1.0`/`1.5`/`2.0`/`3.0`/`4.0`.
  - Retained path rows: 2,562.
  - Pass-like rows: 0. Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 19, all still failing early-history and/or core-density/core-PF
    requirements.
  - Best WFA-density path row:
    `case_shiller_us_sa_mom_rank24 <= 0.5`, prior-down long 11:00 -> 15:59,
    `stop_pct=0.008`, `target_r=4.0`, had early n171/PF 0.903, WFA n595/PF
    1.351/MAR 6.001/average `$110.46`, core n89/PF 1.538, incubation n84/PF
    1.171, and full n881/PF 1.260. Rejected because early history,
    incubation PF, and WFA PF fail.
  - Best loose managed row:
    `case_shiller_us_nsa_pct6 <= 0.023815`, prior-down long 11:00 -> 15:59,
    `stop_pct=0.008`, `target_r=1.5`, had early n224/PF 0.700/net
    `-$11,902.80`, WFA n441/PF 1.518/MAR 7.006/average `$140.76`, core n19/PF
    0.695, incubation n130/PF 1.293, and full n851/PF 1.290. Rejected because
    early history and core coverage/economics fail despite WFA PF.
- Promotion decision: do not stage. House-price/collateral-cycle state is
  academically defensible and independent, but the simple ES intraday
  translation either over-filters into sparse WFA/core samples or has
  loss-making early history. Managed exits do not close the gap. Do not rerun
  simple Case-Shiller, FHFA house-price index, new-home sale price,
  house-price momentum, house-price drawdown, or house-price rank/z-score
  variants without point-in-time source validation and materially different
  execution structure.

## ES Business-Formation / Firm-Creation Screen

- Status: rejected before staged implementation after the flat-hold screen.
  No path audit was run because the flat screen had zero pass-like rows, zero
  near-like rows, zero WFA-density rows, and zero loose WFA/incubation-shaped
  rows.
- Why tested: this was a no-cost official firm-entry/business-dynamism source
  distinct from NFIB, SCE, WEI, CFNAI, retail sales, JOLTS, household balance
  sheets, and ES/NQ price/orderflow trend following. The mean-reversion thesis
  was that firm-creation pressure, high-propensity applications, and changes in
  the high-propensity share can proxy for business dynamism and risk-capacity
  state; after adverse ES movement, stronger firm-entry state might support
  intraday reversal.
- Academic/source backing:
  - Business-dynamism and firm-entry literature, including Akcigit and Ates
    style declining-business-dynamism work, motivates firm creation as a
    macroeconomic state variable tied to competition, innovation, and growth.
  - Production-based and entry-based asset-pricing research, including
    Kogan/Papanikolaou firm-investment asset-pricing surveys and Loualiche-style
    entry/imperfect-competition asset-pricing work, motivates entry shocks and
    investment opportunities as risk-premium state variables.
  - U.S. Census Business Formation Statistics and FRED document business
    applications and high-propensity business applications as timely measures of
    applications for new businesses and applications likely to become employer
    firms:
    `https://www.census.gov/econ/bfs/index.html`,
    `https://fred.stlouisfed.org/release?rid=443`,
    `https://fred.stlouisfed.org/series/BABATOTALSAUS`,
    `https://fred.stlouisfed.org/series/BABATOTALNSAUS`,
    `https://fred.stlouisfed.org/series/BAHBATOTALSAUS`, and
    `https://fred.stlouisfed.org/series/BAHBATOTALNSAUS`.
- Source/data:
  - Scratch script: `/private/tmp/fred_business_formation_screen.py`.
  - Raw cache: `/private/tmp/fred_business_formation_raw.csv`.
  - Feature cache: `/private/tmp/fred_business_formation_features.csv`.
  - Result paths: `/private/tmp/fred_business_formation_es_screen_all.csv` and
    `/private/tmp/fred_business_formation_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Parsed 263 monthly source rows from 2004-07-31 through 2026-05-31 using
    FRED current-history graph CSV mirrors of total business applications and
    high-propensity business applications, both seasonally adjusted and not
    seasonally adjusted.
  - No-lookahead handling used source month-end plus 45 calendar days plus one
    business day. Because the data came from current-history FRED mirrors, any
    future pass would still require Census/FRED release or vintage validation.
- Flat screen:
  - Built total and high-propensity application levels, high-propensity share,
    low-propensity applications, high-minus-low propensity pressure, SA/NSA
    gaps, 3-month and 12-month high-propensity growth gaps, and 1/3/6/12-month
    changes, percentage changes, accelerations, means, ranks, momentum ranks,
    and z-scores.
  - Tested ES long/short flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59 with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - No-lookahead outcomes: 41,981.
  - Retained diagnostic rows: 66,072.
  - Pass-like rows: 0. Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best diagnostics:
  - Top score row was `high_propensity_growth_gap_12m_chg1 <= -0.020460`,
    prior-up long 11:00 -> 12:00: early n49/PF 0.926, WFA n115/PF 1.176,
    core n12/PF 79.286, incubation n70/PF 0.898, and full n234/PF 1.006.
    Rejected because WFA/core density and incubation economics fail.
  - Best visible WFA-PF rows were also sparse or failed incubation. For example
    `high_propensity_business_applications_sa_mom_rank12 <= 0.166667`,
    prior-down long 11:00 -> 12:00, had early n72/PF 0.311, WFA n140/PF
    1.592, core n10/PF 23.095, incubation n28/PF 1.072, and full n248/PF
    1.100; `business_applications_total_sa_z24 <= -0.562578`, prior-down long
    11:00 -> 12:00, had early n39/PF 0.656, WFA n118/PF 1.543, core n10/PF
    23.095, incubation n18/PF 0.931, and full n175/PF 1.274.
- Promotion decision: do not stage. Business formation and firm-entry state are
  academically defensible and independent, but the ES intraday translation has
  no dense WFA candidate and no loose early/WFA/incubation shape. Do not rerun
  simple business applications, high-propensity applications,
  high-propensity-share, low-propensity applications, firm-creation momentum,
  acceleration, rank, or z-score variants without point-in-time source
  validation and materially different execution structure.

## ES Inventory-Cycle / Orders-Backlog Screen

- Status: rejected before staged implementation after the flat-hold screen. No
  path audit was run because the flat screen had zero pass-like rows, zero
  near-like rows, zero WFA-density rows, and zero loose WFA/incubation-shaped
  rows.
- Why tested: this was a no-cost official inventory-cycle and real-demand
  imbalance source distinct from NFIB inventory expectations, GDPNow component
  nowcasts, broad INDPRO/payroll real-activity screens, retail-sales demand,
  business formation, and price/orderflow continuation. The mean-reversion
  thesis was that inventory overhang, order-backlog pressure, and new-order
  momentum can proxy for cyclical production/sales imbalance; after adverse ES
  movement, benign or improving inventory/order state might support intraday
  reversal.
- Academic/source backing:
  - Blinder and Maccini, "Taking Stock: A Critical Assessment of Recent Research
    on Inventories", and Ramey and West, "Inventories", support inventories and
    inventory-to-sales dynamics as first-order business-cycle state variables.
  - FRED current-history graph CSV mirrors were used for Census manufacturing,
    trade, and inventory/order series:
    `https://fred.stlouisfed.org/series/ISRATIO`,
    `https://fred.stlouisfed.org/series/BUSINV`,
    `https://fred.stlouisfed.org/series/MNFCTRIRSA`,
    `https://fred.stlouisfed.org/series/RETAILIRSA`,
    `https://fred.stlouisfed.org/series/WHLSLRIRSA`,
    `https://fred.stlouisfed.org/series/AMTMNO`,
    `https://fred.stlouisfed.org/series/AMTMUO`,
    `https://fred.stlouisfed.org/series/AMTMVS`,
    `https://fred.stlouisfed.org/series/DGORDER`, and
    `https://fred.stlouisfed.org/series/NEWORDER`.
- Source/data:
  - Scratch script: `/private/tmp/fred_inventory_cycle_screen.py`.
  - Raw cache: `/private/tmp/fred_inventory_cycle_raw.csv`.
  - Feature cache: `/private/tmp/fred_inventory_cycle_features.csv`.
  - Result paths: `/private/tmp/fred_inventory_cycle_es_screen_all.csv` and
    `/private/tmp/fred_inventory_cycle_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Parsed 412 monthly source rows from 1992-01-31 through 2026-04-30.
  - No-lookahead handling used source month-end plus 45 calendar days plus one
    business day. Because the data came from current-history FRED mirrors, any
    future pass would still require Census/FRED release or vintage validation.
- Flat screen:
  - Built inventory-to-sales ratios, total business inventories, manufacturers'
    new orders, unfilled orders, shipments, durable goods orders, nondefense
    capital-goods orders, new-orders-to-shipments, unfilled-to-shipments,
    unfilled-to-new-orders, durable/capex orders-to-shipments, new-orders-minus
    shipments, durable-minus-capex orders, average inventory-overhang ratios,
    sector inventory-ratio spreads, order-backlog pressure, and 1/3/6/12-month
    changes, percentage changes, accelerations, means, ranks, momentum ranks,
    and z-scores.
  - Tested ES long/short flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59 with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - No-lookahead outcomes: 41,981.
  - Retained diagnostic rows: 81,198.
  - Pass-like rows: 0. Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best diagnostics:
  - Top score row was `durable_minus_capex_orders_pct_from_mean3 >= 0.026906`,
    prior-up long 11:00 -> 12:00: early n146/PF 0.635, WFA n232/PF 1.179,
    core n19/PF 159.25, incubation n32/PF 1.249, and full n421/PF 1.077.
    Rejected because early history is loss-making and WFA/core/incubation
    density fails.
  - The best visible new-order momentum rows were also sparse or weak. For
    example `manufacturer_new_orders_mom_rank120 >= 0.90`, prior-up long
    11:00 -> 12:00, had early n64/PF 1.018, WFA n121/PF 1.270, core n12/PF
    79.286, incubation n32/PF 1.249, and full n228/PF 1.219; it fails early,
    WFA, core, and incubation density.
- Promotion decision: do not stage. Inventory-cycle and orders-backlog state are
  academically defensible and independent enough to test, but the ES intraday
  translation has no dense WFA candidate and no loose early/WFA/incubation
  shape. Do not rerun simple inventories, inventory-to-sales ratios,
  manufacturer/retail/wholesale inventory pressure, new orders, unfilled
  orders, shipments, durable-goods orders, nondefense-capex orders,
  order-backlog pressure, or inventory-cycle rank/z-score variants without
  point-in-time source validation and materially different execution structure.

## ES Capacity-Utilization / Resource-Slack Screen

- Status: rejected before staged implementation after the flat-hold screen. No
  path audit was run because the flat screen had zero pass-like rows, zero
  near-like rows, zero WFA-density rows, and zero loose WFA/incubation-shaped
  rows.
- Why tested: this was a no-cost official resource-slack source distinct from
  the prior broad INDPRO/payroll/unemployment monthly macro-state screen,
  inventory-cycle/orders-backlog, CFNAI, WEI, GDPNow, and price/orderflow
  continuation. The mean-reversion thesis was that capacity utilization and
  sector slack proxy for output-gap/risk-premium state; after adverse ES
  movement, high slack or improving utilization might support intraday reversal.
- Academic/source backing:
  - Cooper and Priestley, "Time-Varying Risk Premiums and the Output Gap",
    motivate output-gap/resource-utilization state as a time-varying risk-premium
    variable.
  - FRED current-history graph CSV mirrors were used for Federal Reserve G.17
    capacity-utilization series:
    `https://fred.stlouisfed.org/series/TCU`,
    `https://fred.stlouisfed.org/series/MCUMFN`, and
    `https://fred.stlouisfed.org/series/CAPUTLG2211S`.
- Source/data:
  - Scratch script: `/private/tmp/fred_capacity_utilization_screen.py`.
  - Raw cache: `/private/tmp/fred_capacity_utilization_raw.csv`.
  - Feature cache: `/private/tmp/fred_capacity_utilization_features.csv`.
  - Result paths: `/private/tmp/fred_capacity_utilization_es_screen_all.csv` and
    `/private/tmp/fred_capacity_utilization_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Parsed 712 monthly source rows from 1967-01-31 through 2026-04-30. Total
    industry and utilities utilization cover the full range; manufacturing
    utilization covers 652 rows from 1972-01-31 through 2026-04-30.
  - No-lookahead handling used source month-end plus 45 calendar days plus one
    business day. Because the data came from current-history FRED mirrors, any
    future pass would still require Federal Reserve release or vintage
    validation.
- Flat screen:
  - Built total, manufacturing, and utilities capacity utilization; slack
    variants; manufacturing/utility spreads versus total; average utilization;
    utilization dispersion; average slack; sector slack spreads; and 1/3/6/12
    month changes, percentage changes, accelerations, means, ranks, momentum
    ranks, and z-scores.
  - Tested ES long/short flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59 with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - No-lookahead outcomes: 41,981.
  - Retained diagnostic rows: 59,780.
  - Pass-like rows: 0. Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best diagnostics:
  - Top score rows were 12-month total-utilization deterioration after a prior
    down ES session, long 09:35 -> 12:00. `total_capacity_utilization_chg12 <=
    -1.0921` had early n0, WFA n509/PF 0.973/average `-$8.73`, core n31/PF
    0.944, incubation n12/PF 15.960, and full n521/PF 1.024. Rejected because
    early history is absent, WFA/core economics fail, and incubation is tiny.
  - The best visible slack-from-mean row,
    `total_capacity_utilization_from_mean6 <= -0.714867`, prior-down long
    09:35 -> 12:00, had early n0, WFA n164/PF 1.077, core n11/PF 0.968,
    incubation n12/PF 15.960, and full n176/PF 1.232. Rejected because all
    robust split-density gates fail.
- Promotion decision: do not stage. Capacity utilization and resource slack are
  academically defensible and independent enough to test, but the simple ES
  intraday translation has no dense WFA candidate, no early-history coverage in
  the apparent high-score rows, and no loose early/WFA/incubation shape. Do not
  rerun simple total/manufacturing/utilities capacity utilization, slack,
  utilization spread, utilization dispersion, utilization momentum, rank, or
  z-score variants without point-in-time source validation and materially
  different execution structure.

## ES OECD Composite Leading Indicator Screen

- Status: rejected before staged implementation after a flat-hold screen.
- Why tested: this was a public business-cycle timing source distinct from
  CFNAI/WEI/GDPNow, capacity utilization, inventory/orders, business formation,
  price-only liquidity sweeps, ES/MES divergence, and accepted Sierra
  orderflow-continuation mechanics. The intended mean-reversion expression was
  that late-cycle/early-cycle leading-indicator states can proxy for changing
  risk appetite and macro risk premia, which might condition same-session ES
  reversal or relief behavior after a prior up/down session.
- Academic/source backing:
  - Stock and Watson, "New Indexes of Coincident and Leading Economic
    Indicators", motivate composite leading/coincident indicators as
    business-cycle timing state variables.
  - Estrella and Mishkin, "Predicting U.S. Recessions: Financial Variables as
    Leading Indicators", motivate leading-indicator state as recession/risk
    timing information.
  - FRED current-history graph CSV mirror was used for OECD amplitude-adjusted
    U.S. CLI `USALOLITOAASTSAM`
    (`https://fred.stlouisfed.org/series/USALOLITOAASTSAM`).
- Source/data:
  - Scratch script: `/private/tmp/fred_oecd_leading_indicator_screen.py`.
  - Raw cache: `/private/tmp/fred_oecd_leading_indicator_raw.csv`.
  - Feature cache: `/private/tmp/fred_oecd_leading_indicator_features.csv`.
  - Result paths:
    `/private/tmp/fred_oecd_leading_indicator_es_screen_all.csv` and
    `/private/tmp/fred_oecd_leading_indicator_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
  - Parsed 856 monthly OECD CLI rows from 1955-01-31 through 2026-04-30.
  - No-lookahead handling used source month-end plus 45 calendar days plus one
    business day; for example the 2026-04-30 source month became eligible on
    2026-06-15, outside the current ES cache ending 2026-05-29. Because the
    data came from a current-history FRED mirror, any future pass would still
    require OECD/FRED release or vintage validation.
- Flat screen:
  - Built the amplitude-adjusted CLI, gap from 100, absolute gap from 100,
    below/above-100 flags, recovery and overheat pressure, and 1/3/6/12-month
    changes, percentage changes, accelerations, 3/6/12-month means and
    deviations, and 12/24/60/120-month ranks, momentum ranks, and z-scores.
  - Tested ES long/short flat holds from 09:35/10:30/11:00/13:30 to
    12:00/15:30/15:59 with optional previous-completed-session up/down filters
    and current ES round-turn cost assumptions.
  - No-lookahead outcomes: 41,981.
  - Retained diagnostic rows: 20,959.
  - Pass-like rows: 0. Near-like rows: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.5: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.4: 0.
  - Rows with WFA n >= 500 and WFA PF >= 1.3: 0.
  - Rows with WFA n >= 400, WFA PF >= 1.4, incubation n >= 50, and incubation
    PF >= 1.2: 0.
- Best diagnostics:
  - Top score row was `oecd_cli_abs_gap_from_100_mean3 <= 0.247735`,
    prior-down long 11:00 -> 12:00: early n115/PF 0.496, WFA n140/PF 1.040,
    core n10/PF 23.095, incubation n90/PF 1.421, and full n345/PF 1.099.
    Rejected because WFA density/economics fail and the apparent core PF comes
    from only 10 trades.
  - Best dense WFA row was `oecd_cli_recovery_pressure_pct3 >= -0.727384`,
    prior-down long 11:00 -> 15:59: early n119/PF 0.912, WFA n563/PF 1.269,
    core n21/PF 1.368, incubation n67/PF 1.034, and full n804/PF 1.199.
    Rejected because WFA PF, core density, and incubation PF miss.
  - Best WFA400/incubation-shaped row was `oecd_cli_below_100_z12 <=
    1.732051`, prior-down long 11:00 -> 15:30: early n255/PF 0.710, WFA
    n427/PF 1.323, core n124/PF 1.286, incubation n51/PF 1.330, and full
    n733/PF 1.187. Rejected because early-history economics fail and WFA PF is
    well below the near threshold.
- Promotion decision: do not stage. OECD CLI/business-cycle turning-point state
  is independent and academically defensible, but the simple ES intraday
  translation is diluted below WFA PF and fails early-history robustness. Do not
  rerun simple OECD CLI level, gap-from-100, recovery/overheat pressure,
  leading-indicator momentum, rank, or z-score variants without point-in-time
  source validation and materially different execution structure.

## Current ES Independent Mean-Reversion Checkpoint

- The ICI data-horizon gate, NAAIM active-manager exposure screen,
  monetary-liquidity/bank-credit screen, house-price/collateral-cycle screen,
  business-formation/firm-creation screen, and inventory-cycle/orders-backlog
  screen, capacity-utilization/resource-slack screen, and OECD
  leading-indicator screen add more public no-cost branches to the rejected
  list. They did not displace the current best independent mean-reversion lead.
- Current best non-depth lead remains
  `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
  with the caveat that the local ES+MES `trades` history is only about one year
  and cannot prove standard WFA density. Promotion requires longer ES+MES
  `trades` history or an explicit short-history policy exception before rerun.
  A 2026-06-14 engine-timing robustness audit reproduced the primary staged row
  exactly and found two nearby split/month/cost-supportive rows, but the exact
  row's positive-month rate was only `58.3%`; keep this as purchase-supporting
  evidence, not acceptance.
- Current best liquidity-sweep path remains the bounded one-year ES `tbbo` pilot
  described above. Do not rerun price-only sweep/reclaim, opening-range
  failed-break fade, or trade-side-only sweep/fade families; those are rejected.
- The ES `tbbo` pilot is now scaffolded but still data-gated: added
  `src/propstack/data/tbbo_liquidity.py`,
  `src/propstack/build_tbbo_liquidity_cache.py`,
  `src/propstack/strategy_modules/entry/quote_liquidity_sweep_reversion.py`,
  `configs/campaigns/quote_liquidity_sweep_reversion/variants/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim.yaml`,
  and `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
  Focused synthetic verification passed with
  `PYTHONPATH=src pytest -q tests/test_quote_liquidity_sweep_reversion.py`
  (`4 passed`). No quote/depth data has been downloaded, and this is not a
  live-eligible result.
- 2026-06-14 metadata-only refresh for the scaffolded `tbbo` pilot wrote
  `research_artifacts/databento_es_tbbo_20250609_20260609_cost_manifest_20260614.json`.
  Databento reported `262/262` RTH sessions available for `GLBX.MDP3` /
  `ES.FUT` from `2025-06-09` through `2026-06-09`. An 8-session sample estimated
  one-year RTH `tbbo` size at `8.08 GB` and sampled cost at `$14.88`; the same
  sample shape for `mbp-1` estimated `159.85 GB` and `$19.81`. Cost output is
  caveated because only `1/8` sampled sessions had nonzero quoted cost despite
  all sampled sessions having nonzero billable size. The size result still
  confirms `tbbo` is the correct first pilot schema versus `mbp-1`.
- The 2020-start ES+MES `trades` data gate for the primary ES/MES flow-divergence
  branch now has a durable combined manifest:
  `research_artifacts/databento_es_mes_trades_20200101_20260609_cost_manifest_20260614.json`.
  The metadata-only estimate used 24 sampled sessions per symbol over 1,680 RTH
  sessions from 2020-01-01 through 2026-06-09: ES estimated `$554.49`, MES
  estimated `$394.85`, combined `$949.34`. No paid files were downloaded; rerun a
  final metadata check before any approved download.
- Additional same-turn source rechecks did not produce a better no-cost public
  lane: Moody `BAA10Y`/`AAA10Y` FRED graph downloads still timed out, ICE BofA
  OAS graph CSVs still started only in 2023, the guessed ISM/PMI FRED IDs
  returned 404, and EIA petroleum inventory state is already rejected in the
  ledger as both event-day and forward-filled weekly state.
- Credit/default-spread retry detail: the FRED `BAA10Y` and `AAA10Y` series
  pages were reachable, but no unattended observation file was obtained. Plain
  graph CSV requests timed out with zero bytes; cookie-jar graph CSV attempts
  failed with HTTP/2 internal errors; HTTP/1.1 graph CSV attempts timed out; and
  `/private/tmp/fred_credit_spread_retry` contained only small cookie files, not
  usable CSV observations. Keep this branch data-gated until a reliable official
  or licensed historical credit-spread feed is available.
- Corrected Sierra cross-family signal-cache follow-up:
  - Why checked: this was the remaining no-new-data aggregate-orderflow branch
    left open in the ledger. It used corrected Sierra 1-minute aggregate
    BidVolume/AskVolume/NumberOfTrades style data rather than a paid Databento
    quote/depth or ES/MES purchase, so it was the right branch to close before
    elevating paid-data leads.
  - Available evidence: the temporary signal cache
    `/private/tmp/corrected_sierra_cross_family_top_signal_cache.parquet` is no
    longer present, but the engine core trade log remains at
    `data/reports/campaigns/corrected_sierra_cross_family_orderflow_probe/ES/corrected_sierra_cross_family_top_signal_cache/1m/cross_family_large20_signal_probe/core/trade_log.csv`.
  - Bounded audit: replayed all `127` non-empty subsets of the seven executed
    slots from that trade log, using fixed trade outcomes from the existing
    engine report. This is not a full staged rerun, but it is sufficient to
    decide whether rebuilding the missing signal cache is justified.
  - Result: zero pass-like subsets. The audit found `50` near subsets, but every
    near row failed a hard promotion dimension, usually expectancy R and/or weak
    early-history quality.
  - Best-scoring subset was
    `xfam_1000_short_180|xfam_1330_long_120|xfam_1330_short_120|xfam_1430_short_60|xfam_1500_long_60`:
    full n868/net `$129,010`/PF `1.757`/average `$148.6`/expectancy `0.072R`;
    early n183/PF `1.235`/average `$20.4`; WFA n574/PF `1.707`/average
    `$147.2`/expectancy `0.076R`; core n128/PF `1.853`; incubation n111/PF
    `2.168`; worst day `-$3,318`.
  - The all-slot engine report remained full n1089/net `$144,767.50`/PF
    `1.683`/expectancy `0.062R`, with only one target exit and thirty stop
    exits; almost all trades were timed flattens. The branch has useful net/PF
    but not enough R-quality for the staged expectancy gate.
  - Promotion decision: reject this corrected Sierra cross-family signal-cache
    branch as a next independent campaign variant. Do not rebuild the missing
    cache or rerun the slow staged grid unless a materially different signal
    definition raises expectancy R before staging.
- No full-stage independent ES mean-reversion campaign variant has been accepted
  yet.

## Post-Liquidity-Sweep Public-Source Duplicate Audit

- Purpose: after the TBBO liquidity-sweep scaffold, rechecked whether a
  no-new-paid-data public source family remained that was independent,
  academically defensible, mean-reversion-shaped, and not already closed in the
  ledger.
- FINRA aggregate margin debt / customer-credit was already screened and
  rejected. The dense near-miss, negative monthly net-credit shock
  `net_credit_pct1_z24 <= -1.0` long 09:35 -> 16:00, reached only WFA PF about
  `1.40`, WFA MAR about `0.33`, expectancy about `0.17R`, and had thin core
  representation.
- Market breadth / participation was already rejected at the source gate twice:
  Yahoo breadth symbols were unusable, and the official Nasdaq Trader daily
  market-file path did not provide a deterministic unattended history spanning
  WFA and incubation.
- FINRA OTC/ATS and dark-pool transparency was already rejected at the
  historical-data gate. The official API is point-in-time usable for recent
  weeks, but the unattended public history only spans roughly 2021 onward, too
  short for the default full-history WFA protocol.
- OCC option-volume / Reg SHO / stock-loan follow-ups were already closed:
  underlying option-volume and threshold-security endpoints have short public
  history, while OCC stock-loan balance did not meet WFA density plus
  core/incubation gates.
- ISM/PMI was rechecked as a potential scheduled survey-state branch. The
  official ISM reports page was reachable, but FRED graph CSV probes for
  `NAPM`, `ISM/MAN_PMI`, and `NAPMNMI` returned 404, and no unattended official
  historical CSV path was found in this audit. Treat ISM/PMI as a data-source
  gate, not a screenable public branch, unless an approved historical feed is
  added.
- Attention, commodity/weather/fiscal, futures-curve, ETF-flow, funding,
  sentiment, and macro-real-activity families remain covered by prior rejections
  or data gates in the ledger and were not reopened.
- Promotion decision: no additional no-cost public ES mean-reversion campaign
  variant was promoted. The current priority remains
  `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`
  as the strongest non-depth independent lead, pending longer ES+MES `trades`
  history and the predeclared 2020-start validation protocol. The separate
  quote-liquidity-sweep branch remains a bounded one-year ES `tbbo` pilot only
  after explicit data-download approval.

## Current Scratch Candidate Refresh - 2026-06-14

- Purpose: after the liquidity-sweep and public-source duplicate audits, refresh
  the saved scratch-result state so stale `/private/tmp` near rows are not
  mistaken for an unresolved next ES mean-reversion candidate.
- Refresh artifact: `/private/tmp/current_scratch_candidate_audit.csv`.
- Scan scope: `109` recent/top-level scratch CSV files matching `*_top.csv`,
  `*_all.csv`, or `*_summary.csv` under `/private/tmp`, reading up to the first
  `5,000` rows per file.
- Result: `0` files with positive pass flags and `0` pass-flagged rows. The scan
  found `10` files with near flags and `316` near-flagged rows, but the visible
  near rows are already-covered families such as Chicago Fed CFNAI/NFCI and
  NAAIM exposure state. Those source families are rejected in the ledger and do
  not justify a new campaign config without materially different source
  structure.
- Current priority remains unchanged:
  `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`
  is the strongest non-depth independent ES mean-reversion lead, still pending
  longer ES+MES `trades` history and the predeclared validation protocol.
  Quote/depth liquidity sweep remains the separate ES `tbbo` pilot path after
  explicit data-download approval. No accepted full-stage independent ES
  mean-reversion campaign exists yet.

2026-06-14 continuation audit:

- Rechecked old open-looking ledger entries before opening another source
  screen. The corrected-Sierra cross-family combo entry was superseded by the
  later subset replay rejection, and the SEC fails-to-deliver block note was
  superseded by the later corrected-cache FTD rejection. The ledger now marks
  both older entries as superseded so they do not appear to be unresolved
  branches.
- Rechecked option-expiration/OPEX as a possible dealer-hedging/pinning
  calendar thesis. The ledger already closes OPEX/expiration-window seasonality
  as a rejected raw screen, so it was not rerun as a renamed calendar variant.
- No additional no-cost, source-valid, academically distinct ES mean-reversion
  branch was promoted in this continuation. The active recommendation remains:
  validate the ES/MES micro-flow divergence lead only after approved longer
  ES+MES `trades` history, or run the separate bounded ES `tbbo` quote-liquidity
  sweep pilot only after explicit data-download approval.

## ES FRED/New York Fed Reference-Rate Funding-Stress Screen

- Status: duplicate confirmation of an already rejected family. The ledger
  already had a broader NY Fed/OFR reference-rate plumbing rejection; this
  continuation accidentally reopened a narrower FRED-only version. The result is
  still useful as a source retry, but it is not a fresh campaign branch.
- Why tested: daily secured/unsecured overnight funding-rate dislocation is an
  independent thesis from ES/NQ trend following and from balance-sheet quantity
  branches like RRP, H.4.1, bank-credit, and primary-dealer fails: unusual
  overnight funding pressure can proxy for intermediary constraints and
  temporary risk-capacity stress that may mean-revert intraday.
- Academic framing: funding-liquidity and intermediary-constraint research,
  including Brunnermeier/Pedersen-style market-liquidity/funding-liquidity
  feedback and Adrian/Etula/Muir-style intermediary asset-pricing state.
- Source probes:
  - FRED graph CSV mirror for `SOFR`: usable, `2,046` non-null rows from
    `2018-04-03` through `2026-06-11`.
  - FRED graph CSV mirror for `OBFR`: usable, `2,583` non-null rows from
    `2016-03-01` through `2026-06-11`.
  - `TGCR` and `BGCR`: FRED requests returned HTML challenge pages rather than
    parseable CSV.
  - `EFFR`, `DFF`, and `RRPONTSYD`: plain and date-bounded FRED graph CSV
    retries timed out with zero bytes; no-key FRED API calls returned HTTP 400
    requiring an API key.
- Scratch paths:
  - Raw/source probe directory: `/private/tmp/fred_reference_rate_probe`.
  - Screen results: `/private/tmp/fred_reference_rate_es_screen_all.csv` and
    `/private/tmp/fred_reference_rate_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- No-lookahead handling: source observations were shifted by one business day
  before ES eligibility. Features included `SOFR`, `OBFR`, `SOFR-OBFR`,
  `OBFR-SOFR`, one-/five-day changes, five-day means, 21-/63-day ranks, and
  21-/63-day z-scores.
- Screen mechanics: same-session ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, and long/short
  directions.
- Result summary: `6,144` rows evaluated, `0` pass-like rows, and `0`
  near-like rows.
  - Dense WFA rows were too weak. The best `wfa_n >= 500` example was high
    five-day OBFR mean, long `11:00 -> 15:59`: early n0, WFA n505/PF `1.146`/
    MAR `0.843`/average `$65.40`, core n31, incubation n227/PF `1.093`/MAR
    `0.585`.
  - Some short-history `SOFR` stress rows had better economics but failed
    density. High 21-day SOFR z-score, long `13:30 -> 15:59`, had early
    n122/PF `1.198`, WFA n185/PF `1.709`/MAR `9.128`/average `$215.07`, core
    n93/PF `1.767`, incubation n50/PF `1.597`/MAR `8.917`, and full n357/PF
    `1.537`. The source begins in 2018, so this cannot support standard
    full-history WFA acceptance.
- Promotion decision: do not stage. This confirms the prior broader
  NY Fed/OFR reference-rate rejection. Reference-rate funding stress is
  academically clean and source-valid for the reachable series, but the public
  usable histories are too short and dense rows are too weak for the ES
  WFA/incubation gates. Do not rerun simple `SOFR`, `OBFR`, `EFFR`,
  `TGCR`/`BGCR`, `SOFR-OBFR`, reference-rate shock, secured-funding stress,
  overnight-funding-rate level, rank, or z-score variants without a longer
  point-in-time feed and a materially different execution signal.

## ES House STOCK Act / Financial-Disclosure Filing-Pressure Screen

- Status: rejected before staged implementation.
- Why tested: Congressional financial-disclosure and STOCK Act filings are a
  distinct political-information source, not a price/orderflow continuation
  signal. The initial target was transaction-level congressional buy/sell
  pressure, but the official House bulk archives expose only filing metadata
  unless the individual documents are parsed separately.
- Academic framing: congressional trading / political-information asymmetry and
  political-connections research, including Ziobrowski/Cheng/Boyd/Ziobrowski
  abnormal-return work and political stock-ownership literature.
- Source audit:
  - Official House financial-disclosure page:
    `https://disclosures-clerk.house.gov/FinancialDisclosure`.
  - House `ViewReport` exposes annual archives such as
    `/public_disc/financial-pdfs/2026FD.zip`.
  - Downloaded official House archives for `2008` through `2026` under
    `/private/tmp/house_fd_archives`.
  - Each archive contains structured `.txt` and `.xml` metadata, not PDFs in
    this current endpoint. Example 2026 archive contents: `2026FD.txt` and
    `2026FD.xml`.
  - Senate eFD search and Senate ethics financial-disclosure pages returned
    `403 Access Denied` from this environment, so this audit used House only.
- Source limitations:
  - House bulk metadata includes `Prefix`, `Last`, `First`, `Suffix`,
    `FilingType`, `StateDst`, `Year`, `FilingDate`, `DocID`, and older archive
    fields such as `FilingYear`/`DisclosureType`.
  - It does not include ticker, buy/sell side, notional range, asset class, or
    transaction date. This screen therefore tests filing-pressure states, not
    actual congressional trade direction.
  - Parsed `47,242` unique `DocID` rows across `19` annual archives. `P`
    filings begin on `2015-01-03` and run through `2026-06-11`, with `7,522`
    parsed `P` rows. Three apparent filing-date typos from the 2013 archive
    point to `2031`; they are outside the ES sample and do not affect the
    screen through `2026-05-29`.
- Scratch paths:
  - Raw metadata: `/private/tmp/house_fd_metadata_raw.csv`.
  - Feature cache: `/private/tmp/house_fd_filing_pressure_features.csv`.
  - Focused flat screen:
    `/private/tmp/house_fd_filing_pressure_focused_es_screen_all.csv` and
    `/private/tmp/house_fd_filing_pressure_focused_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- No-lookahead handling: filing-pressure features were shifted by one business
  day before ES session eligibility.
- Screen mechanics: same-session ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Feature set: House total filings, unique people, `Hon.` member filings,
  state breadth, candidate-like filings, PTR/member-transaction-like filings,
  extension-like filings, amendment-like filings, annual-like filings, and
  filing-type counts such as `type_P`, `type_T`, `type_C`, `type_X`, `type_A`,
  and `type_O`, plus rolling sums, rolling shares, ranks, and z-scores.
- Result summary: `247,680` focused rows evaluated across `3,895` ES RTH
  sessions, with `0` pass-like rows and `1` loose near-like row.
  - There were `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - There were `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - There were `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
  - The lone loose near row was `house_fd_state_count_rank126 >= 0.726190`,
    prior-up long `09:35 -> 12:00`: early n144/PF `0.757`, WFA n406/PF
    `1.423`/MAR `5.469`, core n83/PF `1.625`, incubation n75/PF `1.189`/MAR
    `0.538`, and full n640/PF `1.274`.
  - The highest-PF rows were sparse artifacts from extension, annual, and
    termination filing bursts; examples had WFA counts near `64` to `119` or
    almost no early/core/incubation coverage.
- Promotion decision: do not stage. House disclosure filing-pressure is
  source-valid enough for a metadata screen, but the simple ES intraday
  translation is not dense or robust. Do not rerun House filing count, PTR count,
  filing-type count, district/state filing breadth, extension/amendment/annual
  filing count, or filing-pressure rank/z-score variants unless a reliable
  source adds transaction-level buy/sell/notional/ticker detail or combined
  House+Senate structured coverage with materially different execution logic.

## ES GFZ Geomagnetic Kp/Ap Behavioral-Mood Screen

- Status: rejected before staged implementation.
- Why tested: geomagnetic storm state is a distinct environmental/behavioral
  source, not a market microstructure, macro, political, or price-action
  restatement. It is also distinct from the prior NYC weather/cloud-cover branch:
  the state is global space weather, not local Wall Street temperature,
  precipitation, or sky cover.
- Academic framing: geomagnetic-storm / investor-mood literature such as
  Krivelyova/Robotti-style stock-return response to geomagnetic storms. The data
  source itself cites Matzka et al. (2021) for the Kp/ap index construction.
- Source audit:
  - Official GFZ Kp/ap text feed:
    `https://kp.gfz-potsdam.de/app/files/Kp_ap_since_1932.txt`.
  - Alternate GFZ mirror:
    `https://www-app3.gfz-potsdam.de/kp_index/Kp_ap_since_1932.txt`.
  - NOAA SWPC `noaa-planetary-k-index.json` is available but only provides a
    recent rolling window, so it was not used for historical validation.
  - GFZ JSON API probe returned HTTP 500 for a short historical range, but the
    full text feed was usable.
- Scratch paths:
  - Raw text: `/private/tmp/gfz_kp_ap_since_1932.txt`.
  - Daily raw cache: `/private/tmp/gfz_kp_ap_daily_raw.csv`.
  - Feature cache: `/private/tmp/gfz_geomagnetic_features.csv`.
  - Screen results: `/private/tmp/gfz_geomagnetic_es_screen_all.csv` and
    `/private/tmp/gfz_geomagnetic_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `34,498` daily UTC observations from `1932-01-01`
  through `2026-06-13`. Recent observations include preliminary flags; the
  screen used completed daily states shifted by one business day before ES
  eligibility.
- Feature set: daily Kp mean/max/std/range, ap mean/max/sum, Kp>=5/6/7 storm
  counts, high-ap counts, storm flags, rolling changes, means, sums, ranks, and
  z-scores.
- Screen mechanics: same-session ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `311,176` rows evaluated across `3,895` ES RTH sessions, with
  `0` pass-like rows and `0` near-like rows.
  - There were `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - There were `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - There were `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
  - Top rows were sparse storm/no-storm artifacts. The visible high-score rows
    often had WFA counts between `25` and `123` or core counts between `0` and
    `13`, despite high PF.
  - Best less-sparse visible row was `storm_kp6_count_z3 <= 1.414214`, long
    `09:35 -> 12:00`: early n43/PF `1.187`, WFA n123/PF `1.512`/MAR `3.005`,
    core n12/PF `1.876`, incubation n34/PF `1.697`/MAR `2.323`, and full
    n202/PF `1.516`. It fails density by a wide margin.
- Promotion decision: do not stage. Geomagnetic Kp/ap has a clean official
  source and an academically distinct behavioral thesis, but simple ES intraday
  translation is either sparse or diluted. Do not rerun simple Kp/ap level,
  ap sum, geomagnetic-storm count, Kp>=5/6 flag, high-ap count, space-weather
  rank/z-score, or geomagnetic mood variants without materially different
  event-study execution or a stronger cross-asset confirmation filter.

## ES NY Fed CMDI Corporate-Bond Distress Screen

- Status: rejected before staged implementation.
- Why tested: the Corporate Bond Market Distress Index is an official
  credit-market functioning source, distinct from price/orderflow continuation,
  ES/MES micro-flow divergence, quote-liquidity sweep, broad OFR stress, and the
  FINRA TRACE breadth source gate. The thesis was mean reversion after
  corporate-bond liquidity or distress pressure has become elevated or unstable.
- Academic framing: Boyarchenko, Crump, Kovner, and Shachar's CMDI research
  combines primary and secondary corporate-bond market dislocation metrics into
  a real-time market-functioning index. This is an academically direct
  credit-liquidity stress source, but the ES intraday translation still needs to
  prove a tradable edge.
- Source audit:
  - Official CMDI page:
    `https://www.newyorkfed.org/research/policy/cmdi`.
  - Page-bundle assets discovered from the New York Fed interactive bundle:
    `/medialibrary/research/interactives/data/cmdi/cmdi_interactive_data.xlsx`,
    `/medialibrary/research/interactives/cmdi/downloads/Market CMDI.xlsx`, and
    `/medialibrary/research/interactives/data/cmdi/cmdi.json`.
  - Cached files:
    `/private/tmp/nyfed_cmdi_interactive_data.xlsx`,
    `/private/tmp/nyfed_cmdi_market_cmdi.xlsx`, and
    `/private/tmp/nyfed_cmdi.json`.
  - Parsed raw cache: `/private/tmp/nyfed_cmdi_weekly_raw.csv`.
  - Feature cache: `/private/tmp/nyfed_cmdi_features.csv`.
  - Screen results: `/private/tmp/nyfed_cmdi_es_screen_all.csv` and
    `/private/tmp/nyfed_cmdi_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `1,116` weekly rows from `2005-01-07` through
  `2026-05-22` for `Market CMDI`, `IG CMDI`, and `HY CMDI`.
- No-lookahead handling: the NY Fed JSON states CMDI is calculated weekly from a
  real-time flow of information, historical calculations use data available in
  real time, and estimates/commentary are published monthly at or shortly after
  `10 a.m.` on the last Wednesday of each month. The screen used a conservative
  eligibility rule of end-of-week Friday plus `31` calendar days plus one
  business day before ES sessions could use the state.
- Feature set:
  - CMDI levels for market, investment-grade, and high-yield sectors.
  - HY-minus-IG, market-minus-IG, market-minus-HY spreads.
  - Cross-sector mean, max, min, dispersion, and sector-to-market ratios.
  - Rolling 1/2/4/8/13-week changes, 4/8/13/26-week means and volatilities, and
    13/26/52/104-week ranks and z-scores.
  - Interaction terms for four-week stress changes times current stress level.
  - Workbook percentile bands were intentionally not used as tradable features
    to avoid depending on a potentially full-sample distribution.
- Screen mechanics: same-session ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `61,024` session/time/direction outcomes across `3,895` ES
  RTH sessions; `23,681` positive/interesting diagnostic rows retained.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
  - Only `2` rows reached `wfa_n >= 400` and `wfa_pf >= 1.4`, and both failed
    holdout density or robustness.
- Best WFA400 row: `cmdi_max_vol26 >= 0.054707`, prior-down long
  `11:00 -> 15:30`; early n83/PF `1.037`, WFA n403/PF `1.509`/MAR `7.607`/
  average `$152.48`, core n124/PF `1.388`, incubation n12/PF `2.024`, and full
  n513/PF `1.453`.
- Best dense WFA row: `market_minus_hy_cmdi_vol13 >= 0.032545`, no prior filter,
  long `11:00 -> 12:00`; early n153/PF `0.769`, WFA n514/PF `1.389`/MAR
  `4.109`/average `$48.50`, core n73/PF `1.112`, incubation n62/PF `2.368`,
  and full n782/PF `1.343`.
- Promotion decision: do not stage. CMDI is source-valid and academically
  relevant, but the ES intraday translation is either too event-sparse, fails
  early/core/holdout robustness, or is diluted below WFA PF. Do not rerun simple
  CMDI level, CMDI change, IG/HY CMDI spread, corporate-bond distress
  volatility, corporate-bond liquidity stress, CMDI rank, or CMDI z-score
  variants without materially different execution structure or a stronger
  independent confirmation filter.

## ES World Uncertainty Index Macro-Uncertainty Screen

- Status: rejected before staged implementation.
- Why tested: WUI is a distinct global/US macro-uncertainty source based on
  Economist Intelligence Unit country reports, not a price/orderflow,
  liquidity-sweep, ES/MES divergence, daily EPU, EMV news-volatility, GPR, or
  corporate-bond stress signal. The intended ES translation was mean reversion
  after elevated or shifting uncertainty states.
- Academic framing: Ahir, Bloom, and Furceri's World Uncertainty Index
  methodology, which counts uncertainty language in EIU country reports and
  normalizes by report length.
- Source audit:
  - Data page:
    `https://worlduncertaintyindex.com/data/`.
  - Monthly workbook:
    `https://worlduncertaintyindex.com/wp-content/uploads/2026/06/WUI_M_dataset_2026_05.xlsx`.
  - Cached workbook: `/private/tmp/wui_monthly_2026_05.xlsx`.
  - Parsed raw cache: `/private/tmp/wui_monthly_raw.csv`.
  - Feature cache: `/private/tmp/wui_uncertainty_features.csv`.
  - Screen results: `/private/tmp/wui_uncertainty_es_screen_all.csv` and
    `/private/tmp/wui_uncertainty_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `221` monthly rows from `2008-01-01` through
  `2026-05-01` for global and US WUI, WTUI, and WPUI series.
- No-lookahead handling: each monthly observation became eligible only after the
  source month plus `45` calendar days plus one business day. Any future
  promotion would still require point-in-time release validation because the
  downloaded workbook is a current-history file.
- Feature set: global and US uncertainty, trade-uncertainty, and
  policy-uncertainty levels; US-minus-global spreads; trade/policy shares;
  policy-minus-trade spreads; 1/3/6/12-month changes and percentage changes;
  3/6/12-month means; 12/24/60/120-month ranks and z-scores; and stress
  interactions.
- Screen mechanics: same-session ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `61,024` ES outcomes across `3,895` sessions, with `16,644`
  diagnostic rows retained.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best score row: `global_policy_share_pct1 >= 0.180796`, prior-down long
  `11:00 -> 15:30`; early n150/PF `0.797`, WFA n352/PF `1.518`/MAR `6.684`/
  average `$155.09`, core n104/PF `1.322`, incubation n11/PF `3.116`, and full
  n516/PF `1.461`.
- Best dense row: `global_wui_chg6 <= 884.38`, prior-down long
  `11:00 -> 15:30`; early n218/PF `0.815`, WFA n579/PF `1.386`/MAR `7.141`/
  average `$116.70`, core n116/PF `1.539`, incubation n30/PF `1.707`, and full
  n838/PF `1.322`.
- Promotion decision: do not stage. WUI/WTUI/WPUI is a clean independent
  uncertainty source, but the ES intraday translation either fails early-history
  robustness, is too holdout-sparse, or dilutes below WFA PF. Do not rerun
  simple World Uncertainty Index level, change, share, spread, rank, or z-score
  variants without materially different execution structure and point-in-time
  release validation.

## Post-WUI Scratch Candidate Refresh

- Status: no hidden saved pass candidate found.
- Scratch output: `/private/tmp/current_scratch_candidate_audit_post_wui.csv`.
- Scope: scanned `120` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `13` files with near flags.
  - `335` near-flagged rows.
- The near rows were from already documented rejected/covered families:
  Chicago Fed NFCI/CFNAI, NAAIM active-manager exposure, and House
  filing-pressure variants.
- Duplicate-source check after this refresh did not surface a clean untouched
  no-cost public family in the obvious sentiment, fiscal-flow, funding,
  dealer-plumbing, Treasury, Fed text, calendar, cross-asset, or macro
  real-activity buckets. Those buckets are already rejected or source-gated in
  the ledger.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES Fannie Mae HPSI Housing-Sentiment Screen

- Status: rejected before staged implementation and source-horizon-limited.
- Why tested: Fannie Mae's National Housing Survey / Home Purchase Sentiment
  Index is a housing-specific consumer sentiment source distinct from the
  already rejected broad housing-starts/permits/mortgage-rate, house-price,
  Michigan/SCE/NFIB, and household-balance-sheet screens. The intended
  mean-reversion thesis was that stressed or optimistic housing sentiment can
  proxy household risk appetite, collateral confidence, and housing-cycle
  pressure around same-day ES reversals.
- Academic framing: Leamer-style housing-cycle evidence, Case/Quigley/Shiller
  housing-wealth and consumption evidence, Piazzesi/Schneider/Tuzel
  housing/asset-pricing logic, and Lemmon/Portniaguina consumer-confidence
  return-predictability evidence support testing housing sentiment as a
  macro-risk state. This is indirect ES evidence, not microstructure evidence.
- Source audit:
  - Fannie Mae National Housing Survey monthly indicator workbook:
    `https://www.fanniemae.com/media/document/xlsx/nhs-monthly-indicator-data-092025`.
  - FRED graph CSV for `FMNHSHPSIUS`:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=FMNHSHPSIUS`.
  - Downloaded workbook:
    `/private/tmp/fannie_nhs_monthly_indicator_data_092025.xlsx`.
  - FRED HPSI raw cache:
    `/private/tmp/fred_fannie_hpsi_raw_20260614.csv`.
  - Parsed component raw cache:
    `/private/tmp/fannie_hpsi_housing_sentiment_raw.csv`.
  - Compact feature cache:
    `/private/tmp/fannie_hpsi_housing_sentiment_compact_features.csv`.
  - Compact screen results:
    `/private/tmp/fannie_hpsi_housing_sentiment_compact2_es_screen_all.csv`
    and `/private/tmp/fannie_hpsi_housing_sentiment_compact2_es_screen_top.csv`.
  - ES cache:
    `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage:
  - Parsed `184` monthly component rows from `2010-06-01` through
    `2025-09-01`.
  - FRED `FMNHSHPSIUS` parsed `175` rows from `2011-03-01` through
    `2025-09-01`.
  - The Fannie workbook last-modified header was `2025-10-03`, and no newer
    unattended workbook was found in this audit. The public series is therefore
    not a current live feed as of the 2026-06-14 check.
- No-lookahead handling: each monthly source row became eligible only after
  month-end plus `15` calendar days, adjusted to the next business day when
  needed. Effective dates ran from `2010-07-15` through `2025-10-15`. Because
  the source stops at `2025-09`, ES sessions were capped at `2025-11-29`
  instead of forward-filling stale discontinued sentiment into 2026.
- Feature set: HPSI, net good-time-to-buy, net good-time-to-sell, net expected
  home prices up, net expected mortgage rates down, net not-concerned-about-job,
  net income higher, expected home-price change, expected rent-price change,
  net mortgage easy, net personal finances better, net economy right-track,
  net buy-over-rent, and net rent-prices-up. The compact audit tested levels,
  1/3/6/12-month changes, 3/6/12-month mean gaps, and 12/24/60/120-month ranks
  and z-scores.
- Screen mechanics: no-lookahead ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `129,024` compact diagnostic rows.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `1` loose-shape row.
  - `0` mean-reversion pass-like rows.
  - `0` mean-reversion near-like rows.
  - `0` mean-reversion loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Only loose row, not mean-reversion-shaped: `hpsi_chg1 <= -2.0`,
  prior-up long `11:00 -> 15:30`; early n42/PF `0.973`, WFA n318/PF `1.353`,
  core n91/PF `1.383`, incubation n35/PF `1.231`, and full n395/PF `1.318`.
- Best mean-reversion diagnostic was sparse and early-history failed:
  `expected_home_price_change_rank60 >= 0.878049`, prior-down long
  `10:00 -> 12:00`; early n197/PF `0.892`, WFA n103/PF `1.936`, core n7,
  incubation n4, and full n304/PF `1.262`.
- Best WFA500 mean-reversion row was uneconomic:
  `net_buy_over_rent >= 39.0`, prior-up short `10:00 -> 15:59`; early n109/PF
  `0.684`, WFA n516/PF `0.912`, core n173/PF `0.747`, incubation n5/PF
  `4.127`, and full n630/PF `0.920`.
- Promotion decision: do not stage. Fannie HPSI housing sentiment is a clean
  independent public thesis, but the current public feed is not live-current,
  and even the bounded historical audit produced no pass, no near row, no dense
  WFA PF >= 1.4 row, and no mean-reversion loose row. Do not rerun simple HPSI,
  good-time-buy/sell, home-price expectation, mortgage-rate expectation,
  mortgage-access sentiment, income/job sentiment, economy right-track,
  buy-versus-rent, rent-price expectation, rank, z-score, change, or mean-gap
  variants unless a durable current source feed and materially different
  execution confirmation are introduced.

## Post-Fannie-HPSI Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the Fannie HPSI
  housing-sentiment outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_fannie_hpsi_20260614.csv`.
- Scope: scanned `153` `/private/tmp/*top.csv`, `*top_finite.csv`, `*all.csv`,
  and `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `347` near-flagged rows.
  - `10` files with loose flags.
  - `42` loose-flagged rows.
  - `0` mean-reversion pass/near/loose flagged rows.
- The only new HPSI flag was the rejected loose prior-up long diagnostic above.
  Remaining near/loose rows are already rejected or covered families including
  BLS price pressure, USDM drought, Chicago Fed NFCI/CFNAI, House
  filing-pressure, NAAIM exposure, FHWA VMT, and CDC ILINet.
- Current priority remains unchanged:
  - First:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending approved longer ES+MES `trades` history and the predeclared
    validation protocol.
  - Second:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES Philadelphia Fed ADS Real-Time Business-Conditions Re-Audit

- Status: rejected before staged implementation; this confirms the older ADS
  rejection rather than opening a fresh source family.
- Why re-audited: Philadelphia Fed ADS is a no-cost public real-time business
  conditions source with all-vintage data, and it was worth a current
  point-in-time recheck after the later WEI/SPF/Moody work because the ADS
  vintage file supports cleaner no-lookahead handling than most current-history
  macro mirrors. The intended ES translation was mean reversion after
  real-activity nowcast stress or relief: unusually weak or rapidly
  deteriorating business conditions might proxy risk-premium/liquidity pressure
  after completed intraday ES weakness, while overheated/improving states might
  support opposite fades.
- Academic framing:
  - The Philadelphia Fed ADS page states that the index is based on Aruoba,
    Diebold, and Scotti (2009), "Real-Time Measurement of Business Conditions,"
    Journal of Business and Economic Statistics.
  - The 2025 Philadelphia Fed technical documentation describes ADS as a
    high-frequency real-business-conditions index updated as new or revised U.S.
    government component data are released.
  - This is a macro-state screen only; it is not direct ES microstructure
    evidence.
- Source audit:
  - Official page:
    `https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/ads`.
  - Current-vintage workbook:
    `/private/tmp/philly_ads_current_vintage_20260614.xlsx`.
  - All-vintages zip:
    `/private/tmp/philly_ads_all_vintages_20260614.zip`.
  - Extracted all-vintages workbook:
    `/private/tmp/philly_ads_all_vintages_xlsx_20260614/ADS_All_Vintages-zip.xlsx`.
  - Technical-documentation PDF:
    `/private/tmp/philly_ads_technical_documentation_20260614.pdf`.
  - Parsed current-vintage raw cache:
    `/private/tmp/philly_ads_current_vintage_raw.csv`.
  - Real-time feature cache:
    `/private/tmp/philly_ads_realtime_features.csv`.
  - Screen results:
    `/private/tmp/philly_ads_realtime_es_screen_all.csv`,
    `/private/tmp/philly_ads_realtime_es_screen_top.csv`, and
    `/private/tmp/philly_ads_realtime_es_screen_top_finite.csv`.
  - ES cache:
    `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage:
  - Current vintage parsed `24,204` daily ADS rows from `1960-03-01` through
    `2026-06-06`.
  - The all-vintage matrix had `1,547` release-vintage columns and `24,204`
    daily rows. Vintages ran from `ADS_INDEX_120508` through
    `ADS_INDEX_061126`.
  - Point-in-time feature rows ran from effective date `2008-12-08` through
    `2026-06-12`; the latest ADS source date in the final vintage was
    `2026-06-06`.
- No-lookahead handling: each `ADS_INDEX_MMDDYY` vintage became eligible only
  one business day after the vintage date. For each vintage, features used only
  that vintage column's nonblank ADS history through that release's latest
  available source date. The screen did not use the current-vintage value for
  historical sessions.
- Feature set: ADS level, stress `-ADS`, positive/negative state, 1/5/21/63/126
  and 252-day ADS changes, stress changes, rolling 5/21/63/126/252-day means,
  mean gaps, z-scores, percentile ranks, short-minus-medium momentum, and
  release-to-release changes, means, ranks, and z-scores over 13/26/52/104
  releases.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions. Mean-reversion-shaped rows were
  defined as prior-down ES longs or prior-up ES shorts.
- Result summary: `33,129` positive/interesting diagnostic rows retained.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass-like rows.
  - `0` mean-reversion near-like rows.
  - `0` mean-reversion loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best dense row with `wfa_n >= 500`, not a mean-reversion setup:
  `ads_chg5_release_z52 >= 0.910742`, no prior filter, long `10:30 -> 15:30`;
  early n159/PF `0.922`, WFA n509/PF `1.376`/MAR `4.196`/average `$121.92`,
  core n123/PF `1.719`, incubation n49/PF `1.137`, and full n763/PF `1.294`.
- Best mean-reversion row with `wfa_n >= 500`:
  `ads_chg21_release_chg1 >= 0.000935`, prior-down long `11:00 -> 15:30`;
  early n200/PF `0.661`, WFA n550/PF `1.314`/MAR `5.625`/average `$101.82`,
  core n111/PF `1.233`, incubation n59/PF `1.374`/MAR `1.089`, and full n831/PF
  `1.243`.
- Best early-qualified mean-reversion diagnostic:
  `ads_from_mean63_release_chg13 <= -0.154589`, prior-down long
  `10:30 -> 12:00`; early n82/PF `1.014`, WFA n210/PF `1.438`/MAR `3.075`,
  core n63/PF `1.435`, incubation n33/PF `2.548`/MAR `3.992`, and full n337/PF
  `1.507`.
- Promotion decision: do not stage. This stricter all-vintage ADS re-audit
  confirms the prior ADS rejection: its ES intraday translation either lacks WFA
  density or dilutes below WFA PF while failing early-history robustness. Do not
  rerun simple ADS level, ADS stress, ADS change, ADS release revision/change,
  business-conditions rank, z-score, or mean-gap variants without materially
  different execution confirmation.

## Post-ADS Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the Philadelphia Fed
  ADS outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_philly_ads_20260614.csv`.
- Scope: scanned `149` `/private/tmp/*top.csv`, `*top_finite.csv`,
  `*all.csv`, and `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `347` near-flagged rows.
  - `6` files with loose flags.
  - `38` loose-flagged rows.
- The ADS re-audit itself produced no pass, near, or loose flags. The remaining
  near/loose rows are already rejected or covered families: BLS price pressure,
  USDM drought, Chicago Fed NFCI/CFNAI, House filing-pressure, NAAIM exposure,
  FHWA VMT, and CDC ILINet.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## Post-Liquidity-Follow-Up Source Exhaustion Checkpoint

- Status: no accepted independent ES mean-reversion campaign has been found yet.
  The next real tests are data-gated rather than no-cost public-source screens.
- Fresh scratch audit:
  `/private/tmp/current_scratch_candidate_audit_post_liquidity_followup_20260614.csv`.
- Scope: scanned `142` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `347` near-flagged rows.
  - `8` loose-flagged rows.
- The flagged files are already rejected or covered families:
  BLS producer/import-export price pressure, CDC ILINet, Chicago Fed NFCI/CFNAI,
  FHWA VMT, House filing-pressure, NAAIM exposure, and USDM drought.
- Focused package verification:
  `PYTHONPATH=src pytest -q tests/test_quote_liquidity_sweep_reversion.py tests/test_es_mes_flow_divergence.py`
  passed with `5 passed`.
- Current ranked path:
  - First: `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`.
    This is the best non-depth independent ES mean-reversion candidate. It needs
    approved longer ES+MES `trades` history and the predeclared
    `research_artifacts/es_mes_flow_divergence_validation_protocol_20260614.md`
    before it can be accepted or rejected on full evidence.
  - Second: `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`.
    This is the only true liquidity-sweep branch still worth testing. It needs
    explicit approval for the bounded one-year ES `tbbo` pilot documented in
    `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
- Do not promote either branch as live-eligible until its data gate and staged
  protocol pass. Do not spend on `tbbo` or ES+MES `trades` without a final
  metadata check and explicit approval.

## ES Moody Baa/Aaa Corporate-Spread Mean-Reversion Screen

- Status: rejected before staged implementation.
- Why tested: this reopened the credit-spread branch after the liquidity-sweep
  follow-up. The earlier OAS and Baa-minus-10Y routes were data-gated, but the
  official FRED graph CSVs for Moody `BAA` and `AAA` corporate yields were
  downloadable and long enough to screen. The intended ES translation was
  credit-stress-conditioned intraday mean reversion, not another trend-following
  branch.
- Academic framing: default-spread and credit-risk expected-return literature
  supports credit spreads as risk-premium and stress-state variables, while
  price-pressure literature motivates testing same-day reversal only after a
  completed ES move.
- Source audit:
  - Official FRED graph CSVs:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAA` and
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=AAA`.
  - Caches:
    `/private/tmp/fred_credit_spread_retry_20260614/BAA.csv` and
    `/private/tmp/fred_credit_spread_retry_20260614/AAA.csv`.
  - Parsed raw cache:
    `/private/tmp/fred_moody_corporate_spread_raw.csv`.
  - Feature cache:
    `/private/tmp/fred_moody_corporate_spread_features.csv`.
  - Screen results:
    `/private/tmp/fred_moody_corporate_spread_es_screen_all.csv` and
    `/private/tmp/fred_moody_corporate_spread_es_screen_top.csv`.
  - ES cache:
    `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: `1,289` monthly rows from `1919-01-01` through
  `2026-05-01`.
- No-lookahead handling: each monthly source observation became eligible only
  after month-end plus `45` calendar days plus one business day. This is
  conservative for a current-history FRED series; any future promotion would
  still require exact release-calendar and vintage validation.
- Feature set: Baa yield, Aaa yield, Baa-minus-Aaa spread, Baa/Aaa ratio,
  1/3/6/12-month changes and percentage changes, 3/6/12-month mean gaps,
  12/24/60/120-month ranks and z-scores, and credit-stress/relief composites.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, and only
  same-day mean-reversion shapes: `prior_down` long and `prior_up` short.
- Result summary: `1,340` credit-state thresholds across `42,880` ES
  mean-reversion rows.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-like rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
  - `0` rows with `wfa_n >= 300`, `wfa_pf >= 1.35`,
    `incubation_n >= 40`, and `incubation_pf >= 1.1`.
- Top score row: `baa_minus_aaa_mean12 <= 0.681667`, `prior_up` short
  `10:30 -> 12:00`; early n28/PF `0.598`, WFA n31/PF `2.203`/MAR
  `3.931`/average `$228.87`, core n17/PF `3.216`, incubation n157/PF
  `0.924`/MAR `-0.292`. This is sparse in WFA/core and fails holdout.
- Promotion decision: do not stage. The long-history Moody Baa/Aaa source is now
  usable enough to close this no-cost credit-spread follow-up, but the simple
  spread/yield/rank/z-score translation does not produce a dense, split-stable
  ES intraday mean-reversion edge. Do not rerun simple Moody Baa, Aaa,
  Baa-minus-Aaa, Baa/Aaa ratio, credit-stress rank, z-score, shock, or relief
  variants without materially different point-in-time credit data or execution
  confirmation.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## Post-Moody-Credit Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the Moody Baa/Aaa
  credit-spread outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_moody_credit_20260614.csv`.
- Scope: scanned `144` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `23` files with near flags.
  - `489` near-flagged rows.
  - `180` loose-flagged rows.
- The incremental flagged rows are not new candidates. They come from already
  rejected or covered families: BLS producer/import-export price pressure, CDC
  ILINet, Chicago Fed NFCI/CFNAI, FHWA VMT, House filing-pressure, NAAIM
  exposure, news-risk ensemble, and USDM drought.
- The Moody Baa/Aaa files themselves produced no pass/near/loose flags.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES Philadelphia Fed SPF Anxious Index Screen

- Status: rejected before staged implementation.
- Why tested: this was an unclosed no-cost professional-forecaster
  macro-expectations source, distinct from Michigan/SCE/NFIB consumer and
  business sentiment, AAII/NAAIM investor sentiment, NFCI/CFNAI/WEI activity
  state, CMDI/WUI uncertainty, ES/MES divergence, liquidity sweep, and accepted
  trend/orderflow continuation.
- Academic framing: survey-forecast disagreement and macro-uncertainty
  literature treats professional forecasts as real-time expectations and
  uncertainty information. The ES translation was contrarian/mean-reversion:
  high or rising recession-probability expectations can proxy macro stress,
  risk aversion, or forced de-risking pressure, so the screen tested reversal
  only after a completed same-day ES move.
- Source audit:
  - Official Philadelphia Fed Survey of Professional Forecasters Anxious Index
    workbook:
    `https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/survey-of-professional-forecasters/anxious-index/anxious_index_chart.xlsx`.
  - Workbook cache:
    `/private/tmp/philly_spf_anxious_index_chart.xlsx`.
  - Parsed raw cache:
    `/private/tmp/philly_spf_anxious_index_raw.csv`.
  - Feature cache:
    `/private/tmp/philly_spf_anxious_index_features.csv`.
  - Screen results:
    `/private/tmp/philly_spf_anxious_index_es_screen_all.csv` and
    `/private/tmp/philly_spf_anxious_index_es_screen_top.csv`.
  - ES cache:
    `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: `231` quarterly Anxious Index rows from `1969Q1` through
  `2026Q3`.
- Source interpretation and no-lookahead handling:
  - The workbook documentation says the Anxious Index is the probability of
    negative quarter-over-quarter real GDP growth in the quarter one quarter in
    the future of the quarterly SPF survey.
  - The workbook labels observations by the quarter being forecast, not by the
    survey quarter.
  - The screen made each value tradable only from the first business day of the
    labeled forecast quarter. This is conservative relative to the prior-quarter
    survey publication and avoids using the workbook's ex-post recession-shading
    column.
- Feature set: Anxious Index level, 1/2/4/8-quarter changes and percentage
  changes, 2/4/8-quarter mean gaps, 4/8/20/40-quarter ranks and z-scores,
  stress-pressure and relief-shock composites.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, and only
  same-day mean-reversion shapes: `prior_down` long and `prior_up` short.
- Result summary: `350` threshold specs across `11,200` ES mean-reversion rows.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-like rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Top score row: `anxious_index_chg1 >= 6.050303`, `prior_down` long
  `14:30 -> 15:59`; early n48/PF `0.574`, WFA n106/PF `1.627`/MAR
  `4.918`/average `$150.66`, core n28/PF `3.459`, incubation n28/PF
  `2.356`/MAR `2.650`, and full n182/PF `1.375`. This is far below WFA/core
  and incubation density, and early-history performance is poor.
- Promotion decision: do not stage. SPF recession anxiety is a clean independent
  expectations/uncertainty source, but the simple level/change/rank/z-score ES
  intraday mean-reversion translation produces only sparse late-day reversal
  pockets. Do not rerun simple SPF Anxious Index level, change, rank, z-score,
  recession-probability stress, or relief variants without exact release-date
  reconstruction and materially different execution confirmation.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## Post-SPF-Anxious Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the Philadelphia Fed
  SPF Anxious Index outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_spf_anxious_20260614.csv`.
- Scope: scanned `146` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `23` files with near flags.
  - `489` near-flagged rows.
  - `180` loose-flagged rows.
- The SPF files themselves produced no pass/near/loose flags. The remaining
  flags are the same already rejected or covered families from the post-Moody
  audit: BLS price pressure, CDC ILINet, Chicago Fed NFCI/CFNAI, FHWA VMT,
  House filing-pressure, NAAIM exposure, news-risk ensemble, and USDM drought.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES Daylight-Saving-Time Sleep-Disruption Screen

- Status: rejected before staged implementation.
- Why tested: deterministic DST transition windows give a clean behavioral-event
  source, distinct from liquidity sweep, ES/MES flow divergence, lunar phase,
  geomagnetic/sunspot activity, and local weather. The caveat is calendar
  overlap: because this is still a seasonal/calendar event, any pass would have
  needed unusually strong split robustness.
- Academic framing: Kamstra, Kramer, and Levi, "Losing Sleep at the Market: The
  Daylight Saving Anomaly" (AER 2000, DOI `10.1257/aer.90.4.1005`) and the AER
  reply (DOI `10.1257/00028280260344795`).
- Source audit:
  - Deterministic U.S. DST transition calendar since the 2007 rule change.
  - DST starts on the second Sunday in March and ends on the first Sunday in
    November; the ES screen used the first RTH Monday/session after each
    transition.
  - No vendor data, revisions, or publication lag apply.
  - Scratch script: `/private/tmp/dst_sleep_disruption_es_screen.py`.
  - Deterministic raw note: `/private/tmp/dst_sleep_disruption_daily_raw.txt`.
  - Feature cache: `/private/tmp/dst_sleep_disruption_features.csv`.
  - Screen results: `/private/tmp/dst_sleep_disruption_es_screen_all.csv` and
    `/private/tmp/dst_sleep_disruption_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Feature set: DST start/end event flags, first post-transition RTH session,
  days since/until DST start/end, pre/post windows of `1`, `2`, `3`, `5`, `10`,
  and `21` days, any-DST post windows, sleep-loss pressure, and generic
  transition-pressure features.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `8,928` evaluated rows over `3,786` ES sessions and `37`
  DST-derived features.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Top event row: `dst_any_post_3d >= 0.5`, prior-up long `10:30 -> 15:59`;
  early n13/PF `1.102`, WFA n38/PF `2.919`/MAR `29.201`, core n7/PF
  `11.676`, incubation n3/PF `18.811`, and full n54/PF `2.593`. This is not
  mean-reversion-shaped and is far too sparse.
- Best direct event row: `dst_end_pre_5d >= 0.5`, no-prior-filter short
  `11:00 -> 12:00`; early n16/PF `0.648`, WFA n40/PF `2.813`, core n8,
  incubation n4, and full n60/PF `2.507`. Also far too sparse.
- Dense complement examples diluted badly:
  - `dst_start_post_21d <= 0.5`, prior-down long `11:00 -> 15:59`: WFA
    n1008/PF `1.018`, core n213/PF `0.979`, incubation n127/PF `2.129`, full
    n1532/PF `1.094`.
  - `dst_end_days_since >= 291.0`, no-prior-filter short `10:00 -> 15:59`:
    WFA n480/PF `1.178`, incubation n47/PF `1.024`, full n710/PF `1.090`.
- Promotion decision: do not stage. DST sleep-disruption windows are too sparse
  as direct events and too diluted as complements. Do not rerun simple DST
  start/end, pre/post-DST windows, sleep-loss pressure, transition-pressure, or
  DST calendar variants without materially different non-calendar confirmation
  and exceptional split robustness.

## Post-DST Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the DST outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_dst_sleep.csv`.
- Scope: scanned `142` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - The DST `all` and `top` files each had `0` pass, near, and loose rows.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## Lunar Phase / Investor-Mood Screen

- Why tested: lunar phase is an academically discussed behavioral-mood source,
  distinct from accepted trend/orderflow continuation, quote-liquidity sweep,
  ES/MES flow divergence, geomagnetic storms, air-pollution mood, local weather,
  and generic weekday/month calendar seasonality.
- Academic framing: Yuan, Zheng, and Zhu, "Are investors moonstruck? Lunar
  phases and stock returns" (`https://doi.org/10.1016/j.jempfin.2005.06.001`;
  SSRN page `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=283156`).
  This supports a behavioral mood hypothesis, but does not directly establish a
  tradable intraday ES mean-reversion rule.
- Source and artifacts:
  - Deterministic lunar-phase approximation only; no revised macro/survey data.
  - Reference new moon Julian day `2451550.25972`, synodic month
    `29.530588853` days, noon-UTC session-date phase.
  - Scratch script: `/private/tmp/lunar_phase_es_screen.py`.
  - Deterministic raw note: `/private/tmp/lunar_phase_daily_raw.csv`.
  - Feature cache: `/private/tmp/lunar_phase_features.csv`.
  - Screen results: `/private/tmp/lunar_phase_es_screen_all.csv` and
    `/private/tmp/lunar_phase_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- No-lookahead handling: lunar state is deterministic and known in advance, so
  each ES session uses only its own calendar-date phase. If this had passed,
  exact ephemeris validation would still be required before staged promotion.
- Feature set: phase age/fraction, sine/cosine phase, illumination and
  darkness, distance to new/full/quarter moon, waxing/waning flags, one-to-seven
  day new/full windows, quarter windows, full-minus-new windows, rolling
  ranks/z-scores/mean gaps, and full/new mood-pressure composites.
- Screen mechanics: session-level ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `205,184` no-lookahead rows evaluated over `3,786` ES
  sessions and `199` lunar-derived features.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Top score row: `dist_quarter_days_from_mean126 <= -2.906154`, prior-down long
  `10:00 -> 15:30`; early n37/PF `1.259`, WFA n110/PF `2.037`/MAR `9.787`,
  core n25/PF `6.777`, incubation n19/PF `2.025`, full n166/PF `1.949`. This
  is mean-reversion-shaped but far below early/WFA/core/incubation density.
- Best dense WFA row with at least 500 WFA trades: `dist_quarter_days_rank21 <=
  0.238095`, no prior filter, long `11:00 -> 15:30`; early n217/PF `0.891`,
  WFA n543/PF `1.314`, core n110/PF `1.547`, incubation n76/PF `0.664`, and
  full n836/PF `1.125`. This is not mean-reversion-shaped and fails holdout.
- Promotion decision: do not stage. Lunar phase produced only sparse
  quarter-phase artifacts and holdout-failed broad long diagnostics. Do not
  rerun simple lunar phase age, full/new moon window, illumination,
  waxing/waning, quarter-phase, lunar rank/z-score, or lunar mood-pressure
  variants without materially different cross-asset confirmation and exact
  ephemeris validation.

## Post-Lunar Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the lunar outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_lunar_phase.csv`.
- Scope: scanned `136` `/private/tmp/*top.csv`, `*all.csv`, and `*summary.csv`
  files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - The lunar `all` and `top` files each had `0` pass, `0` near, and `0` loose
    rows.
- Remaining near/loose flags come from already rejected or covered scratch
  families: Chicago Fed NFCI/CFNAI, House filing-pressure, NAAIM exposure, FHWA
  VMT/USDM continuation diagnostics, and news-risk ensemble outputs.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## SILSO Daily Sunspot / Solar-Activity Screen

- Why tested: daily solar activity is a no-cost official environmental state
  not already closed as a direct sunspot branch. It is adjacent to, but distinct
  from, the rejected GFZ geomagnetic Kp/ap screen: Kp/ap measures Earth
  geomagnetic disturbance, while SILSO sunspot counts measure solar activity.
- Academic framing: indirect environmental-mood support from
  Krivelyova/Robotti geomagnetic-storm stock-return evidence
  (`https://doi.org/10.2139/ssrn.375702`) and Hirshleifer/Shumway
  weather-mood evidence (`https://doi.org/10.1111/1540-6261.00556`). This is
  weaker than a direct ES market-microstructure thesis, so the screen needed a
  strong split-stable result to justify promotion.
- Source and artifacts:
  - Official WDC-SILSO daily total sunspot-number CSV:
    `https://www.sidc.be/SILSO/DATA/SN_d_tot_V2.0.csv`.
  - Raw cache: `/private/tmp/silso_daily_sunspot_raw.csv`.
  - Feature cache: `/private/tmp/silso_daily_sunspot_features.csv`.
  - Scratch script: `/private/tmp/silso_sunspot_es_screen.py`.
  - Screen results: `/private/tmp/silso_sunspot_es_screen_all.csv` and
    `/private/tmp/silso_sunspot_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `76,122` daily rows from `1818-01-01` through
  `2026-05-31`. Recent rows are preliminary (`definitive_flag=0`), so the
  scratch screen used a conservative one-business-day lag after each completed
  source date. Any future pass would require exact SILSO preliminary/final
  vintage handling.
- Feature set: sunspot number, sunspot standard deviation, observation count,
  zero/active/high-sunspot flags, uncertainty ratio, 1/2/3/5/10/21/63-day
  changes and percentage changes, 5/10/21/63/126/252/504-day means, ranks,
  z-scores, mean gaps, and solar-pressure/solar-shock/solar-relief composites.
- Screen mechanics: session-level ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `294,976` no-lookahead rows evaluated over `3,786` ES
  sessions and `304` solar-derived features.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best dense WFA row: `sunspot_active_flag_z63 <= 0.509902`, prior-up long
  `13:30 -> 15:30`; early n348/PF `0.650`, WFA n553/PF `1.352`/MAR `1.408`,
  core n169/PF `2.204`, incubation n125/PF `0.857`, full n1026/PF `1.081`.
  This is not mean-reversion-shaped and fails early/incubation PF.
- Best mean-reversion-shaped score row:
  `sunspot_uncertainty_ratio_mean10 <= 0.148264`, prior-down long
  `10:30 -> 15:59`; early n412/PF `0.758`, WFA n555/PF `1.116`/MAR `0.411`,
  core n18/PF `6.660`, incubation n59/PF `2.321`, full n1026/PF `1.154`.
  Higher-PF mean-reversion rows were sparse, with only about `90`-`109` WFA
  trades.
- Promotion decision: do not stage. Daily sunspot state either dilutes below WFA
  PF or relies on sparse solar-cycle pockets with weak early/core structure. Do
  not rerun simple sunspot level, active/high-sunspot flags, solar shock/relief,
  observation-count, uncertainty-ratio, rank, z-score, or mean-gap variants
  without materially different cross-asset confirmation and exact SILSO vintage
  handling.

## Post-SILSO Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the solar outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_silso_sunspot.csv`.
- Scope: scanned `138` `/private/tmp/*top.csv`, `*all.csv`, and `*summary.csv`
  files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - The SILSO `all` and `top` files each had `0` pass, `0` near, and `0` loose
    rows.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## SAD / Daylight Behavioral-Mood Screen

- Why tested: seasonal-affective-disorder / daylight length is a named
  academic behavioral-mood thesis, distinct from lunar phase, geomagnetic Kp/ap,
  sunspot activity, local weather/cloud cover, and air-pollution mood. It does
  overlap broad calendar seasonality, so any pass would have needed exceptional
  split robustness before promotion.
- Academic framing: Kamstra, Kramer, and Levi, "Winter Blues: A SAD Stock Market
  Cycle" (`https://doi.org/10.1257/000282803321455322`). This supports a mood
  seasonality hypothesis but does not directly establish an intraday ES
  mean-reversion rule.
- Source and artifacts:
  - Deterministic New York daylight approximation only; no revised source data.
  - Latitude `40.7128`; declination formula
    `23.44*sin(2*pi*(day_of_year-80)/365.2422)`.
  - Scratch script: `/private/tmp/daylight_sad_es_screen.py`.
  - Deterministic raw note: `/private/tmp/daylight_sad_daily_raw.txt`.
  - Feature cache: `/private/tmp/daylight_sad_features.csv`.
  - Screen results: `/private/tmp/daylight_sad_es_screen_all.csv` and
    `/private/tmp/daylight_sad_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- No-lookahead handling: daylight state is deterministic and known in advance,
  so each ES session uses only its own calendar-date daylight features.
- Feature set: daylight hours, night hours, short-/long-day pressure, fall SAD
  pressure, winter recovery pressure, annual sine/cosine, solstice distances,
  seasonal flags, rolling changes/ranks/z-scores/mean gaps, SAD-onset shock,
  and daylight-recovery shock.
- Screen mechanics: session-level ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES up/down
  filters, and long/short directions.
- Result summary: `243,264` no-lookahead rows evaluated over `3,786` ES
  sessions and `248` daylight-derived features.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Top mean-reversion-shaped row: `annual_cos_mean21 <= -0.926323`, prior-down
  long `10:30 -> 12:00`; early n44/PF `0.425`, WFA n107/PF `2.585`/MAR
  `25.273`, core n23/PF `5.843`, incubation n5/PF `7.016`, full n156/PF
  `1.811`. This is a sparse seasonal artifact, not a candidate.
- Best dense WFA row: `fall_sad_pressure_mean252 <= 0.423907`, prior-up long
  `09:35 -> 15:30`; early n123/PF `1.015`, WFA n522/PF `1.214`/MAR `0.908`,
  core n174/PF `1.355`, incubation n46/PF `1.112`, full n691/PF `1.178`.
  This is not mean-reversion-shaped and is far below WFA PF.
- Promotion decision: do not stage. Deterministic daylight/SAD state produces
  sparse calendar artifacts or dense rows far below WFA PF. Do not rerun simple
  daylight length, night length, SAD pressure, fall onset, winter recovery,
  solstice distance, annual sine/cosine, rank, z-score, or mean-gap variants
  without materially different non-calendar confirmation and exceptional split
  robustness.

## Post-SAD Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the daylight outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_daylight_sad.csv`.
- Scope: scanned `140` `/private/tmp/*top.csv`, `*all.csv`, and `*summary.csv`
  files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - The daylight `all` and `top` files each had `0` pass, `0` near, and `0`
    loose rows.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES CDC ILINet Disease-Activity Screen

- Status: rejected before staged implementation.
- Why tested: CDC ILINet is a no-cost public-health / disease-stress source,
  distinct from transportation mobility, Wall Street weather, news sentiment,
  WUI uncertainty, ES/MES divergence, liquidity sweep, and accepted
  trend/orderflow continuation. The intended translation was mean reversion
  after public-health stress or relief states, but it still needed dense,
  split-stable ES behavior.
- Academic framing: viral-disease/economic-activity and pandemic-market-impact
  literature supports disease activity as a macro and uncertainty state. I used
  Adda-style viral-disease/economic-activity logic, Baker/Bloom/Davis/Kost/
  Sammon/Viratyosin COVID market-uncertainty work, and Karlsson/Nilsson/Pichler
  pandemic economic-performance work as source-family support, not as accepted
  causal evidence for an ES intraday rule.
- Source audit:
  - Official CDC FluView Interactive page:
    `https://www.cdc.gov/fluview/overview/fluview-interactive.html`.
  - Official FluView dashboard:
    `https://gis.cdc.gov/grasp/fluview/fluportaldashboard.html`.
  - Metadata endpoint:
    `https://gis.cdc.gov/grasp/flu2/GetPhase02InitApp?appVersion=Public`.
  - Download endpoint used by the dashboard:
    `https://gis.cdc.gov/grasp/flu2/PostPhase02DataDownload`.
  - Request scope: national ILINet, `DatasourceDT` ID `1`, `RegionTypeId` `3`,
    subregion `0`, all enabled seasons.
  - Raw zip: `/private/tmp/cdc_ilinet_national_1997_2026.zip`.
  - Parsed raw cache: `/private/tmp/cdc_ilinet_national_raw.csv`.
  - Feature cache: `/private/tmp/cdc_ilinet_national_features.csv`.
  - Scratch script: `/private/tmp/cdc_ilinet_es_screen.py`.
  - Screen results:
    `/private/tmp/cdc_ilinet_es_screen_all.csv` and
    `/private/tmp/cdc_ilinet_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `1,497` weekly national ILINet rows from MMWR week
  `1997-40` through `2026-22`.
- No-lookahead handling: each source week became eligible only after MMWR week
  end plus `7` calendar days plus one business day. This is conservative for a
  dashboard source and avoids same-week surveillance leakage; any future pass
  would still require exact CDC release-timing validation.
- Feature set: weighted ILI, unweighted ILI, ILI total, ILI visit share,
  weighted-minus-unweighted ILI, pediatric/adult/senior ILI shares, disease
  stress and relief composites, 1/2/4/8/13-week changes and percentage changes,
  4/8/13/26/52-week ranks, z-scores, and mean gaps.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `220,992` diagnostic rows across `3,786` eligible sessions
  and `211` disease-derived features.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `2` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `1` row with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best loose row: `ili_total_pct2 >= 0.191983`, no prior filter, long
  `11:00 -> 15:30`; early n179/PF `1.278`, WFA n476/PF `1.459`/MAR `4.033`,
  core n91/PF `1.557`, incubation n68/PF `1.037`/MAR `0.464`, and full
  n723/PF `1.345`. This fails WFA density and incubation PF/MAR.
- Best WFA500/PF1.4 row: `weighted_ili_chg1 >= 0.131470`, no prior filter,
  long `10:00 -> 15:30`; early n153/PF `1.136`, WFA n511/PF `1.400`/MAR
  `3.292`, core n111/PF `1.428`, incubation n71/PF `1.029`/MAR `0.364`, and
  full n735/PF `1.300`.
- Best visible mean-reversion diagnostic was sparse: `senior_share_z13 >=
  1.799185`, prior-down long `10:00 -> 15:59`; early n48/PF `0.853`, WFA
  n108/PF `1.906`, core n40/PF `2.244`, incubation n12/PF `3.449`, and full
  n168/PF `1.821`.
- Promotion decision: do not stage. CDC ILINet is a clean independent public
  source with enough history, but simple disease-activity state does not produce
  a dense split-stable ES mean-reversion branch. The only loose rows are weak
  broad long diagnostics with poor incubation robustness. Do not rerun simple
  CDC ILINet weighted ILI, unweighted ILI, ILI total/share, age-share, ILI
  change, disease-stress rank, z-score, or mean-gap variants without exact CDC
  release-timing validation and a materially different execution signal.

## Post-CDC ILINet Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the CDC ILINet
  disease-activity outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_cdc_ilinet.csv`.
- Scope: scanned `130` `/private/tmp/*top.csv`, `*all.csv`, and `*summary.csv`
  files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `17` files with near flags.
  - `345` near-flagged rows.
  - `2` files with loose flags.
  - `4` loose-flagged rows.
- CDC ILINet added only loose diagnostics and no pass/near flags. The remaining
  near rows are already rejected or covered families: Chicago Fed NFCI/CFNAI,
  House filing-pressure, BLS price pressure, and NAAIM exposure.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## EIA Electricity-Demand Source Gate

- Status: rejected at the source-access gate in the current environment; no ES
  screen was run.
- Why considered: electricity generation, retail sales, or load could be a
  no-cost official real-activity / physical-demand source, distinct from FHWA
  VMT, rail freight, TSA travel demand, CDC disease activity, and accepted
  price/orderflow continuation.
- Source probe:
  - Official EIA v2 monthly electric-power operational-data route for U.S.
    generation returned HTTP `403`.
  - Official EIA v2 monthly electricity retail-sales route for U.S. sales
    returned HTTP `403`.
  - Official EIA v2 daily RTO/region route for grid data returned HTTP `403`.
  - Local environment check found no `EIA_API_KEY`, `EIA_KEY`, or `EIA_TOKEN`.
- Decision: do not screen now. Reopen only with an official EIA API key or a
  durable public bulk file, then validate release timing before using any
  current-history electricity series.
- Do not rerun simple EIA electricity generation, retail sales, load, grid
  demand, power-output growth, electricity-demand rank, or electricity-demand
  z-score variants until the source gate is cleared.

## ES U.S. Drought Monitor Climate-Stress Screen

- Status: rejected before staged implementation.
- Why tested: national drought/climate stress is an official physical-risk /
  real-activity source, distinct from local Wall Street weather/cloud cover,
  geomagnetic mood, transportation mobility, CDC disease activity,
  quote-liquidity sweep, ES/MES divergence, and accepted trend/orderflow
  continuation.
- Academic framing: climate/drought market-efficiency and economic-output
  literature supports drought state as a macro physical-risk variable. I used
  Hong/Li/Xu-style climate-risk evidence, Dell/Jones/Olken temperature and
  economic-growth evidence, and drought cost-of-capital research as source-
  family support, not as accepted causal evidence for an ES intraday rule.
- Source audit:
  - Official U.S. Drought Monitor / NDMC data-services percent-area endpoint:
    `https://usdmdataservices.unl.edu/api/USStatistics/GetDroughtSeverityStatisticsByAreaPercent`.
  - Official DSCI endpoint:
    `https://usdmdataservices.unl.edu/api/USStatistics/GetDSCI`.
  - Scope: `aoi=conus`, `statisticsType=1`, `startdate=1/1/2000`,
    `enddate=6/9/2026`.
  - Percent-area raw cache: `/private/tmp/usdm_conus_area_percent_raw.csv`.
  - DSCI raw cache: `/private/tmp/usdm_conus_dsci_raw.csv`.
  - Merged raw cache: `/private/tmp/usdm_conus_drought_raw.csv`.
  - Feature cache: `/private/tmp/usdm_conus_drought_features.csv`.
  - Scratch script: `/private/tmp/usdm_drought_es_screen.py`.
  - Screen results:
    `/private/tmp/usdm_drought_es_screen_all.csv` and
    `/private/tmp/usdm_drought_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `1,380` weekly CONUS rows from `2000-01-04` through
  `2026-06-09`.
- No-lookahead handling: each Tuesday map date became ES-eligible on Thursday,
  matching the official Thursday morning USDM release before RTH. Any future
  pass would still need exact release-time validation if traded live before
  09:35 ET.
- Feature set: cumulative D0-D4 percent area, DSCI, moderate/severe/extreme/
  exceptional-only area, weighted drought pressure, severe/extreme shares of
  drought, drought relief and stress composites, 1/2/4/8/13/26-week changes and
  percentage changes, and 4/8/13/26/52/104-week ranks, z-scores, and mean gaps.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `482,112` diagnostic rows across `3,786` eligible sessions
  and `442` drought-derived features.
  - `0` pass-like rows.
  - `1` near-like row.
  - `2` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Lone near row: `moderate_only_pct1 <= -0.035103`, prior-up long
  `11:00 -> 15:30`; early n140/PF `0.933`, WFA n404/PF `1.435`/MAR `1.436`,
  core n71/PF `1.585`, incubation n63/PF `1.151`/MAR `1.295`, and full
  n607/PF `1.316`. This is prior-up long continuation, not mean reversion, and
  still misses WFA PF and density.
- Best loose sibling: same condition, prior-up long `14:30 -> 15:30`; early
  n140/PF `0.600`, WFA n404/PF `1.473`/MAR `1.789`, core n71/PF `1.567`,
  incubation n63/PF `1.015`/MAR `0.151`, and full n607/PF `1.248`.
- Promotion decision: do not stage. USDM is a clean independent official source,
  but national drought state does not produce a pass-shaped or mean-reversion ES
  branch. Do not rerun simple U.S. Drought Monitor D0-D4, DSCI, drought
  severity, drought relief/worsening, drought pressure, drought rank, drought
  z-score, or climate-stress variants without a materially different execution
  signal or cross-asset confirmation.

## Post-USDM Drought Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the USDM drought
  outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_usdm_drought.csv`.
- Scope: scanned `132` `/private/tmp/*top.csv`, `*all.csv`, and `*summary.csv`
  files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `347` near-flagged rows.
  - `4` files with loose flags.
  - `8` loose-flagged rows.
- USDM added one near/loose row and one additional loose row, both rejected
  above as weak continuation diagnostics. The remaining near rows are already
  rejected or covered families: Chicago Fed NFCI/CFNAI, House filing-pressure,
  BLS price pressure, and NAAIM exposure.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES EPA New York Metro AQI Pollution-State Screen

- Status: rejected before staged implementation.
- Why tested: local air pollution is a no-cost official environmental /
  investor-mood source, distinct from local weather/cloud cover, geomagnetic
  mood, drought/climate stress, CDC disease activity, transportation mobility,
  ES/MES divergence, quote-liquidity sweep, and accepted trend/orderflow
  continuation.
- Academic framing: air-pollution and investor-behavior literature supports a
  plausible mood/attention channel, especially Heyes/Neidell/Saberian evidence
  on PM2.5 near the NYSE and S&P 500 behavior. This was treated as
  source-family support only; the ES intraday translation still had to be
  split-stable after current costs.
- Source audit:
  - EPA AirData pre-generated file index:
    `https://aqs.epa.gov/aqsweb/airdata/download_files.html#AQI`.
  - EPA daily AQI report page:
    `https://www.epa.gov/outdoor-air-quality-data/air-quality-index-daily-values-report`.
  - EPA daily-download page states recent ozone, PM2.5, and PM10 data can come
    from AirNow until AQS data replace them.
  - Geographic scope: New York-Newark-Jersey City, NY-NJ-PA CBSA, code `35620`.
  - 2010-2025 source: `daily_aqi_by_cbsa_YEAR.zip` AirData annual files.
  - 2026 source: EPA SAS broker report
    `dataprog.ad_rep_aqi_daily_drupal_airnow_xso2_ca.sas` with `poll=all`,
    `year=2026`, `cbsa=35620`.
  - Raw directory: `/private/tmp/epa_airdata_nyc_cbsa`.
  - Combined raw cache: `/private/tmp/epa_nyc_cbsa_aqi_raw.csv`.
  - Feature cache: `/private/tmp/epa_nyc_cbsa_aqi_features.csv`.
  - Scratch script: `/private/tmp/epa_nyc_aqi_es_screen.py`.
  - Screen results:
    `/private/tmp/epa_nyc_aqi_es_screen_all.csv` and
    `/private/tmp/epa_nyc_aqi_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `5,959` daily New York metro rows from `2010-01-01`
  through `2026-06-12`.
- No-lookahead handling: each AQI observation became ES-eligible only from the
  next business day, so same-session trades used completed prior-day AQI only.
  Any future pass would need monitor-level point-in-time validation if using
  same-day AirNow/AQS updates.
- Feature set: overall AQI, pollutant-specific AQI where available, main
  pollutant flags, PM2.5 and ozone dominance, PM2.5-minus-ozone spread,
  moderate/bad AQI flags, AQI changes, percentage changes, rolling means, ranks,
  z-scores, mean gaps, and pollution stress/relief composites.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `129,568` diagnostic rows across `3,786` eligible sessions
  and `182` AQI-derived features.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass/near/loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best score row: `overall_aqi_mean252 >= 60.011905`, prior-up short
  `13:30 -> 15:59`; early n507/PF `0.613`, WFA n840/PF `0.933`, core
  n120/PF `1.908`, incubation n20/PF `1.993`, and full n1367/PF `0.874`.
- Best broad long diagnostic: `overall_aqi_from_mean10 <= -8.1`, no prior
  filter, long `09:35 -> 15:30`; early n291/PF `0.824`, WFA n688/PF `1.149`,
  core n134/PF `1.936`, incubation n117/PF `1.691`, and full n1096/PF `1.217`.
- Promotion decision: do not stage. NYC metro AQI is a clean independent source
  with full current coverage through the ES cache, but prior-day pollution state
  does not produce even a loose ES intraday edge. Do not rerun simple EPA/AirNow
  AQI, PM2.5, ozone, AQI change, air-pollution stress, air-pollution relief,
  pollution rank, or pollution z-score variants without a materially different
  execution signal or a point-in-time monitor-level PM2.5 reconstruction.

## Post-EPA NYC AQI Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the EPA AQI outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_epa_nyc_aqi.csv`.
- Scope: scanned `134` `/private/tmp/*top.csv`, `*all.csv`, and `*summary.csv`
  files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `347` near-flagged rows.
  - `4` files with loose flags.
  - `8` loose-flagged rows.
- EPA AQI produced no pass, near, or loose flags. The remaining near rows are
  already rejected or covered families: Chicago Fed NFCI/CFNAI, House
  filing-pressure, BLS price pressure, NAAIM exposure, and USDM continuation
  diagnostics.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## TSA Checkpoint Passenger-Throughput Source-Horizon Audit

- Status: rejected at the data-horizon gate; no ES screen run.
- Why checked: this is an official daily travel-demand / mobility source,
  distinct from FHWA road VMT, AAR/BTS rail freight, Census retail demand,
  accepted orderflow/trend systems, liquidity sweep, and ES/MES divergence.
  The intended ES translation would be mean reversion after air-travel demand
  shocks, using checkpoint throughput as a high-frequency service-consumption
  and mobility proxy.
- Source audit:
  - Official current TSA page:
    `https://www.tsa.gov/travel/passenger-volumes`.
  - Official annual archive pages:
    `https://www.tsa.gov/travel/passenger-volumes/2019` through
    `https://www.tsa.gov/travel/passenger-volumes/2025`.
  - Raw HTML caches:
    `/private/tmp/tsa_passenger_volumes_{2019..2026}.html`.
  - Parsed raw cache: `/private/tmp/tsa_checkpoint_throughput_raw.csv`.
- Source coverage: parsed `2,719` daily rows from `2019-01-01` through
  `2026-06-11`.
- Update timing: the current TSA page says passenger travel numbers are updated
  Monday through Friday by `9 a.m.`; holiday weeks may be delayed. A future
  short-history pilot would still need explicit publication-lag handling.
- Academic framing: travel-demand and passenger-traffic research supports using
  air passenger activity as a mobility/service-demand proxy. This was treated
  only as a source-family rationale because the history is too short for the
  standard ES acceptance workflow.
- Promotion decision: do not screen under the default protocol. The official
  source begins in 2019, so it has no `2011-2014` early-history coverage and
  only a short `2019-2024` WFA-like span dominated by the COVID collapse and
  recovery. Do not rerun simple TSA passenger throughput, air-travel demand,
  passenger-volume change, travel-demand rank/z-score, or air-mobility shock
  variants unless a longer official point-in-time source is found or a
  predeclared short-history pilot policy is approved.

## ES AAR/BTS Rail-Freight Activity Screen

- Status: rejected before staged implementation.
- Why tested: this is a transportation/freight real-activity source, distinct
  from FHWA road VMT, accepted orderflow/trend systems, liquidity sweep, ES/MES
  divergence, BLS price pressure, and Census trade-balance state. The intended
  ES translation was mean reversion after freight-activity shocks: unusually
  weak or strong rail shipment state can proxy industrial demand and goods-flow
  stress, but the intraday ES rule still has to be dense and split-stable.
- Source audit:
  - No prior repo coverage for AAR/rail-freight traffic was found.
  - Data.gov/BTS dataset identifier:
    `https://data.transportation.gov/api/views/uyr2-7q4x`.
  - Data.gov describes the source as monthly carload and intermodal units from
    AAR/BTS, but `data.transportation.gov` Socrata CSV/API routes returned
    HTTP 503 from the shell. A BTS methodology-page probe returned HTTP 403.
  - FRED graph CSV routes for BTS/AAR rail series were reachable and were used
    only for this scratch screen:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=RAILFRTCARLOADSD11`
    and
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=RAILFRTINTERMODALD11`.
  - FRED CSV caches:
    `/private/tmp/fred_RAILFRTCARLOADSD11.csv` and
    `/private/tmp/fred_RAILFRTINTERMODALD11.csv`.
  - Parsed raw cache: `/private/tmp/fred_bts_aar_rail_freight_raw.csv`.
  - Feature cache: `/private/tmp/fred_bts_aar_rail_freight_features.csv`.
  - Focused screen results:
    `/private/tmp/fred_bts_aar_rail_freight_es_screen_all.csv` and
    `/private/tmp/fred_bts_aar_rail_freight_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `315` monthly rows from `2000-01-31` through
  `2026-03-31` for rail carloads and intermodal units.
- No-lookahead handling: each monthly observation became eligible only after
  month-end plus `45` calendar days plus one business day. Any future pass
  would still require a working primary BTS/AAR source plus exact release/vintage
  validation because this scratch screen used FRED current-history CSVs.
- Feature set: rail carloads, intermodal units, total rail units, intermodal
  share, carload share, intermodal-minus-carloads, intermodal/carloads ratio,
  total rail momentum, 12-month growth, intermodal/carload growth gap,
  rail-mix shift, and goods-pressure composites; 1/3/6/12-month changes and
  percentage changes, 3/6/12-month mean gaps, and 12/24/60/120-month ranks,
  momentum ranks, and z-scores.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `92,774` positive/interesting diagnostic rows retained across
  `3,913` eligible ES sessions.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` mean-reversion pass-like rows.
  - `0` mean-reversion near-like rows.
  - `0` mean-reversion loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best visible mean-reversion row: `rail_total_mom3 >= 0.035118`, prior-down
  long `11:00 -> 15:59`; early n39/PF `1.611`/average `$150.77`, WFA
  n102/PF `1.308`/MAR `1.467`/average `$80.78`, core n25/PF `1.069`,
  incubation n12/PF `4.604`, and full n163/PF `1.419`. This is far below the
  WFA/core/incubation density required for staged promotion.
- Promotion decision: do not stage. Rail-freight activity is a cleanly
  different economic-activity thesis, but the ES intraday translation produces
  no pass/near/loose rows, and the best visible mean-reversion diagnostics are
  too sparse. Do not rerun simple AAR/BTS carload level, intermodal level, rail
  total, rail growth, rail mix, carload/intermodal spread, rank, or z-score
  variants without a working primary BTS/AAR source and materially different
  execution structure.

## Post-Rail-Freight Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the rail-freight
  outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_rail_freight.csv`.
- Scope: scanned `128` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `17` files with near flags.
  - `345` near-flagged rows.
- The rail screen produced no near/loose flags. The remaining near rows are
  already rejected or covered families: Chicago Fed NFCI/CFNAI, NAAIM exposure,
  House filing-pressure, the FHWA VMT continuation near row, and BLS
  price-pressure outputs.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES FHWA VMT Mobility-State Screen

- Status: rejected before staged implementation.
- Why tested: this is a no-cost official transportation/activity source,
  distinct from accepted trend/orderflow continuation, liquidity sweep,
  ES/MES divergence, WUI/CMDI uncertainty/credit stress, BLS price pressure,
  and Census trade-balance state. The intended ES translation was mean
  reversion after real-activity/mobility pressure states: unusually weak or
  rebounding travel demand can proxy changing consumer/activity regimes, but
  the intraday ES rule still has to be dense and split-stable.
- Academic framing: transportation-output and VMT/economic-activity research
  supports treating mobility as a macro activity state. This screen used that
  support only as a source-family rationale, not as accepted causal evidence for
  an ES intraday strategy.
- Source audit:
  - Official FHWA Traffic Volume Trends page:
    `https://www.fhwa.dot.gov/policyinformation/travel_monitoring/tvt.cfm`.
  - Official FHWA April 2026 workbook:
    `https://www.fhwa.dot.gov/policyinformation/travel_monitoring/26aprtvt/26aprtvt.xlsx`.
  - The live BTS Socrata TSI endpoint was checked first but returned HTTP 503
    from the shell, so FHWA VMT was used as the accessible official
    transportation/activity source.
  - Parsed raw cache: `/private/tmp/fhwa_vmt_raw.csv`.
  - Feature cache: `/private/tmp/fhwa_vmt_features.csv`.
  - Focused screen results:
    `/private/tmp/fhwa_vmt_mobility_es_screen_all.csv` and
    `/private/tmp/fhwa_vmt_mobility_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `316` monthly rows from `2000-01-31` through
  `2026-04-30` from the workbook `SAVMT` sheet, using not-seasonally-adjusted
  VMT and seasonally adjusted VMT.
- No-lookahead handling: each monthly source observation became eligible only
  after month-end plus `45` calendar days plus one business day. Any future pass
  would still require exact FHWA release/vintage validation because the current
  workbook contains revised/current-history observations.
- Feature set: VMT level, seasonality gap, SA/NSA ratio, one- and three-month
  SA momentum, 12-month SA/NSA growth, mobility rebound pressure, year-over-year
  acceleration, and three-month SA acceleration; 1/3/6/12-month changes and
  percentage changes, 3/6/12-month mean gaps, and 12/24/60/120-month ranks,
  momentum ranks, and z-scores.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `69,041` positive/interesting diagnostic rows retained across
  `3,913` eligible ES sessions.
  - `0` pass-like rows.
  - `1` near-like row.
  - `0` loose-shape rows.
  - `0` mean-reversion pass-like rows.
  - `0` mean-reversion near-like rows.
  - `0` mean-reversion loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Lone near row, not a mean-reversion candidate:
  `vmt_sa_minus_nsa_pct1 <= -1.036159`, prior-up long `09:35 -> 12:00`;
  early n176/PF `0.838`/average `-$18.64`, WFA n416/PF `1.457`/MAR
  `4.615`/average `$87.91`, core n91/PF `1.840`, incubation n41/PF
  `1.628`/MAR `1.994`, and full n654/PF `1.371`.
- Best visible mean-reversion diagnostic:
  `vmt_sa_mom3_pct1 >= -0.576286`, prior-down long `11:00 -> 15:30`;
  early n216/PF `0.810`/average `-$32.60`, WFA n570/PF `1.277`/MAR
  `5.965`/average `$93.93`, core n147/PF `1.356`, incubation n68/PF
  `1.382`/MAR `2.055`, and full n887/PF `1.217`.
- Promotion decision: do not stage. FHWA VMT is a clean independent official
  public source, but it does not produce a pass-shaped ES mean-reversion branch.
  The only near-like row is prior-up long continuation, and the visible
  mean-reversion diagnostics fail early-history robustness and dilute below WFA
  PF `1.4`/`1.5`. Do not rerun simple VMT level, VMT growth, SA/NSA VMT gap,
  VMT momentum, mobility rebound, VMT rank, or VMT z-score variants without
  exact point-in-time FHWA release validation and materially different execution
  structure.

## Post-FHWA Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the FHWA VMT
  outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_fhwa_vmt.csv`.
- Scope: scanned `126` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `17` files with near flags.
  - `345` near-flagged rows.
- The only new FHWA near row is rejected in the section above because it is
  prior-up long continuation, not mean reversion. The remaining near rows are
  already rejected or covered families: Chicago Fed NFCI/CFNAI, NAAIM exposure,
  House filing-pressure, and BLS price-pressure outputs.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES Census Goods Trade-Balance / External-Demand Pressure Screen

- Status: rejected before staged implementation.
- Why tested: this is a no-cost official goods-trade and external-demand source,
  distinct from BLS producer/import-export price pressure, CPI/breakeven
  inflation, WUI uncertainty, CMDI credit stress, ES/MES divergence,
  liquidity sweep, and accepted trend/orderflow continuation. The intended ES
  translation was mean reversion after external-demand pressure states:
  trade-deficit shifts, import/export growth gaps, and import intensity may
  proxy macro pressure, but any ES intraday rule must still be dense and
  split-stable.
- Academic framing: international-macro current-account / external-imbalance
  literature and macro-news asset-pricing logic motivate goods-trade state as a
  macro risk variable. This was treated as a source-family screen, not accepted
  causal evidence for an ES intraday rule.
- Source audit:
  - Official Census page:
    `https://www.census.gov/foreign-trade/balance/c0004.html`.
  - Page title: `Trade in Goods with World, Seasonally Adjusted`.
  - HTML cache: `/private/tmp/census_goods_trade_c0004.html`.
  - Parsed raw cache: `/private/tmp/census_goods_trade_balance_raw.csv`.
  - Feature cache: `/private/tmp/census_goods_trade_balance_features.csv`.
  - Screen results: `/private/tmp/census_goods_trade_balance_es_screen_all.csv`
    and `/private/tmp/census_goods_trade_balance_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `448` monthly rows from `1989-01-31` through
  `2026-04-30` for seasonally adjusted goods exports, imports, and balance.
- No-lookahead handling: each monthly observation became eligible only after
  source month-end plus `45` calendar days plus one business day. Any future
  promotion would still require exact Census release/vintage validation because
  the public HTML page is current history.
- Feature set: goods exports, goods imports, goods balance, goods deficit,
  total goods trade, import/export ratio, deficit share of total trade, balance
  share of imports, export-minus-import growth gaps, import-minus-export growth
  gaps, and external-demand pressure; 1/3/6/12-month changes and percentage
  changes, 3/6/12-month mean gaps, and 12/24/60/120-month ranks, momentum ranks,
  and z-scores.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `102,676` positive/interesting diagnostic rows retained.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `2` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best WFA500/PF row:
  `goods_imports_sa_mil_pct_from_mean12 <= 0.013773`, prior-down long
  `14:30 -> 15:59`; early n199/PF `0.594`/average `-$43.88`, WFA n568/PF
  `1.443`/MAR `3.588`/average `$79.13`, core n19/PF `5.856`, incubation
  n87/PF `0.842`, and full n854/PF `1.194`.
- Best more balanced diagnostic:
  `external_demand_pressure_3m_from_mean3 <= -0.002083`, prior-down long
  `11:00 -> 15:30`; early n235/PF `0.831`/average `-$26.70`, WFA n526/PF
  `1.382`/MAR `5.840`/average `$123.80`, core n114/PF `1.403`, incubation
  n55/PF `1.460`, and full n849/PF `1.303`.
- Promotion decision: do not stage. Census goods-trade pressure produces no
  pass-like, near-like, or loose-shape rows. The most attractive diagnostics are
  prior-down long reversals that fail early-history robustness and either miss
  WFA PF `1.5` or fail incubation/core density. Do not rerun simple goods
  exports, goods imports, goods balance, trade deficit, import/export ratio,
  deficit share, export/import growth gap, external-demand pressure, rank,
  z-score, or mean-gap variants without exact point-in-time Census release
  validation and materially different execution structure.

## Post-Census-Trade Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the Census
  goods-trade outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_census_trade_balance.csv`.
- Scope: scanned `124` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `515` near-flagged rows.
- The Census screen produced no near/loose flags. The remaining near rows are
  already rejected or covered families: BLS price pressure, Chicago Fed
  NFCI/CFNAI, NAAIM exposure, House filing-pressure, and news-risk ensemble
  outputs.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES BLS Producer / Import-Export Price Pressure Screen

- Status: rejected before staged implementation.
- Why tested: this is a no-cost official input-cost / terms-of-trade pressure
  source, distinct from CPI/breakeven inflation, Beige Book inflation text, WUI
  uncertainty, CMDI credit stress, ES/MES divergence, liquidity sweep, and
  accepted trend/orderflow continuation. The intended ES translation was
  mean reversion after macro cost-pressure states: producer/import/export price
  shocks can proxy temporary risk-premium, margin, and liquidity-pressure
  regimes, but the intraday rule still has to be dense and split-stable.
- Academic framing: inflation/news and input-cost shock literature supports
  price indexes as macro state variables, while price-pressure mean-reversion
  literature motivates fading temporary pressure rather than trading it as pure
  continuation. This was treated as a source-family screen, not as accepted
  causal evidence for an ES intraday rule.
- Source audit:
  - Official BLS public API:
    `https://api.bls.gov/publicAPI/v2/timeseries/data/`.
  - FRED graph/data routes for the same family timed out from the shell, and
    BLS static time-series files returned BLS `Access Denied`; the BLS API
    succeeded without a registration key.
  - BLS series:
    `WPU00000000`, `WPUFD49207`, `WPSFD49207`, `WPU061`, `WPUID61`,
    `EIUIR`, `EIUIQ`, and `EIUIREXFUELS`.
  - API caches:
    `/private/tmp/bls_ppi_import_export_pressure_api_2000_2009.json`,
    `/private/tmp/bls_ppi_import_export_pressure_api_2010_2019.json`, and
    `/private/tmp/bls_ppi_import_export_pressure_api_2020_2026.json`.
  - Parsed raw cache: `/private/tmp/bls_ppi_import_export_pressure_raw.csv`.
  - Feature cache: `/private/tmp/bls_ppi_import_export_pressure_features.csv`.
  - Focused screen results:
    `/private/tmp/bls_ppi_import_export_pressure_focused_es_screen_all.csv` and
    `/private/tmp/bls_ppi_import_export_pressure_focused_es_screen_top.csv`.
  - ES cache: `/private/tmp/es_active_rth_1m_20100606_20260529.parquet`.
- Source coverage: parsed `317` monthly rows from `2000-01-31` through
  `2026-05-31` for PPI series; import/export price series were populated
  through `2026-04-30`.
- No-lookahead handling: each monthly source observation became eligible only
  after month-end plus `45` calendar days plus one business day. Any future pass
  would still require exact BLS release/vintage validation because the API
  returns current-history observations.
- Feature set: PPI all commodities, final-demand goods, fuels/power,
  intermediate-demand goods, all-import price, all-export price, and import
  price excluding fuels; import-minus-export, import-ex-fuel-minus-import,
  PPI-minus-import/export, energy-minus-all, final-goods-minus-all,
  terms-of-trade pressure, producer-import pressure, ex-fuel import pressure,
  and energy-input pressure composites; 1/3/6/12-month changes and percentage
  changes, 3/6/12-month mean gaps, and 12/24/60/120-month ranks, momentum ranks,
  and z-scores.
- Screen mechanics: session-level no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-day ES
  up/down filters, and long/short directions.
- Result summary: `64,895` positive/interesting diagnostic rows retained.
  - `0` pass-like rows.
  - `4` near-like rows.
  - `15` loose-shape rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `15` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
  - `15` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`,
    `incubation_n >= 50`, and `incubation_pf >= 1.2`.
- Best near row: `ppi_final_sa_minus_export_price_from_mean6 <= 0.5`,
  prior-down long `10:30 -> 15:30`; early n168/PF `0.897`/average `-$17.72`,
  WFA n536/PF `1.407`/MAR `6.654`/average `$113.28`, core n111/PF `1.548`,
  incubation n73/PF `1.242`/MAR `0.928`, and full n829/PF `1.292`.
- Best dense WFA-PF row: `ppi_all_commodities_pct_from_mean6 <= 0.004005`,
  prior-down long `14:30 -> 15:59`; early n223/PF `0.496`/average `-$58.64`,
  WFA n535/PF `1.483`/MAR `3.922`/average `$91.85`, core n29/PF `1.453`,
  incubation n57/PF `0.748`, and full n846/PF `1.183`.
- Promotion decision: do not stage. The BLS price-pressure family is a clean
  independent public-source branch, but every attractive row is effectively a
  late-sample prior-down long reversal and fails early-history robustness. The
  best rows also miss at least one of WFA PF `1.5`, core density, or incubation
  robustness. Do not rerun simple PPI, import/export price, ex-fuel import,
  PPI-minus-import/export, terms-of-trade pressure, energy input-cost pressure,
  producer-import pressure, rank, z-score, or mean-gap variants without exact
  point-in-time BLS release validation and materially different execution
  structure.

## Post-BLS Scratch Candidate Refresh

- Status: no hidden saved pass candidate found after adding the BLS
  price-pressure outputs.
- Scratch output:
  `/private/tmp/current_scratch_candidate_audit_post_bls_ppi_trade.csv`.
- Scope: scanned `122` `/private/tmp/*top.csv`, `*all.csv`, and
  `*summary.csv` files, up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags.
  - `0` pass-flagged rows.
  - `19` files with near flags.
  - `515` near-flagged rows.
- The new BLS near rows are rejected in the section above. The remaining near
  rows are already rejected or covered families: Chicago Fed NFCI/CFNAI, NAAIM
  exposure, House filing-pressure, and news-risk ensemble outputs.
- Current priority remains unchanged:
  - Best non-depth independent ES mean-reversion lead:
    `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
    pending longer ES+MES `trades` history and the predeclared 2020-start
    validation protocol.
  - Best true liquidity-sweep branch:
    `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`,
    pending explicit approval for a bounded one-year ES `tbbo` pilot.

## ES U.S. Courts Bankruptcy Distress-Reversion Campaign

- Status: staged and rejected at WFA, but this is the strongest no-new-data
  independent ES mean-reversion variant found in this pass. It is not
  live-eligible.
- Why tested: U.S. bankruptcy filings are a realized legal-distress source,
  distinct from survey sentiment, credit-spread levels, ADS/WEI/CFNAI
  business-condition indexes, liquidity sweep, ES/MES microstructure
  divergence, and accepted trend/orderflow continuation. The ES translation is
  explicitly mean-reversion: after public Chapter 11 filing growth is elevated,
  buy ES only after a prior-session ES down move.
- Academic framing: Campbell, Hilscher, and Szilagyi (2008), "In Search of
  Distress Risk", and Vassalou and Xing (2004), "Default Risk in Equity
  Returns", support distress/default-risk state conditioning. This is indirect
  ES evidence; the campaign still had to clear the repo's staged gates.
- Source audit:
  - Official U.S. Courts data-table pages were scraped for Table F-2 quarterly
    bankruptcy-filings Excel links.
  - Source manifest:
    `research_artifacts/uscourts_bankruptcy_f2_quarterly_manifest_20260614.json`.
  - Local downloaded workbooks:
    `/private/tmp/uscourts_bankruptcy/f2_YYYY-MM-DD.xls[x]`.
  - Repo feature cache:
    `data/external/uscourts_bankruptcy_f2_quarterly_features.csv`.
  - Scratch feature cache:
    `/private/tmp/uscourts_bankruptcy/uscourts_bankruptcy_f2_quarterly_features_2010_2026.csv`.
  - Scratch flat diagnostic screen:
    `/private/tmp/uscourts_bankruptcy/uscourts_bankruptcy_f2_es_mean_reversion_screen_all.csv`
    and
    `/private/tmp/uscourts_bankruptcy/uscourts_bankruptcy_f2_es_mean_reversion_screen_top.csv`.
  - Campaign config:
    `configs/campaigns/bankruptcy_distress_reversion/variants/ES/1m/chapter11_yoy_prior_down_long.yaml`.
  - Campaign report:
    `data/reports/campaigns/bankruptcy_distress_reversion/ES/1m_full_history/1m/chapter11_yoy_prior_down_long/campaign_tests`.
- Source coverage: parsed `64` quarterly F-2 rows from `2010-03-31` through
  `2026-03-31`. The only unattended gap was `2015-12-31`, where no official
  Excel download link was found by the page scrape; no synthetic repair was
  applied.
- No-lookahead handling: each quarter became eligible only after quarter end
  plus `45` calendar days, moved to the next weekday when needed. The 2026-Q1
  row became eligible on `2026-05-15`.
- Feature set: national total filings, Chapter 7/11/13/other splits,
  business and nonbusiness totals, business Chapter 11, QoQ/YoY percentage
  changes, 16-quarter z-scores using prior-quarter rolling statistics,
  business share, Chapter 11 share, and business-Chapter-11 share.
- Scratch diagnostic mechanics: no-lookahead ES RTH flat holds using entries
  `09:35`, `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`,
  `15:30`, and `15:59`, one ES contract, `$30` round-turn cost, prior-session
  ES up/down filters, and long/short directions.
- Scratch diagnostic result: `7,488` screened rows, `0` pass-like rows,
  `1` near-like row, `4` loose-shape rows, and `4` mean-reversion loose rows.
  Best row was `total_ch11_yoy_pct >= 14.780168`, prior-down long
  `11:00 -> 15:30`: full n491/PF `1.242`, WFA n215/PF `1.365`, core n231/PF
  `1.149`, incubation n45/PF `1.397`.
- Campaign implementation:
  - Added entry module `bankruptcy_distress_reversion`, with as-of quarterly
    feature lookup, stale-feature protection, prior-session up/down filter, and
    signal-level stop/target metadata.
  - Registered the module in `src/propstack/strategy_modules/entry/__init__.py`.
  - Added focused tests in `tests/test_strategy_modules.py`.
  - Added campaign metadata in
    `configs/campaigns/bankruptcy_distress_reversion/campaign.yaml`.
- Final staged result:
  - Limited core grid: passed. `108/108` combinations profitable, `0` Apex
    rule-violating iterations. Top row used threshold `11.876485`, entry
    `11:00`, stop `0.03`, target `5R`: n232, net `$30,527.50`, PF `1.356`,
    MAR `1.705`, win rate `53.9%`, max drawdown `$9,130`.
  - Limited monkey: passed. Core beat monkey net profit in `95.3%` of runs and
    max drawdown in `99.4625%` of runs.
  - WFA: failed. `18` windows, no early exit, stitched OOS n409, net
    `$45,867.50`, PF `1.384`, MAR `0.642`, expectancy R `0.0207`, win rate
    `55.5%`, Apex violations `0`. It failed PF `1.5`, length-adjusted MAR
    `0.7086`, expectancy R `0.2`, and total-trades `500`. Profitable window
    rate was `50%`, and several OOS windows had zero trades.
- Promotion decision: do not promote to live, incubation, or accepted status.
  The branch is economically interesting and passed core plus monkey, but WFA
  does not meet the objective gates and the signal is too sparse/regime
  dependent. Treat this as the best current no-new-data ES-only independent
  mean-reversion candidate to study further, not as an accepted third alpha
  family. Do not rerun simple bankruptcy total, Chapter 11 growth, business
  filing growth, filing share, z-score, rank, or prior-down long variants
  without a materially different WFA repair that directly addresses sparse OOS
  windows and low expectancy R.

## ES Atlanta Fed SBU Business-Uncertainty Screen

- Status: rejected before staged implementation. This is an independent,
  academically backed ES mean-reversion source, but the corrected source-gate
  diagnostic produced `0` pass-like, `0` near-like, and `0` loose-shape rows.
- Why tested: the Atlanta Fed Survey of Business Uncertainty is a no-cost,
  official monthly panel survey of U.S. firms' one-year-ahead sales and
  employment expectations and uncertainty. It is distinct from Michigan
  consumer sentiment, NFIB small-business sentiment, SPF recession anxiety,
  ADS/WEI/CFNAI real-activity indexes, ES/MES microstructure divergence,
  quote-liquidity sweep, bankruptcy distress, and the accepted trend/orderflow
  continuation families.
- Academic framing: Altig, Barrero, Bloom, Davis, Meyer, and Parker,
  "Surveying Business Uncertainty", motivates the SBU as a firm-expectations
  and subjective-uncertainty data source. The ES thesis was indirect and
  contrarian: when public business expectations/uncertainty states imply weak
  or uncertain firm growth, buy ES only after completed intraday weakness, or
  short only after completed intraday strength.
- Source audit:
  - Official SBU page:
    `https://www.atlantafed.org/research-and-data/surveys/business-uncertainty`.
  - Official workbook downloaded to
    `/private/tmp/atlanta_sbu_data_20260614.xlsx` from
    `https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/datafiles/research/surveys/business-uncertainty/sbu-data.xlsx`.
  - Because local Python did not have `openpyxl`, the final corrected screen
    used FRED mirrors of the same core SBU series:
    `ATLSBUSRGEP` business expectations for sales-revenue growth,
    `ATLSBUSRGUP` business uncertainty for sales-revenue growth,
    `ATLSBUEGEP` business expectations for employment growth, and
    `ATLSBUEGUP` business uncertainty for employment growth.
  - Corrected feature cache:
    `/private/tmp/atlanta_sbu_business_uncertainty_corrected_features.csv`.
  - Corrected diagnostic screen:
    `/private/tmp/atlanta_sbu_business_uncertainty_corrected_es_screen_all.csv`
    and
    `/private/tmp/atlanta_sbu_business_uncertainty_corrected_es_screen_top.csv`.
  - The first scratch pass used the same four series but had the sales and
    employment expectation/uncertainty labels crossed for two FRED IDs; the
    corrected outputs above supersede
    `/private/tmp/atlanta_sbu_business_uncertainty_*`.
- Source coverage: `114` monthly SBU observations from `2016-12-01` through
  `2026-05-01`. The corrected no-lookahead merge produced `2,305` eligible ES
  sessions from `2017-01-16` through `2026-05-29`.
- No-lookahead handling: each observation month became eligible only after
  month-end plus `15` calendar days, moved to the next weekday when needed, and
  then as-of merged onto actual ES sessions. Any future pass would still require
  exact official release-date or vintage validation before campaign staging.
- Feature set: sales and employment expectation levels, sales and employment
  uncertainty levels, average expectation, average uncertainty,
  employment-minus-sales expectation gap, employment-minus-sales uncertainty
  gap, uncertainty-to-expectation ratio, 1/3/6/12-month changes, 3/6/12-month
  mean gaps, and 12/24/60-month ranks and z-scores.
- Scratch diagnostic mechanics: same-session ES RTH flat holds using prior
  RTH-open-to-entry completed moves, entries `09:35`, `10:00`, `10:30`,
  `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`, and `15:59`, one ES
  contract, `$30` round-turn cost, and only mean-reversion directions
  (`prior_down_long` and `prior_up_short`).
- Corrected diagnostic result: `2,741` feature-threshold specs, `128`
  entry/exit/side/move outcome specs, `62,019` retained positive diagnostic
  rows, `0` pass-like rows, `0` near-like rows, and `0` loose-shape rows.
  High-PF rows were tiny pockets rather than campaign candidates. The best
  score row was `uncertainty_to_expectation_chg12 <= -0.362849`,
  `prior_down_long`, `40` ticks minimum completed weakness, `09:35 -> 12:00`:
  early n0, WFA n12/PF `6.324`, core n8/PF `7.024`, incubation n8/PF `7.012`,
  full n20/PF `6.629`. The best dense WFA-400 row was
  `employment_minus_sales_uncertainty_gap_mean3 <= 0.282333`,
  `prior_down_long`, `10` ticks minimum weakness, `11:00 -> 15:59`: early
  n229/PF `0.947`, WFA n419/PF `1.295`, core n156/PF `1.368`,
  incubation n134/PF `0.743`, full n782/PF `1.076`.
- Promotion decision: do not stage SBU as a campaign. The source is legitimate
  and independent, but simple SBU sales/employment expectation, uncertainty,
  gap, ratio, rank, z-score, change, and mean-gap variants are either sparse
  high-PF pockets or dense low-PF rows with weak early/incubation robustness.
  Do not rerun simple SBU business-expectations or uncertainty state variants
  without exact release/vintage validation and a materially different execution
  confirmation signal.

## ES Liquidity-Sweep Versus ES/MES Continuation Checkpoint

- User follow-up: "what about liquidity sweep?" For ES, treat liquidity sweep as
  a separate quote/depth branch, not as the current ES/MES flow-divergence lead.
- True sweep candidate retained:
  `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`.
  It requires an approved one-year ES `tbbo` pilot cache before any staged run.
  Protocol:
  `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
- Rejected sweep-like families remain closed: price-only PDH/PDL or overnight
  high/low wick/reclaim, opening-range failed break, ICT/SMC sweep plus FVG
  retrace, and aggregate trade-side-only sweep/fade. Do not rerun these as
  "liquidity sweep" without actual quote/depth confirmation.
- Current first ranked non-depth ES mean-reversion candidate remains
  `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`,
  because it already passed limited core and monkey on the one-year aligned
  ES/MES trade-side sample and failed WFA only on short-history density/window
  gates.
- A predeclared 2020-start ES/MES validation sibling now exists at
  `configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start.yaml`.
  It must not be run until the approved ES+MES `trades` cache exists at
  `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`.
- Spend boundary: no Databento quote/depth or ES+MES trade downloads were run in
  this checkpoint. Either branch needs a fresh metadata/cost check and explicit
  approval before pulling paid data.

## ES EIA Petroleum Inventory Stress Re-Audit

- Status: rejected before staged implementation. This rechecked the reachable
  official EIA historical XLS route, so the petroleum branch should remain
  closed unless a materially different execution signal is introduced.
- Why tested: weekly petroleum inventories are a no-cost official physical
  supply/demand source, distinct from BLS input-price pressure, Census trade
  balance, drought/weather/climate stress, ES/MES microstructure divergence,
  quote-liquidity sweep, and accepted trend/orderflow continuation. Academic
  framing used Hamilton/Kilian-style oil shock and macroeconomic activity
  evidence: petroleum supply/demand stress can proxy transient macro risk
  pressure, but the ES translation still has to be split-stable after costs.
- Source audit:
  - Official EIA historical XLS files loaded successfully from `hist_xls` for
    `WCESTUS1`, `WCRSTUS1`, `W_EPC0_SAX_YCUOK_MBBL`, `WGTSTUS1`, and
    `WDISTUS1`.
  - Feature cache:
    `/private/tmp/eia_petroleum_stress_features.csv`.
  - Screen results:
    `/private/tmp/eia_petroleum_stress_es_screen_all.csv` and
    `/private/tmp/eia_petroleum_stress_es_screen_top.csv`.
  - Scratch refresh:
    `/private/tmp/current_scratch_candidate_audit_post_eia_petroleum_stress_20260614.csv`.
  - ES cache:
    `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
- Source coverage: `2,280` weekly rows after merging U.S. crude stocks excluding
  SPR, total crude stocks, Cushing crude stocks, total gasoline stocks, and
  distillate stocks. Source dates run from `1982-08-20` through `2026-06-05`
  where available; Cushing begins in `2004`.
- No-lookahead handling: each week-ended EIA observation became eligible only
  from source Friday plus seven calendar days. This is deliberately conservative
  versus exact Weekly Petroleum Status Report release timestamps and avoids
  same-day release assumptions.
- Feature set: inventory levels, 1/4/13-week changes, percentage changes,
  drawdowns, 13/26/52-week ranks, z-scores, mean gaps, total-inventory draw,
  product draw, crude-minus-product draw, Cushing share of crude stocks, and
  gasoline-plus-distillate share.
- Diagnostic mechanics: same-session ES RTH flat holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, and both no-filter rows
  plus mean-reversion rows (`prior_down_long` and `prior_up_short`) after
  completed intraday moves of 8/16/32/48 ticks.
- Result summary: `3,819` eligible ES sessions, `136` feature columns, `816`
  threshold specs, `160` outcome specs, and `36,329` retained positive
  diagnostic rows.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `0` loose-shape rows.
  - `29,011` retained mean-reversion rows, with `0` mean-reversion pass/near/
    loose rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `1` row with `wfa_n >= 500` and `wfa_pf >= 1.4`, but it was not
    mean-reversion and failed incubation badly.
  - `0` rows with `wfa_n >= 400`, `wfa_pf >= 1.4`, `incubation_n >= 50`, and
    `incubation_pf >= 1.2`.
- Best WFA500/PF row: `all_inventory_draw4_from_mean13 <= -19711.538462`,
  no prior filter, long `09:35 -> 15:30`; early n146/PF `0.955`, WFA n571/PF
  `1.416`/MAR `6.862`, core n64/PF `2.586`, incubation n51/PF `0.433`, and
  full n768/PF `1.177`.
- Best dense mean-reversion rows were weak: low gasoline-stock 26-week rank,
  prior-up short `14:30 -> 15:59`, had WFA n427/PF `1.044`, early PF `0.760`,
  incubation n63/PF `1.552`, and full PF `1.073`; low crude-ex-SPR rank had
  WFA n418/PF `1.037` and full PF `0.951`.
- Best loose-looking mean-reversion row: `products_draw4_pct_rank26 <=
  0.307692`, prior-down long `13:30 -> 15:30`; early n109/PF `0.905`, WFA
  n337/PF `1.406`, core n74/PF `1.692`, incubation n58/PF `0.834`, and full
  n504/PF `1.231`.
- Promotion decision: do not stage. Official EIA petroleum inventory state is
  valid enough to screen through the XLS path, but the ES intraday translation
  either becomes sparse high-PF event pockets or dense low-PF/holdout-failed
  exposure. Do not rerun simple crude/gasoline/distillate/Cushing inventory
  level, drawdown, rebuild, rank, z-score, product-draw, total-draw, or
  inventory-share variants without materially different non-petroleum
  confirmation.

## ES BLS Productivity / Unit-Labor-Cost Stress Screen

- Status: rejected before staged implementation. This is a distinct official
  macro cost/efficiency source, but the ES intraday mean-reversion translation
  did not clear even a pre-campaign diagnostic gate.
- Why tested: productivity and unit-labor-cost shocks are linked to production-
  based asset-pricing and labor-cost pressure research. A plausible ES
  translation is that weak real output/productivity or rising unit labor costs
  proxy slow-moving macro stress, and same-day ES weakness may partially
  mean-revert when the stress state is already known.
- Source audit:
  - Official current-history FRED graph CSV mirrors of BLS Labor Productivity
    and Costs series:
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=OPHNFB`,
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=ULCNFB`,
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=COMPRNFB`,
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=HOANBS`,
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=OUTNFB`, and
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=PRS85006092`.
  - Feature cache:
    `/private/tmp/bls_productivity_unit_labor_features.csv`.
  - Flat screen results:
    `/private/tmp/bls_productivity_unit_labor_es_screen_all.csv` and
    `/private/tmp/bls_productivity_unit_labor_es_screen_top.csv`.
  - Managed-exit rescue:
    `/private/tmp/bls_productivity_unit_labor_path_rescue_top.csv`.
  - ES cache:
    `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
- Source coverage: six quarterly BLS/FRED series with `317` source quarters from
  `1947-Q1` through `2026-Q1`; the ES screen had `3,817` eligible RTH sessions
  from `2011-01-03` through `2026-06-09`.
- No-lookahead handling: each quarterly observation became eligible only after
  quarter-end plus `90` calendar days. This deliberately excluded `2026-Q1`
  from the current ES sample and is still only a current-history diagnostic; any
  future pass would require exact BLS release/vintage validation.
- Feature set: labor productivity, unit labor cost, real compensation per hour,
  hours worked, real output, published labor-productivity annual-rate change,
  1- and 4-quarter changes/pct changes, 8/16/32-quarter ranks and z-scores,
  unit-labor-cost-minus-productivity pressure, compensation-minus-productivity
  pressure, and output-minus-hours pressure.
- Flat diagnostic mechanics: same-session ES RTH holds using entries `09:35`,
  `10:00`, `10:30`, `11:00`, `13:30`, and `14:30`, exits `12:00`, `15:30`,
  and `15:59`, one ES contract, `$30` round-turn cost, no-filter rows, and
  mean-reversion rows (`prior_down_long`, `prior_up_short`, `gap_down_long`,
  and `gap_up_short`).
- Flat result summary: `185` feature columns, `174` screened feature columns,
  and `3,132` retained positive split rows.
  - `0` pass-like rows.
  - `0` near-like rows.
  - `6` loose-shape rows, all mean-reversion rows.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.5`.
  - `0` rows with `wfa_n >= 500` and `wfa_pf >= 1.4`.
- Best loose flat row: low 8-quarter rank of four-quarter real-output change
  (`real_output_chg4_rank8 <= 0.30`), prior-down long `10:30 -> 15:30`; full
  n437/PF `1.361`, WFA n304/PF `1.377`/MAR `2.678`, core n27/PF `2.355`, and
  incubation n52/PF `1.223`. It failed WFA density/PF and core density.
- Focused managed-exit rescue: took the six loose rows plus the strongest
  bounded mean-reversion diagnostics, `20` candidate rows total, and tested
  stop-first paths with `stop_pct` `0.0025`, `0.0035`, `0.005`, `0.0075`, and
  `0.010`, and targets `1R`, `1.5R`, `2R`, `3R`, and `4R`. The rescue retained
  `232` positive rows, with `0` pass-like and `0` near-like rows.
- Best managed row: `real_output_chg4_rank16 <= 0.30`, prior-down long
  `11:00 -> 15:30`, `stop_pct=0.010`, `target_r=3.0`; full n274/PF `1.593`,
  WFA n190/PF `1.738`/MAR `6.534`, core n53/PF `1.799`, and incubation n28/PF
  `1.021`. This is a sparse current-history pocket, not a promotable campaign.
- Promotion decision: do not stage. BLS productivity/unit-labor-cost state is a
  valid official macro source, but the simple ES intraday translation either
  lacks WFA density, fails the WFA PF gate, or depends on too few quarterly
  states with weak 2025-2026 holdout behavior. Do not rerun simple productivity,
  unit-labor-cost, compensation, hours, real-output, productivity-minus-cost,
  or output-minus-hours rank/z-score/change variants without exact BLS vintage
  validation and materially different execution confirmation.

## Post-BLS-Productivity Candidate Refresh

- Status: no new independent ES mean-reversion campaign was promoted after the
  BLS productivity/unit-labor-cost rejection.
- Duplicate/source refresh: the remaining no-cost source list is still covered
  by prior ledger closures. This includes GSCPI, regional Fed manufacturing
  surveys, ICI/fund-flow/MMF/NAAIM sources, volatility/option/Treasury/
  commodity/FX lanes, labor/retail/housing/business-formation/inventory/
  capacity/utilization sources, OECD CLI, JOLTS/claims, consumer-sentiment and
  survey-expectations sources, Beige Book/FOMC text, AQI/weather/lunar/sunspot/
  daylight/DST calendar sources, and prior price-only market-structure variants.
- Scratch audit: wrote
  `/private/tmp/current_scratch_candidate_audit_post_bls_productivity_20260614.csv`
  after scanning `165` `/private/tmp/*top*.csv`, `*all*.csv`, and
  `*summary*.csv` files, reading up to `5,000` rows per file.
- Scratch audit result: `44` files had at least one interesting flag; `1` file
  had pass-flagged rows, `19` had near-flagged rows, and `12` had loose-shape
  rows. The only pass flags came from `/private/tmp/campaign_summary_mining.csv`
  and mapped to the existing ES `morning_orderflow_momentum` signed-flow
  full-stage passes, not a new mean-reversion alpha.
- The new BLS productivity files contributed `0` pass-like rows, `0` near-like
  rows, and only the six flat loose rows already rejected above. Remaining
  near/loose flags are already rejected or covered families, including Chicago
  Fed NFCI/CFNAI, House filing-pressure, BLS price pressure, NAAIM exposure,
  USDM drought, FHWA VMT, CDC ILINet, personal saving/PCE/profit-margin, and
  similar prior audits.
- Current priority remains unchanged:
  1. First: `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`
     after approved longer ES+MES `trades` history and the predeclared
     validation protocol in
     `research_artifacts/es_mes_flow_divergence_validation_protocol_20260614.md`.
  2. Second: `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`
     as a bounded one-year ES `tbbo` pilot governed by
     `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
- No paid Databento data was pulled. Rerun metadata/cost checks and get explicit
  approval before either the ES+MES `trades` validation dataset or the ES `tbbo`
  liquidity-sweep pilot.

## ES Report-Tree Reversion Audit

- Status: no hidden ES report-tree mean-reversion pass was found. This does not
  finish the third-strategy objective; it narrows the next action to the
  already ranked data-gated branches.
- Audit artifact:
  `research_artifacts/es_campaign_summary_reversion_audit_20260614.csv`.
- Scope: scanned `184` ES `campaign_test_summary.json` files under
  `data/reports/campaigns`.
- Method note: the audit used stage progression rather than the top-level
  `passed` boolean because existing accepted reports can still contain later
  legacy `acceptance_oos_test` failures.
- Reversion-like report count: `58`, using campaign/variant keywords including
  reversion, reversal, fade, sweep, gap, inventory, absorption, exhaustion,
  liquidity, and divergence.
- Only three reversion-like ES summaries reached both limited core and limited
  monkey before failing WFA:
  - `liquidity_risk_capacity_priority/ES/5m/cftc_rrp_vx_priority_long`.
  - `bankruptcy_distress_reversion/ES/1m/chapter11_yoy_prior_down_long`.
  - `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short`.
- Promotion decision: no existing report-tree ES mean-reversion candidate is
  live-eligible or sufficient for the independent third-alpha objective. The
  current actionable sequence remains:
  1. First: `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start`
     after approved longer ES+MES `trades` history and the predeclared protocol.
  2. Second: `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`
     after an approved bounded one-year ES `tbbo` pilot.
- No paid Databento data was pulled for this audit.

## ES AQR BAB/QMJ Factor-Stress Screen

- Status: rejected before staged implementation. This is an academically clean,
  independent equity-factor state thesis, but it did not produce a promotable ES
  mean-reversion campaign.
- Academic/source framing:
  - BAB used the AQR daily Betting Against Beta equity factor workbook, based on
    Frazzini and Pedersen's "Betting Against Beta" research.
  - QMJ used the AQR daily Quality Minus Junk equity factor workbook, based on
    Asness, Frazzini, and Pedersen's "Quality Minus Junk" research.
  - Thesis tested: broad equity factor stress/relief could create same-day ES
    index reversion pressure after low-beta or quality factor underperformance.
- Source/data artifacts:
  - BAB workbook:
    `/private/tmp/aqr_factor_state/bab_daily.xlsx`.
  - QMJ workbook:
    `/private/tmp/aqr_factor_state/qmj_daily.xlsx`.
  - Parsed feature caches:
    `/private/tmp/aqr_factor_state/aqr_bab_factor_features.csv` and
    `/private/tmp/aqr_factor_state/aqr_qmj_factor_features.csv`.
  - Scratch screen results:
    `/private/tmp/aqr_factor_state/aqr_bab_es_screen_all.csv`,
    `/private/tmp/aqr_factor_state/aqr_bab_es_screen_top.csv`,
    `/private/tmp/aqr_factor_state/aqr_qmj_es_screen_all.csv`, and
    `/private/tmp/aqr_factor_state/aqr_qmj_es_screen_top.csv`.
  - Durable combined top-row artifact:
    `research_artifacts/es_aqr_bab_qmj_factor_stress_top_20260614.csv`.
  - ES cache:
    `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
- Source caveat: both AQR workbooks state that AQR reconstructs full history on
  updates. The screen therefore used them only as a current-history diagnostic;
  any future pass would require a point-in-time or reproducible vintage policy.
- No-lookahead handling: each daily factor return became eligible no earlier than
  the next business-day ES session, then was carried forward only after that
  eligibility date.
- Feature set: USA daily factor return, 3/5/10/21/63-day sums and means,
  21/63/126/252-day ranks and z-scores of the daily factor return and 5-day sum,
  plus absolute, negative-stress, and positive-pressure variants.
- ES diagnostic mechanics: fixed RTH holds using entries `09:35`, `10:00`,
  `10:30`, `11:00`, `13:30`, and `14:30`; exits `12:00`, `15:30`, and `15:59`;
  one ES contract; `$30` round-turn cost; no-filter longs/shorts plus
  `prior_down_long` and `prior_up_short` mean-reversion filters.
- BAB coverage/result:
  - Parsed factor coverage: `1930-12-01` through `2026-03-31`.
  - ES screen coverage: `3,817` sessions from `2011-01-03` through `2026-06-09`.
  - Screen rows: `9,210`.
  - `0` pass-like rows, `0` near-like rows, and `2` loose-shape rows.
  - Best loose row: `bab_usa_rank126 <= 0.190476`, no-filter long
    `09:35 -> 15:59`, full n780/PF `1.389`, WFA n492/PF `1.487`, core
    n85/PF `1.316`, incubation n109/PF `1.273`. It misses promotion because WFA
    density is below 500 and WFA PF is below 1.5.
- QMJ coverage/result:
  - Parsed factor coverage: `1957-07-01` through `2026-03-31`.
  - ES screen coverage: `3,817` sessions from `2011-01-03` through `2026-06-09`.
  - Screen rows: `33,536`.
  - `0` pass-like rows, `0` near-like rows, and `4` loose-shape rows.
  - Best loose row: `qmj_usa_rank126 <= 0.198413`, no-filter long
    `09:35 -> 15:59`, full n786/PF `1.291`, WFA n501/PF `1.355`, core
    n99/PF `1.286`, incubation n107/PF `1.234`. It has enough WFA density but
    does not come close to the WFA PF gate.
- Promotion decision: do not stage BAB/QMJ factor-stress ES variants. The edge
  shape is directionally plausible but too weak after ES costs and split testing.
  Do not rerun simple BAB/QMJ level, return, sum, rank, z-score, low-factor-stress
  long, or high-factor-pressure short variants without materially different
  execution confirmation and a point-in-time vintage plan.
- Current priority remains unchanged:
  1. First: `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start`
     after approved longer ES+MES `trades` history and the predeclared protocol.
  2. Second: `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`
     after an approved bounded one-year ES `tbbo` pilot.

## Post-AQR Scratch-Candidate Audit

- Status: no unresolved saved pass-shaped ES mean-reversion candidate was found
  after adding the AQR BAB/QMJ outputs.
- Audit artifact:
  `research_artifacts/current_scratch_candidate_audit_post_aqr_20260614.csv`.
- Scope: scanned `166` scratch CSV files from top-level `/private/tmp` plus
  `/private/tmp/aqr_factor_state`, reading up to `5,000` rows per file.
- Result:
  - `0` files with positive pass flags and `0` pass-flagged rows.
  - `19` files with near flags and `347` near-flagged rows.
  - `8` files with loose flags and `20` loose rows.
- AQR contribution: BAB/QMJ added only loose rows, no pass or near rows.
  - `/private/tmp/aqr_factor_state/aqr_bab_es_screen_all.csv`: `0` pass,
    `0` near, `2` loose.
  - `/private/tmp/aqr_factor_state/aqr_qmj_es_screen_all.csv`: `0` pass,
    `0` near, `4` loose.
- The remaining near rows are already rejected or covered source families from
  prior audits, not new live-eligible evidence.
- Current actionable sequence remains data-gated:
  1. First: build and validate the predeclared ES/MES 2020-start trade-history
     sibling.
  2. Second: run the quote-confirmed ES `tbbo` liquidity-sweep pilot if the data
     download is explicitly approved.

## Data-Gated Next-Action Checkpoint

- Status: the independent ES mean-reversion objective is blocked on external
  market-data approval, not on another local source-screen pass.
- Current-state checks:
  - No local SPY/SPX/ETF minute dataset was found under `data/` for a cash-futures
    dislocation or ETF-futures basis reversion test.
  - ES orderflow absorption/exhaustion is not a fresh route: `orderflow_regime`
    `absorption_exhaustion_reversal`, `orderflow_opening_drive`
    `opening_absorption_fade`, and `opening_price_flow_divergence_fade` are
    already in the report tree and failed before WFA promotion.
  - The post-AQR scratch audit found `0` pass-flagged saved scratch rows after
    scanning `/private/tmp` and `/private/tmp/aqr_factor_state`.
- Best current non-depth candidate:
  `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start`.
  Required next step is explicit approval to obtain 2020-start ES+MES Databento
  `trades` history, then run the predeclared validation protocol in
  `research_artifacts/es_mes_flow_divergence_validation_protocol_20260614.md`.
  The existing metadata-only estimate is
  `research_artifacts/databento_es_mes_trades_20200101_20260609_cost_manifest_20260614.json`
  with sampled combined estimate about `$949.34`.
- Best true liquidity-sweep candidate:
  `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim`.
  Required next step is explicit approval for the bounded one-year ES `tbbo`
  pilot in `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
  The existing metadata-only estimate is
  `research_artifacts/databento_es_tbbo_20250609_20260609_cost_manifest_20260614.json`
  with sampled one-year RTH `tbbo` cost about `$14.88` and estimated size
  `8.08 GB`.
- Do not treat further no-cost public macro/news/factor/calendar/source scans as
  higher priority unless a genuinely new point-in-time source is introduced. The
  ledger now has repeated mechanical audits showing no unresolved saved
  pass-shaped ES mean-reversion candidate.

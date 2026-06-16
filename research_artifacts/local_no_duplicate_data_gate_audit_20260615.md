# Local No-Duplicate ES Data-Gate Audit

Date: 2026-06-15

Status: FAIL

## Purpose

This audit records the local stop condition after the corrected engine/stage
audit and fifteen active ES campaigns. Archived tests are now explicitly ignored
when checking for duplicate edges; they remain historical context only and do
not block a new campaign.

## Active Campaigns Rejected In This Run

All active campaigns used predeclared variants, costs, forced-flatten logic, and
the corrected stage gates in `src/propstack/research/campaign_stages.py`.

| Campaign | Variants | Terminal result |
| --- | ---: | --- |
| `es_mes_micro_flow_divergence_reversion` | 5 | Original variants failed before WFA. After the clarified per-failed-variant rescue rule, all five one-time parameter-only rescues were run and all failed `limited_monkey_test`; random-placebo profitable rates ranged from `0.36` to `0.47`, all with negative median PnL. |
| `es_prior_session_ibs_reversion` | 5 | All corrected variants failed core robustness; best profitable-combo rate was `0.3333333333333333`. |
| `es_connors_rsi2_mean_reversion` | 5 | All variants failed core robustness; best profitable-combo rate was `0.06172839506172839`. |
| `es_range_compression_breakout` | 5 | Four variants failed core; the only original core pass failed monkey with `percentage_profitable=0.3933333333333333` and negative median PnL. All five one-time parameter-only rescues have now been run; the ID/NR4 rescue failed monkey and the other four failed core. |
| `es_rth_intraday_risk_premium` | 5 | All fixed long-bias variants lost money after ES costs. |
| `es_overnight_intraday_reversal` | 5 | All variants failed the `0.70` core profitable-combo gate; best pocket had only `33/81` profitable combinations and zero benchmark-passing combinations. All five one-time parameter-only rescues have now been run and failed core. |
| `es_signed_orderflow_persistence` | 5 | All five own-ES signed-flow continuation variants failed the `0.70` core profitable-combo gate. All five one-time parameter-only rescues have now been run and failed core; best rescue profitable-combo rate was `0.1111111111111111`. |
| `es_opening_drive_inventory_absorption` | 5 | All five opening-drive inventory/absorption variants failed before WFA. All five one-time parameter-only rescues have now been run; the 60-minute continuation rescue failed monkey with `percentage_profitable=0.20666666666666667`, and the other four rescues failed core. |
| `es_turn_of_month_seasonality` | 5 | All five turn-of-month calendar-seasonality variants failed the `0.70` core profitable-combo gate. All five one-time parameter-only rescues have now been run and failed core; best rescue profitable-combo rate was `0.07407407407407407`. |
| `es_daily_time_series_momentum` | 5 | All five prior-daily-trend momentum variants failed the `0.70` core profitable-combo gate. All five one-time parameter-only rescues have now been run and failed core; best rescue profitable-combo rate was `0.2839506172839506`. |
| `es_late_day_intraday_momentum` | 5 | All five late-day market intraday momentum variants failed the `0.70` core profitable-combo gate. All five one-time parameter-only rescues have now been run and failed core; every original and rescue grid had `0.0` profitable combinations. |
| `es_volume_shock_liquidity_reversal` | 5 | All five volume-shock liquidity-reversal variants failed the `0.70` core profitable-combo gate. All five one-time parameter-only rescues have now been run and failed core; best rescue profitable-combo rate was `0.20987654320987653`. |
| `es_prior_day_stop_run_reclaim` | 5 | All five prior-day stop-run reclaim variants failed before WFA. All five one-time parameter-only rescues have now been run; the morning prior-high rejection rescue passed core but failed monkey with `percentage_profitable=0.32666666666666666`, while the other four rescues failed core. |
| `es_vwap_pullback_continuation` | 5 | All five VWAP pullback-continuation variants failed before WFA. All five one-time parameter-only rescues have now been run; the midday trend-reclaim rescue passed core but failed monkey with `percentage_profitable=0.18` and `median_net_profit=-3210.0`, while the other four rescues failed core. |
| `es_cftc_tff_hedging_pressure` | 5 | Initial `run1` artifacts were invalidated because the limited-core first-window sample predated non-null shifted CFTC feature coverage. All five corrected `run2` originals and all five one-time parameter-only rescues failed `limited_core_grid_test`; best rescue profitable-combo rate was `0.3333333333333333` with only `5` top-row trades. |

Updated rescue policy: each failed variant can be rescued once. Rescue attempts
may change existing fixed parameters or tunable parameter space, but not the
core strategy mechanic. Completed parameter-only rescues for all 75 active
failed ES variants were run and failed. No second rescue is permitted for those
variants.

## Duplicate-Edge Scope

Archived tests are ignored when checking whether a proposed campaign is a
duplicate edge. The duplicate gate should compare only against active research
surfaces:

- `campaigns/*/campaign.yaml`
- active variant configs under `campaigns/*/variants/`
- active reports under `backtest-campaigns/`
- current non-archived rows in `research_ledger.csv`

The following are historical evidence only and must not block a new campaign as
a duplicate edge: `_archived/`, `configs/campaigns/archive*/`,
`data/reports/campaigns/archive*/`, and archived report-refresh CSV/JSON
manifests under `_archived/research_artifacts/`.

Policy artifact:
`research_artifacts/duplicate_edge_scope_policy_20260615.md`.

## Local Data Inventory

Locally available and usable:

- Long ES Databento 1-minute OHLCV parquet history under `data/cache/databento`.
- Corrected ES Sierra aggregated trade-orderflow cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
- One-year ES/MES flow divergence caches:
  `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv` and
  `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`.
- One-year ES Databento trade-orderflow cache:
  `data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv`.
- Local shifted CFTC TFF hedging-pressure feature file:
  `data/external/cftc_tff_hedging_pressure_features.csv`, with usable non-null
  `SPX_open_interest_chg13` coverage from `2013-04-15` through `2026-05-29`.

Continuation check on the long OHLCV cache: this cache is locally usable. Under
the active-only duplicate policy, archived OHLCV-only tests do not block a new
campaign. The active rejected OHLCV/bar families from this run remain
range-compression, prior-session IBS, Connors RSI2, RTH risk premium,
overnight-intraday reversal, turn-of-month seasonality, daily time-series
momentum, late-day market intraday momentum, volume-shock liquidity
reversal, prior-day stop-run reclaim, and VWAP pullback continuation. The active
rejected Sierra aggregate-orderflow families now include ES/MES micro-flow
divergence, own-ES signed-orderflow persistence, and opening-drive
inventory/absorption. The active rejected external-positioning family is
CFTC/TFF hedging pressure.

Latest verification: `python3 -m research.preflight --skip-tests` passed with
233 active configs checked, and the active ES variant-level report sweep found
158 raw variant-level reports, 0 passes, 75 latest original reports, 75
`rescue1` reports, and 0 active variants missing `rescue1`.

Missing for the retained branches:

- No `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`.
- No long ES+MES `trades` cache from `2020-01-01`.
- No `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`.
- No local SPY/SPX/ETF minute cache for cash-futures dislocation testing.

## Retained Branches

Priority 1: ES/MES flow-divergence validation.

- Protocol:
  `research_artifacts/es_mes_flow_divergence_validation_protocol_20260614.md`.
- Required data: Databento `trades`, `ES.FUT` and `MES.FUT`, RTH only,
  `2020-01-01` through `2026-06-09`.
- Metadata-only estimate:
  `research_artifacts/databento_es_mes_trades_20200101_20260609_cost_manifest_20260614.json`.
- Estimated sampled cost: ES `$554.49`, MES `$394.85`, combined `$949.34`.
- No paid files were downloaded.

Priority 2: quote-confirmed liquidity-sweep pilot.

- Protocol:
  `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
- Required data: Databento `tbbo`, `ES.FUT`, RTH only, `2025-06-09` through
  `2026-06-09`.
- Metadata-only estimate:
  `research_artifacts/databento_es_tbbo_20250609_20260609_cost_manifest_20260614.json`.
- Estimated one-year RTH `tbbo` sample cost: `$14.88`; estimated size:
  `8.08 GB`.
- No quote/depth files were downloaded.

Both estimates must be refreshed immediately before any approved download.

## Decision

FAIL.

No ES strategy candidate currently passes the corrected research methodology.
Continuing without violating the duplicate-edge rule requires avoiding the
currently active rejected edge families above. Archived tests do not block a
fresh campaign under the active-only policy. The retained external market-data
branches remain valid next steps, but they are not the only allowed path if a
new active-only, non-duplicate local edge is proposed.

## Continuation Check

Continuation artifact:
`research_artifacts/es_goal_continuation_audit_20260615.md`.

All active failed variants have now consumed their one allowed rescue and
failed. A machine sweep of active
`backtest-campaigns/**/campaign_test_summary.json` files found no active
variant-level report with `passed=true`. The duplicate-edge check for future
campaign selection should ignore archived tests and compare only against the
active rejected campaign families listed above.

## 2026-06-16 Market-Plumbing Update

Added active failed campaign `es_market_plumbing_liquidity_capacity` using local lagged market-plumbing features. Archived market-plumbing tests were ignored for duplicate checks per policy. The campaign used a conservative one-row lagged feature file and excluded CFTC/TFF legs to avoid duplicating the active CFTC hedging-pressure family.

Valid originals: 5 `run2` reports. Variant rescues: 5 `rescue1` reports. Passes: 0. Latest verification after rescues: `python3 -m research.preflight --skip-tests` passed with 248 active configs; active sweep found 173 raw variant-level reports, 0 passes, 80 latest original reports, 80 `rescue1` reports, and 0 active variants missing `rescue1`.

The active rejected external-feature families now include CFTC/TFF hedging pressure and market-plumbing liquidity capacity. Continuing must avoid these active edges; archived tests still do not block a fresh non-duplicate campaign.

## 2026-06-16 Bankruptcy-Distress Update

Added active failed campaign `es_bankruptcy_distress_regime_reversion` using local U.S. Courts F-2 derived bankruptcy features. Archived bankruptcy tests were ignored for duplicate checks per policy. Valid originals: 5 `run2` reports after invalidating zero-trade `run1` data-window artifacts. Variant rescues: 5 `rescue1` reports. Passes: 0.

The active rejected external-feature families now include CFTC/TFF hedging pressure, market-plumbing liquidity capacity, and bankruptcy/distress regime reversion.


## 2026-06-16 Prior-Session Level Breakout Update

Added active failed campaign `es_prior_session_level_breakout_continuation` using the local Sierra RTH cache and the existing prior high/low breakout-continuation module. Archived tests were ignored for duplicate checks per policy. Valid originals: 5 `run1` reports. Variant rescues: 5 `rescue1` reports. Passes: 0.

The active rejected prior-level families now include failed-sweep reclaim/reversion and confirmed level breakout continuation. Continuing must avoid both active edges; archived tests still do not block a fresh non-duplicate campaign.


## 2026-06-16 VPIN Toxicity Continuation Update

Added active failed campaign `es_vpin_toxicity_continuation` using the local Sierra RTH cache and an OHLCV VPIN/toxicity proxy. Archived tests were ignored for duplicate checks per policy. Valid originals: 5 `run1` reports. Variant rescues: 5 `rescue1` reports. Passes: 0.

The active rejected order-flow families now include ES/MES divergence, raw signed-flow persistence, opening-drive inventory/absorption, and VPIN/toxicity proxy continuation. Continuing must avoid these active edges; archived tests still do not block a fresh non-duplicate campaign.


## 2026-06-16 Overnight Return Late-Day Momentum Update

Added active failed campaign `es_overnight_return_late_day_momentum` using the local Sierra RTH cache and the existing overnight-return late-day module. Archived tests were ignored for duplicate checks per policy. Valid originals: 5 `run1` reports. Variant rescues: 5 `rescue1` reports. Passes: 0.

The active rejected overnight/late-day families now include early overnight-intraday reversal, first/last-window late-day intraday momentum, and overnight-return late-day continuation. Continuing must avoid these active edges; archived tests still do not block a fresh non-duplicate campaign.


## 2026-06-16 Prior-Level Delta Dislocation Update

Added active failed campaign `es_prior_level_delta_dislocation` using the local Sierra RTH trade-orderflow cache and the existing prior-level delta-dislocation module. Archived tests were ignored for duplicate checks per policy. Valid originals: 5 `run1` reports. Variant rescues: 5 `rescue1` reports. Passes: 0.

The active rejected prior-level/orderflow families now include failed-sweep reclaim/reversion, confirmed level breakout continuation, and prior-level price/orderflow dislocation. Continuing must avoid these active edges; archived tests still do not block a fresh non-duplicate campaign.

Latest verification after this update: `python3 -m research.preflight --skip-tests` passed with 333 configs checked; active sweep found 105 source variants, 105 rescue configs, 228 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.


## 2026-06-16 Orderflow Absorption Exhaustion Reversal Update

Added active failed campaign `es_orderflow_absorption_exhaustion_reversal` using local Sierra same-clock orderflow ranks. Archived tests were ignored for duplicate checks per policy. Valid originals: 5 `run1` reports. Variant rescues: 5 `rescue1` reports. Passes: 0. The active rejected orderflow families now include ES/MES divergence, raw signed-flow persistence, opening-drive inventory/absorption, VPIN/toxicity proxy continuation, prior-level delta dislocation, and same-clock orderflow absorption/exhaustion reversal.

Latest verification after this update: `python3 -m research.preflight --skip-tests` passed with 348 configs checked; active sweep found 110 source variants, 110 rescue configs, 238 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`.

## 2026-06-16 Active-Only Duplicate Exhaustion Check

Archived tests remain ignored for duplicate-edge decisions. Under that scope,
the remaining local modules do not provide a clean new edge: weekday/session
bias is already active as `es_rth_intraday_risk_premium`; gap/overnight fade and
inventory modules overlap active overnight/gap reversal families; opening-range
modules overlap active compression/breakout families; intraday capitulation and
VWAP-style mean reversion overlap active Connors, volume-shock, and VWAP
families; signed-flow/orderflow-state/orderflow-combo modules overlap active
signed-flow, opening-drive, VPIN, prior-level delta-dislocation, and same-clock
absorption/exhaustion families. Quote-confirmed sweep reversion remains
data-gated by the missing `tbbo` cache.

Decision remains FAIL for the local active campaign set. No candidate strategy
report exists.

## 2026-06-16 Day-of-Week Seasonality Recheck

The active-only duplicate gate was reopened for weekday-specific seasonality
because the active RTH risk-premium campaign tested unconditional all-weekday
long exposure, while the active turn-of-month campaign tested monthly calendar
windows. A fresh active campaign, `es_day_of_week_seasonality`, was therefore
allowed as a weekly calendar anomaly test.

Result: FAIL. All five originals and all five one-time stop/target
parameter-space rescues failed `limited_core_grid_test` with `0.0`
profitable-combo rate. The active rejected calendar families now include
unconditional RTH intraday premium, turn-of-month seasonality, and
day-of-week seasonality.

Latest verification: `python3 -m research.preflight --skip-tests` passed with
363 configs checked; active sweep found 115 source variants, 115 rescue
configs, 248 raw variant-level reports, 0 passes, and 0 active variants missing
`rescue1`.


## 2026-06-16 Overnight Inventory Sweep Reversion Update

Added active failed campaign `es_overnight_inventory_sweep_reversion` using local Databento ES ETH/RTH OHLCV and an explicit roll-calendar cache. Archived overnight-inventory tests were ignored for duplicate checks per policy. This active edge is now blocked from relaunch under a new name.

Result: FAIL. Valid originals: 5 `run1` reports. Variant rescues: 5 `rescue1` reports. One original reached and failed `limited_monkey_test`; every rescue failed `limited_core_grid_test`. Passes: 0.

The active rejected overnight/prior-level families now include early overnight gap reversal, overnight-return late-day continuation, prior RTH stop-run reclaim, and completed ETH overnight high/low sweep reversion. Continuing must avoid these active edges; archived tests still do not block a fresh non-duplicate campaign.

Latest verification: `python3 -m research.preflight --skip-tests` passed with 378 configs checked; active sweep found 24 campaigns, 120 source variants, 120 rescue configs, 258 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1` report.

## 2026-06-16 Post-Overnight Active-Only Remaining Module Recheck

Archived tests remain ignored for duplicate-edge decisions. The current blocker
is active duplicate scope plus missing approved external caches, not archived
history.

Current verified active sweep: 24 active campaigns, 120 source variants, 120
`rescue1` configs, 258 raw variant-level reports, 0 passes, and 0 active
variants missing `rescue1`.

Remaining unused local entry modules were rechecked:

- `intraday_capitulation_mr` is not a fresh edge. Its completed-bar down-shock,
  low-RSI, below-running-VWAP, high-relative-volume long setup is a stricter
  expression of the active high-volume liquidity-reversal edge and overlaps the
  active Connors RSI/VWAP mean-reversion context.
- `opening_range_breakout`, `opening_range_filtered_breakout`, and
  `opening_range_inverse_breakout` are not admitted as a new local campaign.
  Active `es_range_compression_breakout` already used opening-range breakout
  variants under a Crabel/NR7 compression thesis. Dropping the compression
  requirement after those active failures would be a post-result mechanic
  relaxation, not a clean new edge.
- `morning_intraday_momentum`, `intraday_momentum_priority`,
  `morning_orderflow_momentum`, and `gao_last_half_hour_orderflow` map to the
  active intraday-momentum, opening-drive, and signed-flow/orderflow families.
- `cftc_tff_tiered_hedging_pressure` and
  `liquidity_risk_capacity_priority` map to active CFTC/TFF and
  market-plumbing/funding-liquidity families.
- `opening_gap_orderflow_fade` and `rth_gap_fade` map to active overnight/gap
  reversal and overnight-return families.
- `orderflow_recent_pocket_combo`, `trade_orderflow_state_rank`,
  `trade_orderflow_multi_pressure`, and `trade_orderflow_multi_state_rank` map
  to active signed-flow, ES/MES divergence, opening-drive, VPIN/toxicity,
  prior-level delta-dislocation, and same-clock absorption/exhaustion families.
- `quote_liquidity_sweep_reversion` remains data-gated by the missing ES TBBO
  liquidity cache.

Local external-data gate status remains unchanged:

- Present: one-year ES/MES divergence caches,
  `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv` and
  `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`.
- Missing: longer ES+MES `trades` history from `2020-01-01`.
- Missing: `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`.

Decision remains FAIL for the local active campaign set. No candidate strategy
report exists. Continuing without violating the active duplicate-edge rule
requires either an approved external-data branch or an explicit rule change from
the user.

## ES/NQ Cross-Index Lead-Lag Update - 2026-06-16

`es_nq_cross_index_lead_lag` is now an active failed campaign. It was launched
from the user-supplied cross-asset lead-lag Edge 5 using local ES and NQ Sierra
RTH order-flow caches, not external TBBO. The campaign is distinct from the
active failed ES/MES micro-flow divergence family because it tests NQ
cross-index information leadership into ES rather than same-underlying MES/ES
micro-flow reversion.

All five originals and all five one-time parameter-space rescues failed
`limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated
incubation, or frozen validation. This edge family is now blocked from relaunch
under a new active name unless the user explicitly changes the duplicate-edge
rule or supplies a materially different data/mechanic thesis.

Latest verification: `python3 -m research.preflight --skip-tests` passed with
393 configs checked; active sweep found 25 active campaigns, 125 source
variants, 125 rescue configs, 268 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## FOMC Pre-Announcement Drift Update - 2026-06-16

`es_fomc_pre_announcement_drift` is now an active failed campaign. It was
eligible when launched because no active scheduled-FOMC pre-announcement drift
campaign existed outside `_archived`, and the required data were local: ES
Sierra RTH bars plus an official scheduled FOMC calendar.

All five originals and all five one-time rescues failed before WFA. The only
rescue to pass core, `decision_day_open_long_1000/rescue1`, failed monkey and
one-tick-worse trade-path stress. This event-calendar edge is now blocked from
relaunch under a new active name unless the user explicitly changes the
duplicate-edge rule or approves a materially different pre-test thesis.

Latest verification: active sweep found 26 active campaigns, 130 source
variants, 130 rescue configs, 278 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## Volatility-Managed Intraday Premium Update - 2026-06-16

`es_volatility_managed_intraday_premium` is now an active failed campaign. It
was eligible when launched because no active lagged realized-volatility-managed
intraday premium campaign existed outside `_archived`. The required data were
local: ES Sierra RTH bars plus the derived one-session-shifted volatility
feature file.

All five originals and all five one-time rescues failed before WFA. The only
rescue to pass core, `low_10d_range_midmorning_long_1030/rescue1`, failed the
random-placebo monkey gate. This lagged-volatility state edge is now blocked
from relaunch under a new active name unless the user explicitly changes the
duplicate-edge rule or approves a materially different pre-test thesis.

Latest verification: active sweep found 27 active campaigns, 135 source
variants, 135 rescue configs, 288 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## Halloween Seasonal Premium Update - 2026-06-16

`es_halloween_seasonal_premium` is now an active failed campaign. It was
eligible when launched because no active half-year Halloween / Sell-in-May
seasonal campaign existed outside `_archived`. The required data were local ES
Sierra RTH bars and deterministic calendar-month membership.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
This half-year seasonal edge is now blocked from relaunch under a new active
name unless the user explicitly changes the duplicate-edge rule or approves a
materially different pre-test thesis.

Latest verification: active sweep found 28 active campaigns, 140 source
variants, 140 rescue configs, 298 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## Quarterly Expiration Pressure Update - 2026-06-16

`es_quarterly_expiration_pressure` is now an active failed campaign. It was
eligible when launched because no active quarterly expiration/roll-calendar
pressure campaign existed outside `_archived`, and the required data were local:
ES Sierra RTH bars plus deterministic third-Friday quarterly expiration and CME
equity-index roll-date rules.

All five originals and all five one-time rescues failed before WFA. The only
rescue to pass core, `monday_after_expiration_reversal_long_1000/rescue1`,
failed the random-placebo monkey gate with negative median net profit. This
deterministic expiration-calendar edge is now blocked from relaunch under a new
active name unless the user explicitly changes the duplicate-edge rule or
approves a materially different pre-test thesis.

Latest verification: active sweep found 29 active campaigns, 145 source
variants, 145 rescue configs, 308 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## Pre-Holiday Effect Update - 2026-06-16

`es_preholiday_effect` is now an active failed campaign. It was eligible when
launched because no active pre-holiday futures/calendar campaign existed outside
`_archived`, and the required data were local: ES Sierra RTH bars plus a
deterministic NYSE full-holiday calendar.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
The best rescue reached only `0.5` profitable combinations and zero
benchmark-passing combinations. This pre-holiday calendar edge is now blocked
from relaunch under a new active name unless the user explicitly changes the
duplicate-edge rule or approves a materially different pre-test thesis.

Latest verification: active sweep found 30 active campaigns, 150 source
variants, 150 rescue configs, 318 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## Turn-of-Year Effect Update - 2026-06-16

`es_turn_of_year_effect` is now an active failed campaign. It was eligible when
launched because no active turn-of-year/Santa-rally campaign existed outside
`_archived`, and the required data were local: ES Sierra RTH bars plus a
deterministic NYSE regular-session turn-of-year calendar.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
The best rescue reached only `0.4166666666666667` profitable combinations and
zero benchmark-passing combinations. This annual turn-of-year calendar edge is
now blocked from relaunch under a new active name unless the user explicitly
changes the duplicate-edge rule or approves a materially different pre-test
thesis.

Latest verification: active sweep found 31 active campaigns, 155 source
variants, 155 rescue configs, 328 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## BLS Macro Release-Day Drift Update - 2026-06-16

`es_bls_macro_release_day_drift` is now an active failed campaign. It was
eligible when launched because no active CPI/Employment Situation release-day
campaign existed outside `_archived`, and the required data were local/free:
ES Sierra RTH bars plus ALFRED/FRED BLS release-date downloads. It is distinct
from active FOMC pre-announcement drift because it tests BLS 08:30 ET
post-release RTH sessions and does not use release values or surprises.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
The best rescue reached only `0.5833333333333334` profitable combinations and
zero benchmark-passing combinations. This BLS macro-release calendar edge is now
blocked from relaunch under a new active name unless the user explicitly changes
the duplicate-edge rule or approves a materially different pre-test thesis.

Latest verification: active sweep found 32 active campaigns, 160 source
variants, 160 rescue configs, 338 raw variant-level reports, 0 passes, and no
active variants missing a latest original or `rescue1` report.

## Term-Structure Lead-Lag Feedback Update - 2026-06-16

`es_term_structure_lead_lag_feedback` is now an active failed campaign. It was
eligible when launched because no active ES front-vs-next-contract
term-structure lead-lag campaign existed outside `_archived`, and the required
data were local: ES Sierra RTH bars, raw Sierra ES contract files, and the
explicit ES roll calendar. It is distinct from the active failed ES/NQ
cross-index lead-lag family because it tests same-underlying front/deferred
contract dislocation, not cross-index information transfer.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
The best original reached only `0.48148148148148145` profitable combinations
with zero benchmark-passing combinations and only `4` top-combo trades. The best
rescue reached only `0.2222222222222222` profitable combinations with zero
benchmark-passing combinations and only `5` top-combo trades. This
term-structure lead-lag edge is now blocked from relaunch under a new active
name unless the user explicitly changes the duplicate-edge rule or approves a
materially different pre-test thesis.

Latest verification: active sweep found 33 active campaigns, 165 source
variants, 165 rescue configs, 348 raw variant-level reports, 0 passes, and no
active variants missing any original run or `rescue1` report.

## Monthly OPEX Pressure Update - 2026-06-16

`es_monthly_opex_pressure` is now an active failed campaign. It was eligible
when launched because no active non-quarterly monthly listed-option expiration
pressure campaign existed outside `_archived`, and the required data were
local: ES Sierra RTH bars plus a deterministic NYSE third-Friday OPEX calendar.
It is distinct from the active failed quarterly-expiration campaign because
March, June, September, and December are excluded and the thesis is monthly
listed-option pinning/unwind pressure, not quarterly futures roll pressure.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
The best original reached only `0.5555555555555556` profitable combinations
with zero benchmark-passing combinations and `12` top-combo trades. The best
rescue reached only `0.5833333333333334` profitable combinations with zero
benchmark-passing combinations and `12` top-combo trades. This monthly OPEX edge
is now blocked from relaunch under a new active name unless the user explicitly
changes the duplicate-edge rule or approves a materially different pre-test
thesis.

Latest verification: active sweep found 34 active campaigns, 170 source
variants, 170 rescue configs, 358 raw variant-level reports, 0 passes, and no
active variants missing any original run or `rescue1` report.

## VIX Expiration Pressure Update - 2026-06-16

`es_vix_expiration_pressure` is now an active failed campaign. It was eligible
when launched because no active VIX derivatives settlement pressure campaign
existed outside `_archived`, and the required data were local: ES Sierra RTH
bars plus a deterministic VIX standard expiration calendar. It is distinct from
monthly and quarterly OPEX campaigns because the event is VIX settlement tied
to SPX option SOQ mechanics, not equity/index listed-option expiration or ES
quarterly roll pressure.

All five originals and all five one-time rescues failed `limited_core_grid_test`.
The best original reached only `0.6666666666666666` profitable combinations
with zero benchmark-passing combinations and `17` top-combo trades. The best
rescue reached only `0.5833333333333334` profitable combinations with zero
benchmark-passing combinations and `17` top-combo trades. This VIX settlement
edge is now blocked from relaunch under a new active name unless the user
explicitly changes the duplicate-edge rule or approves a materially different
pre-test thesis.

Latest verification: active sweep found 35 active campaigns, 175 source
variants, 175 rescue configs, 368 raw variant-level reports, 0 passes, and no
active variants missing any original run or `rescue1` report.

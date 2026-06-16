# ES Goal Continuation Audit

Date: 2026-06-15

Decision: FAIL

## Purpose

This note records the continuation check after the clarified per-failed-variant
rescue rule was applied to the defensible local ES variants. It prevents the
search from relaunching rejected local-only campaigns, running post-result
parameter mining, or using an unapproved paid-data branch as if it were already
testable. It does not block a genuinely new local, active-only non-duplicate
edge.

## Active Campaign State

Active campaign directories currently present:

- `es_mes_micro_flow_divergence_reversion`
- `es_prior_session_ibs_reversion`
- `es_connors_rsi2_mean_reversion`
- `es_range_compression_breakout`
- `es_rth_intraday_risk_premium`
- `es_overnight_intraday_reversal`
- `es_signed_orderflow_persistence`
- `es_opening_drive_inventory_absorption`
- `es_turn_of_month_seasonality`
- `es_daily_time_series_momentum`
- `es_late_day_intraday_momentum`
- `es_volume_shock_liquidity_reversal`
- `es_prior_day_stop_run_reclaim`
- `es_vwap_pullback_continuation`
- `es_cftc_tff_hedging_pressure`

Machine summary command:

```bash
for f in $(find backtest-campaigns -name campaign_test_summary.json | sort); do
  jq -r '[.campaign_id, .variant_id // "campaign", .test_run_id // "",
    (.passed|tostring),
    ([.stages[]? | select(.status=="failed") | .stage] | first // "none"),
    ([.stages[]? | select(.status=="skipped") | .stage] | length | tostring)] | @tsv' "$f"
done
```

Result:

- No active variant-level `campaign_test_summary.json` has `passed=true`.
- ES/MES micro-flow divergence now has five one-time per-variant rescues
  consumed; all five failed at `limited_monkey_test` before WFA.
- Range-compression now has five one-time per-variant rescues consumed. The
  ID/NR4 rescue failed at `limited_monkey_test`; the other four failed
  `limited_core_grid_test` with profitable-combo rates at or below
  `0.4074074074074074`.
- Overnight-intraday reversal now has five one-time per-variant rescues
  consumed. The best rescue remained `high_overnight_first15_short_1000`, which
  failed core at `0.691358024691358` and zero benchmark-passing combinations.
- Prior-session IBS now has five one-time per-variant rescues consumed. The
  best rescue reached only `0.5061728395061729` profitable core combinations
  and zero benchmark-passing combinations.
- Connors RSI2 now has five one-time per-variant rescues consumed. The best
  rescue reached only `0.345679012345679` profitable core combinations and zero
  benchmark-passing combinations.
- RTH intraday risk premium now has five one-time per-variant rescues consumed.
  All five stop/target-only rescues had a `0.0` profitable-combo rate.
- ES signed-orderflow persistence has five one-time per-variant rescues
  consumed. All five original variants and all five rescues failed
  `limited_core_grid_test`; the best rescue reached only
  `0.1111111111111111` profitable core combinations.
- Opening-drive inventory/absorption has five one-time per-variant rescues
  consumed. All five failed before WFA, with the only rescue to reach monkey at
  `percentage_profitable=0.20666666666666667` and failed one-tick stress.
- Turn-of-month seasonality has five one-time per-variant rescues consumed. All
  five originals and all five rescues failed `limited_core_grid_test`; the best
  rescue reached only `0.07407407407407407` profitable core combinations.
- Daily time-series momentum has five one-time per-variant rescues consumed. All
  five originals and all five rescues failed `limited_core_grid_test`; the best
  rescue reached only `0.2839506172839506` profitable core combinations.
- Late-day market intraday momentum has five one-time per-variant rescues
  consumed. All five originals and all five rescues failed
  `limited_core_grid_test`; every original and rescue grid had `0.0`
  profitable core combinations.
- Volume-shock liquidity reversal has five one-time per-variant rescues
  consumed. All five originals and all five rescues failed
  `limited_core_grid_test`; the best rescue reached only
  `0.20987654320987653` profitable core combinations and only 13 trades in
  its top row.
- Prior-day stop-run reclaim has five one-time per-variant rescues consumed.
  All five originals and all five rescues failed before WFA. The strongest
  rescue, `morning_prior_high_reject_short`, passed the core profitable-combo
  gate but failed `limited_monkey_test` with `percentage_profitable=0.32666666666666666`
  and `median_net_profit=-770.0`.
- VWAP pullback continuation has five one-time per-variant rescues consumed. All
  five originals and all five rescues failed before WFA. The strongest rescue,
  `midday_trend_reclaim_two_sided`, passed the core profitable-combo gate but
  failed `limited_monkey_test` with `percentage_profitable=0.18` and
  `median_net_profit=-3210.0`.
- CFTC/TFF hedging pressure has five one-time per-variant rescues consumed.
  Initial `run1` artifacts were invalidated because the limited-core first
  window predated non-null shifted CFTC feature coverage. All five corrected
  `run2` originals and all five rescues failed `limited_core_grid_test`; the
  best rescue reached only `0.3333333333333333` profitable core combinations
  and only `5` trades in its top row.
- The long local Databento OHLCV cache was rechecked. It remains usable.
  Archived tests are ignored for duplicate-edge checks, so archived OHLCV-only
  families do not block a fresh campaign by themselves. Active rejected
  OHLCV/bar families from this run remain range-compression, prior-session IBS,
  Connors RSI2, RTH risk premium, overnight-intraday reversal,
  turn-of-month seasonality, daily time-series momentum, late-day market
  intraday momentum, volume-shock liquidity reversal, prior-day stop-run
  reclaim, and VWAP pullback continuation.
  Active rejected aggregate-orderflow families now include ES/MES micro-flow
  divergence, own-ES signed-orderflow persistence, and opening-drive
  inventory/absorption. The active rejected external-positioning family is
  CFTC/TFF hedging pressure.

## Local Data State

Current ES orderflow-related local files:

- `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.validation.json`
- `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv`
- `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`
- `data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv`

Current ES price/volume local files:

- Long Databento 1-minute OHLCV parquet history under `data/cache/databento`.
- Shifted CFTC/TFF hedging-pressure feature file:
  `data/external/cftc_tff_hedging_pressure_features.csv`.

Missing retained-branch data:

- No long ES+MES `trades` cache from `2020-01-01`.
- No `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`.
- No `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`.

## Retained Next Branches

The retained external-data branches remain data-gated:

1. ES/MES flow-divergence validation using Databento `trades`, `ES.FUT` and
   `MES.FUT`, RTH only, `2020-01-01` through `2026-06-09`.
   Supporting protocol:
   `research_artifacts/es_mes_flow_divergence_validation_protocol_20260614.md`.
   Existing metadata-only sampled estimate:
   `research_artifacts/databento_es_mes_trades_20200101_20260609_cost_manifest_20260614.json`.
   Combined estimate: `$949.3382585047899`.

2. Quote-confirmed ES liquidity-sweep pilot using Databento `tbbo`, `ES.FUT`,
   RTH only, `2025-06-09` through `2026-06-09`.
   Supporting protocol:
   `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md`.
   Existing metadata-only sampled estimate:
   `research_artifacts/databento_es_tbbo_20250609_20260609_cost_manifest_20260614.json`.
   Estimated one-year RTH `tbbo` cost: `$14.87618900835275`.

Both estimates are metadata-only and must be refreshed immediately before any
approved download. No paid data was downloaded in this continuation.

## Conclusion

No active local campaign or rescue has passed the current methodology. The
duplicate-edge check now ignores archived tests, so archived-only families are
not rejected solely because they were tested before. The current research
decision remains `FAIL`; the active goal is not complete because no ES candidate
strategy has passed. Further work may continue through a genuinely new local
edge that is not one of the active rejected families, or through an approved
external-data branch.

## Current Fail-Closed Confirmation

The earlier campaign-level blocker was superseded by the user clarification
that each failed variant can be rescued once. After applying that rule to every
active failed variant, no local variant-level report passes, and every active
failed variant has consumed its single allowed rescue. This is a fail-closed
campaign state, not a claim that only paid data can move the goal forward.

Continuation recheck:

- Active ES variant-level summary count: `158` raw
  `campaign_test_summary.json` files, representing 75 latest original reports
  and 75 `rescue1` reports for 75 active source variants.
- Active variant-level passes: `0`.
- Active variants missing a `rescue1` report: `0`.
- `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`:
  absent.
- `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`: absent.

The retained ES/MES and TBBO branches remain data-gated, but the active-only
duplicate policy also permits fresh local campaigns when the proposed edge is
not already active and rejected.

## Goal Continuation Blocked Audit

Continuation recheck on 2026-06-15:

- Active ES variant-level summaries inspected:
  `158` raw files under `backtest-campaigns/*/*/ES/*/campaign_test_summary.json`,
  representing 75 latest original reports and 75 `rescue1` reports for 75
  active source variants.
- Active ES variant-level passes: `0`.
- Active variants missing a `rescue1` report: `0`.
- Local ES Databento `trades` files are present for `2025-06-09` through
  `2026-06-09`.
- Local MES Databento `trades` files are present for `2025-06-10` through
  `2026-06-09`.
- Missing retained ES/MES branch input:
  `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`.
- Missing retained quote branch input:
  `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`.
- The long local OHLCV cache remains usable. Archived OHLCV-only tests are
  ignored by the duplicate-edge gate; active rejected OHLCV/bar families from
  this run remain blocked unless the core edge changes. The local Sierra
  aggregate-orderflow lane remains usable for genuinely new non-duplicate
  orderflow edges, but not for relaunching ES/MES divergence or own-ES
  signed-orderflow persistence, opening-drive inventory/absorption,
  turn-of-month seasonality, daily time-series momentum, late-day market
  intraday momentum, volume-shock liquidity reversal, prior-day stop-run
  reclaim, VWAP pullback continuation, or CFTC/TFF hedging pressure under a new
  active name.

Conclusion: FAIL, not blocked. No active strategy passes. Meaningful progress
requires either a fresh local edge outside the active rejected families, or an
approved and available longer ES/MES `trades` cache or ES `tbbo` liquidity
cache for the retained external-data branches.

## 2026-06-16 Continuation Update

Tested new active-only, non-duplicate local campaign `es_market_plumbing_liquidity_capacity` after archived tests were excluded from duplicate checks. The campaign used a no-lookahead lagged market-plumbing feature file and exactly five variants. All five valid originals failed before WFA; all five failed variants received exactly one rescue and all rescues failed. No candidate strategy emerged.

Current active sweep: 80 active source variants, 80 latest original reports, 80 `rescue1` reports, 173 raw variant-level reports, 0 passes, 0 missing rescues.

## 2026-06-16 Bankruptcy-Distress Continuation Update

Tested active-only, non-duplicate campaign `es_bankruptcy_distress_regime_reversion`. All five corrected originals failed core; each failed variant received exactly one rescue and all five rescues failed core. No candidate strategy emerged.


## 2026-06-16 Prior-Session Level Breakout Continuation Update

`es_prior_session_level_breakout_continuation` is now an active failed campaign. The active-only duplicate gate ignored archived tests, but this edge is now blocked from relaunch under a new active name. Originals and per-failed-variant rescues completed; zero variants passed and no run reached WFA/Monte Carlo/frozen validation.


## 2026-06-16 VPIN Toxicity Continuation Update

`es_vpin_toxicity_continuation` is now an active failed campaign. The active-only duplicate gate ignored archived tests, but this VPIN/toxicity proxy edge is now blocked from relaunch under a new active name. Originals and per-failed-variant rescues completed; zero variants passed and no run reached WFA/Monte Carlo/frozen validation.


## 2026-06-16 Overnight Return Late-Day Momentum Update

`es_overnight_return_late_day_momentum` is now an active failed campaign. The active-only duplicate gate ignored archived tests, but this overnight-return late-day continuation edge is now blocked from relaunch under a new active name. Originals and per-failed-variant rescues completed; zero variants passed and no run reached monkey/WFA/Monte Carlo/frozen validation.


## 2026-06-16 Prior-Level Delta Dislocation Continuation

Added `es_prior_level_delta_dislocation` as an active-scope non-duplicate campaign. Archived tests were ignored for duplicate checks. Exactly five original variants and exactly five one-time rescues were run. All failed `limited_core_grid_test`; best rescue was `pdl_sell_absorption_long/rescue1` at `0.5555555555555556` profitable combinations and only `15` top-combo trades. No candidate strategy report was created.


## 2026-06-16 Orderflow Absorption Exhaustion Reversal Continuation

Added `es_orderflow_absorption_exhaustion_reversal` as an active-scope non-duplicate campaign. Exactly five originals and exactly five one-time rescues were run. No run reached WFA, Monte Carlo, simulated incubation, or frozen validation.

Current verified active sweep: 110 active source variants, 110 rescue configs, 238 raw variant-level reports, 0 passes, and 0 active variants missing `rescue1`. Final preflight for the active config set passed with 348 configs checked. Decision remains FAIL; archived tests remain excluded from duplicate-edge checks, while active failed campaign families still block relaunching the same edge under a new name.

## 2026-06-16 Active-Only Duplicate Exhaustion Check

Reviewed the remaining local entry modules after excluding archived tests from
duplicate checks. `calendar_session_bias` is already represented by the active
`es_rth_intraday_risk_premium` campaign. The remaining local-only gap,
overnight, intraday mean-reversion, opening-range, signed-flow, orderflow-state,
and orderflow-combo modules map to active rejected campaign families. The
quote-confirmed liquidity-sweep branch still requires the missing ES `tbbo`
cache, and the retained ES/MES flow-divergence branch still requires longer
ES+MES `trades` history. No paid data was pulled.

Conclusion: FAIL. There is no active ES candidate strategy and no defensible
new local non-duplicate campaign to launch without changing the economic edge
rules or acquiring approved external data.

## 2026-06-16 Day-of-Week Seasonality Continuation

Reopened the active-only duplicate gate for weekday-specific seasonality. The
edge was treated as distinct from unconditional all-weekday RTH long exposure
and monthly turn-of-month timing, then tested as `es_day_of_week_seasonality`
with exactly five variants and one rescue per failed variant.

Outcome: FAIL. All five originals and all five stop/target parameter-space
rescues failed `limited_core_grid_test` with `0.0` profitable-combo rate. No
run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen
validation. Active sweep after aggregation found 115 source variants, 115
rescue configs, 248 raw variant-level reports, 0 passes, and 0 active variants
missing `rescue1`.

Final preflight after this campaign passed with 363 configs checked.


## 2026-06-16 Overnight Inventory Sweep Reversion Continuation

Added `es_overnight_inventory_sweep_reversion` as an active-scope non-duplicate campaign after excluding archived tests from the duplicate gate. To avoid roll-selection lookahead, the campaign used a newly built explicit-roll ETH/RTH Databento OHLCV cache instead of the earlier same-day-volume front cache. Exactly five originals and exactly five one-time rescues were run.

Outcome: FAIL. `midpoint_low_sweep_reclaim_long/run1` passed core but failed monkey (`percentage_profitable=0.26`, `median_net_profit=-601.25`). The other originals and all rescues failed core. Current verified active sweep: 24 campaigns, 120 source variants, 120 rescue configs, 258 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. Final preflight passed with 378 configs checked.

## 2026-06-16 Post-Overnight Active-Only Duplicate Recheck

Rechecked the remaining unused local entry modules after the overnight inventory
campaign. Archived tests remain ignored for duplicate checks. The active scope
still blocks relaunching the same economic edges under new names.

Key duplicate decisions:

- `intraday_capitulation_mr` was rejected as a new campaign because it is a
  high-volume down-shock mean-reversion setup filtered by RSI and running VWAP,
  overlapping active `es_volume_shock_liquidity_reversal`,
  `es_connors_rsi2_mean_reversion`, and VWAP-context mean-reversion evidence.
- Pure opening-range breakout/fade modules were rejected as a new campaign
  because active `es_range_compression_breakout` already used opening-range
  breakout variants under the Crabel/NR7 compression thesis. Dropping the
  compression condition after active failures would be a post-result mechanic
  relaxation rather than a clean independent edge.
- Remaining local orderflow, intraday momentum, CFTC/TFF, market-plumbing, and
  gap modules map to active rejected families.

External-data gate status: only the one-year ES/MES divergence caches are
present locally; the longer ES+MES `trades` branch and the ES `tbbo`
quote-liquidity branch remain missing and were not pulled.

Current verified active sweep: 24 campaigns, 120 source variants, 120 one-time
rescues, 258 raw variant-level reports, 0 passes, and no active variants missing
`rescue1`.

Conclusion: FAIL for the local active campaign set. No candidate strategy report
exists. Continuing without a duplicate-rule violation requires approved external
data for a retained branch or an explicit user rule change.

## 2026-06-16 ES/NQ Cross-Index Lead-Lag Campaign

Added `es_nq_cross_index_lead_lag` after the user asked about cross-asset
lead-lag Edge 5. This was eligible under the active-only duplicate rule because
local full-RTH ES and NQ Sierra caches existed and no active ES/NQ lead-lag
campaign existed outside `_archived`. The campaign is distinct from failed
ES/MES micro-flow divergence because it tests cross-index NQ information
leadership into ES, not same-underlying micro/mini flow reversion.

Outcome: FAIL. All five original variants failed `limited_core_grid_test` with
`0.0` profitable-combo rate. All five one-time parameter-space rescues were run
and also failed `limited_core_grid_test`; best rescue profitable-combo rate was
`0.07407407407407407`, still far below the `0.70` gate, with zero
benchmark-pass combinations. No run reached monkey, WFA, Monte Carlo, simulated
incubation, or frozen validation.

Current verified active sweep: 25 campaigns, 125 source variants, 125 rescue
configs, 268 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`. Final preflight passed with 393 configs
checked.

## 2026-06-16 FOMC Pre-Announcement Drift Campaign

Added `es_fomc_pre_announcement_drift` as a local active-only non-duplicate
campaign after excluding archived tests from duplicate checks. The edge used
official scheduled FOMC decision dates plus local ES Sierra RTH data. Decision
day variants flattened before noon ET to avoid historical statement-time
ambiguity; no FOMC decision text, surprises, minutes, or post-announcement bars
were used.

Outcome: FAIL. All five original variants failed before WFA. Each failed
variant received exactly one parameter-space/fixed-parameter rescue. Only
`decision_day_open_long_1000/rescue1` passed the core profitable-combo gate, but
it failed `limited_monkey_test` with `percentage_profitable=0.33666666666666667`,
`median_net_profit=-298.75`, trade-path stress profitability
`0.6166666666666667`, and one-tick-worse net profit `-80.0`. The other rescues
failed `limited_core_grid_test`.

This FOMC pre-announcement event edge is now an active failed family and should
not be relaunched under a new active campaign name without a materially
different thesis approved before testing.

Current verified active sweep: 26 campaigns, 130 source variants, 130 rescue
configs, 278 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 Volatility-Managed Intraday Premium Campaign

Added `es_volatility_managed_intraday_premium` as a local active-only
non-duplicate campaign. The edge uses lagged realized-volatility state to
condition intraday ES long exposure and is distinct from the failed
unconditional RTH intraday risk premium because every signal requires a
prior-session volatility/range/semivolatility state.

Outcome: FAIL. All five originals failed before WFA. Each failed variant
received exactly one rescue. `low_10d_range_midmorning_long_1030/rescue1`
passed the core profitable-combo gate at `0.7222222222222222`, but failed
`limited_monkey_test` with `percentage_profitable=0.24` and
`median_net_profit=-2081.25`. No run reached WFA, Monte Carlo, simulated
incubation, or frozen validation.

This volatility-managed intraday premium edge is now an active failed family and
should not be relaunched under a new active campaign name without a materially
different thesis approved before testing.

Current verified active sweep: 27 campaigns, 135 source variants, 135 rescue
configs, 288 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 Halloween Seasonal Premium Campaign

Added `es_halloween_seasonal_premium` as a local active-only non-duplicate
campaign. The edge tests the half-year Halloween / Sell-in-May seasonal anomaly
and is distinct from active day-of-week, turn-of-month, FOMC event,
volatility-state, and unconditional RTH premium campaigns.

Outcome: FAIL. All five originals and all five one-time stop/target rescues
failed `limited_core_grid_test`. Best rescue was `winter_midday_long_1200/rescue1`
with profitable-combo rate `0.5`, zero benchmark-passing combinations, top net
`1000.0`, PF `1.0526870389884089`, MAR `0.22386592295394953`, and best-day
concentration `0.77`.

This half-year seasonal edge is now an active failed family and should not be
relaunched under a new active campaign name without a materially different
thesis approved before testing.

Current verified active sweep: 28 campaigns, 140 source variants, 140 rescue
configs, 298 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 Quarterly Expiration Pressure Campaign

Added `es_quarterly_expiration_pressure` as a local active-only non-duplicate
campaign. The edge tests deterministic quarterly index futures/options
expiration and CME equity-index roll-date pressure using only ES Sierra RTH bars
and pre-known calendar rules.

Outcome: FAIL. All five originals failed before WFA. Each failed variant
received exactly one stop/target parameter-space rescue. Four rescues failed
`limited_core_grid_test`; `monday_after_expiration_reversal_long_1000/rescue1`
passed core with `1.0` profitable combinations but failed `limited_monkey_test`
with `percentage_profitable=0.47` and `median_net_profit=-30.0`. No run reached
WFA, Monte Carlo, simulated incubation, or frozen validation.

This quarterly expiration pressure edge is now an active failed family and
should not be relaunched under a new active campaign name without a materially
different thesis approved before testing.

Current verified active sweep: 29 campaigns, 145 source variants, 145 rescue
configs, 308 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 Pre-Holiday Effect Campaign

Added `es_preholiday_effect` as a local active-only non-duplicate campaign. The
edge tests the documented pre-holiday premium in equity/futures markets using
deterministic NYSE full-holiday dates and local ES Sierra RTH data. Early-close
sessions were excluded to match the validated local RTH cache.

Outcome: FAIL. All five originals failed `limited_core_grid_test`. Each failed
variant received exactly one parameter-space/fixed-parameter rescue, and all
five rescues also failed `limited_core_grid_test`. Best rescue was
`preholiday_momentum_confirmed_midday_long_1200/rescue1` with `0.5`
profitable-combo rate, zero benchmark-passing combinations, top net `232.5`,
and only `6` top-combo trades. No run reached monkey, WFA, Monte Carlo,
simulated incubation, or frozen validation.

This pre-holiday effect edge is now an active failed family and should not be
relaunched under a new active campaign name without a materially different
thesis approved before testing.

Current verified active sweep: 30 campaigns, 150 source variants, 150 rescue
configs, 318 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 Turn-of-Year Effect Campaign

Added `es_turn_of_year_effect` as a local active-only non-duplicate campaign.
The edge tests the documented January/turn-of-year/Santa-rally anomaly using
deterministic NYSE regular-session calendar dates and local ES Sierra RTH data.
Early-close sessions were excluded to match the validated local RTH cache.

Outcome: FAIL. All five originals failed `limited_core_grid_test`. Each failed
variant received exactly one parameter-space/fixed-parameter rescue, and all
five rescues also failed `limited_core_grid_test`. Best rescue was
`january_first2_open_long_1000/rescue1` with `0.4166666666666667`
profitable-combo rate, zero benchmark-passing combinations, top net `222.5`,
and only `3` top-combo trades. No run reached monkey, WFA, Monte Carlo,
simulated incubation, or frozen validation.

This turn-of-year effect edge is now an active failed family and should not be
relaunched under a new active campaign name without a materially different
thesis approved before testing.

Current verified active sweep: 31 campaigns, 155 source variants, 155 rescue
configs, 328 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 BLS Macro Release-Day Drift Campaign

Added `es_bls_macro_release_day_drift` as a local active-only non-duplicate
campaign. The edge tests whether known 08:30 ET CPI and Employment Situation
release dates carry a positive ES RTH drift after macro uncertainty resolution.
It uses only local ES Sierra RTH data and ALFRED/FRED BLS release dates; release
values, revisions, and survey surprises are not used.

Outcome: FAIL. All five originals failed `limited_core_grid_test`. Each failed
variant received exactly one parameter-space/fixed-parameter rescue, and all
five rescues also failed `limited_core_grid_test`. Best rescue was
`employment_release_open_long_1000/rescue1` with `0.5833333333333334`
profitable-combo rate, zero benchmark-passing combinations, top net `465.0`,
PF `1.382716049382716`, and only `17` top-combo trades. No run reached monkey,
WFA, Monte Carlo, simulated incubation, or frozen validation.

This BLS macro-release calendar edge is now an active failed family and should
not be relaunched under a new active campaign name without a materially
different thesis approved before testing.

Current verified active sweep: 32 campaigns, 160 source variants, 160 rescue
configs, 338 raw variant-level reports, 0 passes, and no active variants
missing a latest original or `rescue1`.

## 2026-06-16 Term-Structure Lead-Lag Feedback Campaign

Added `es_term_structure_lead_lag_feedback` as a local active-only
non-duplicate campaign. The edge tests whether completed front-vs-next-contract
ES dislocations near roll produce short-term spread-feedback reversion in the
front contract. It uses only local ES Sierra data and the explicit ES roll
calendar; no paid data was pulled.

Outcome: FAIL. All five originals failed `limited_core_grid_test`. Each failed
variant received exactly one parameter-space rescue, and all five rescues also
failed `limited_core_grid_test`. Best original was
`late_morning_two_sided_spread_feedback_1130/run1` with `0.48148148148148145`
profitable-combo rate, zero benchmark-passing combinations, top net `342.5`,
PF `69.5`, and only `4` top-combo trades. Best rescue was
`late_day_two_sided_spread_feedback_1530/rescue1` with
`0.2222222222222222` profitable-combo rate, zero benchmark-passing
combinations, top net `100.0`, and only `5` top-combo trades. No run reached
monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

This term-structure lead-lag edge is now an active failed family and should not
be relaunched under a new active campaign name without a materially different
thesis approved before testing.

Current verified active sweep: 33 campaigns, 165 source variants, 165 rescue
configs, 348 raw variant-level reports, 0 passes, and no active variants
missing any original run or `rescue1`.

## 2026-06-16 Monthly OPEX Pressure Campaign

Added `es_monthly_opex_pressure` as a local active-only non-duplicate campaign.
The edge tests whether non-quarterly standard monthly listed-option expiration
sessions create intraday ES pressure or reversal effects through hedging,
pinning, and post-expiration inventory unwind. It uses only local ES Sierra RTH
bars and a deterministic NYSE third-Friday OPEX calendar; March, June,
September, and December are excluded to avoid duplicating the active failed
quarterly expiration/roll campaign.

Outcome: FAIL. All five originals failed `limited_core_grid_test`. Each failed
variant received exactly one stop/target parameter-space rescue, and all five
rescues also failed `limited_core_grid_test`. Best original was
`nonquarterly_opex_thursday_positioning_short_1330/run1` with
`0.5555555555555556` profitable-combo rate, zero benchmark-passing
combinations, top net `740.0`, PF `2.0033898305084747`, and only `12`
top-combo trades. Best rescue was
`nonquarterly_opex_thursday_positioning_short_1330/rescue1` with
`0.5833333333333334` profitable-combo rate, zero benchmark-passing
combinations, top net `830.625`, PF `2.1536458333333335`, and only `12`
top-combo trades. No run reached monkey, WFA, Monte Carlo, simulated
incubation, or frozen validation.

This monthly OPEX edge is now an active failed family and should not be
relaunched under a new active campaign name without a materially different
thesis approved before testing.

Current verified active sweep: 34 campaigns, 170 source variants, 170 rescue
configs, 358 raw variant-level reports, 0 passes, and no active variants
missing any original run or `rescue1`.

## 2026-06-16 VIX Expiration Pressure Campaign

Added `es_vix_expiration_pressure` as a local active-only non-duplicate
campaign. The edge tests whether VIX futures/options settlement creates
transitory SPX option demand, volatility-hedging pressure, or post-settlement
unwind that spills into ES. It uses only local ES Sierra RTH bars and a
deterministic VIX standard expiration calendar.

Outcome: FAIL. All five originals failed `limited_core_grid_test`. Each failed
variant received exactly one stop/target parameter-space rescue, and all five
rescues also failed `limited_core_grid_test`. Best original was
`vix_settlement_open_pressure_short_1000/run1` with `0.6666666666666666`
profitable-combo rate, zero benchmark-passing combinations, top net `1040.0`,
PF `1.4952380952380953`, and only `17` top-combo trades. Best rescue was
`vix_settlement_open_pressure_short_1000/rescue1` with `0.5833333333333334`
profitable-combo rate, zero benchmark-passing combinations, top net `2208.75`,
PF `2.2004076086956523`, and only `17` top-combo trades. No run reached
monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

This VIX derivatives settlement edge is now an active failed family and should
not be relaunched under a new active campaign name without a materially
different thesis approved before testing.

Current verified active sweep: 35 campaigns, 175 source variants, 175 rescue
configs, 368 raw variant-level reports, 0 passes, and no active variants
missing any original run or `rescue1`.

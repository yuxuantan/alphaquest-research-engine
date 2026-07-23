# ES AOI Orderflow Local Data Gate - 2026-06-22

Status: NEEDS MANUAL REVIEW / data approval required.

## Scope

This audit continues the active ES search for strategies combining market-generated
areas of interest, volume-profile context, large-trade/orderflow confirmation, and
absorption/trapped-trader evidence.

The current local workspace was checked after these newly authored campaigns failed:

- `es_profile_aoi_footprint_trap_confluence`
- `es_video_aoi_lvn_orderflow_playbook`
- `es_large200_record_aoi_profile_reaction`
- `es_true_vap_aoi_breakout_continuation`
- `es_true_vap_market_aoi_footprint_trap_reversion`

All five campaigns failed `limited_core_grid_test` before monkey, WFA, Monte
Carlo, simulated incubation, or acceptance OOS.

## Current Local Evidence

- `backtest-campaigns/**/variant_test_summary.json` currently has zero ES runs with
  `passed=true`.
- The local long-history ES orderflow caches are completed-bar Sierra-derived caches:
  - `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
  - `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`
  - `data/cache/orderflow/es_sierra_footprint_large200_record_proxy_1m_20120103_20260609_rth_ny.parquet`
  - `data/cache/orderflow/es_sierra_footprint_vap_profile_1m_20101214_20260610_full_rth_ny.parquet`
- These caches support completed-bar OHLCV, aggregate signed-volume, aggregate
  `large10`/`large20` proxy fields, and completed-bar footprint imbalance/absorption
  research after validation.
- The new true VAP profile cache supports previous-session POC, VAH, VAL, and
  nearest high/low LVNs from Sierra SCID volume-at-price aggregation. It is a
  real volume-at-price profile, not an OHLCV uniform profile approximation.
- The new `large200_record_*` cache supports only a strict Sierra SCID record-volume
  proxy filtered to `volume >= 200`, `num_trades == 1`, and exact side-volume coverage.
  It is not vendor-equivalent print data.
- These local caches do not support vendor-equivalent `>200 lot` ES large-print
  detection, print sequencing, trade fragmentation, tick replay, or queue/depth inference.
- A direct raw-file audit on 2026-06-22 found no local ES `*.trades.dbn*` or
  `*tbbo*.dbn*` files under `data/raw/ES`.
- The local Databento ES `trades` download for `2020-01-01` through `2026-06-09`
  was explicitly stopped and has no completed manifest. It must not be used as a
  complete or validated campaign input.
- Local Databento ES OHLCV files are not enough for the requested large-trade or
  quote-liquidity branch.

## Duplicate / Exhaustion Check

The active source tree already contains failed AOI/orderflow families covering:

- prior value-area acceptance/rejection
- prior LVN rejection
- prior POC magnet behavior
- opening-range orderflow breakout/retest/failed breakout
- opening-drive and footprint absorption initiation
- session-extreme delta divergence
- prior-level delta dislocation
- rolling liquidity sweep reversion with footprint/MES crowding
- round-number orderflow barriers
- VWAP/orderflow pullbacks and deviations
- local Sierra profile/AOI footprint trap confluence
- video-derived value-edge and LVN orderflow playbook
- strict Sierra large200-record AOI/profile reaction proxy
- true Sierra previous-session VAP AOI breakout continuation
- true Sierra previous-session VAP market-AOI footprint trap reversion

`research_artifacts/local_no_duplicate_edge_inventory_gate_20260620.md` already
classified the remaining unused local modules as duplicate, stale wrappers, or
data-gated. The true VAP profile cache reopened one no-cost local lane, but the
new 2026-06-22 true VAP campaign rejected that lane at the first staged gate.

## Post-Proxy Campaign Result

`es_large200_record_aoi_profile_reaction` tested the only locally defensible
large-record proxy path after a separate source-quality audit. Its five predeclared
variants were:

- `market_aoi_large200_two_sided_trap_1500`
- `market_aoi_large200_two_sided_continuation_1500`
- `profile_value_large200_two_sided_trap_1500`
- `profile_value_large200_two_sided_continuation_1500`
- `combined_aoi_profile_large200_reaction_1500`

Result:

- Terminal stage: `limited_core_grid_test`
- Variants tested: 5
- Variants passed: 0
- Profitable combinations: `0/27` for every variant
- Benchmark-passing combinations: `0` for every variant
- Apex rule-violating iterations: `0`
- Campaign summary: `backtest-campaigns/es_large200_record_aoi_profile_reaction/campaign_test_summary.json`

This rejects the Sierra proxy expression of the requested large-trade AOI/profile
mechanic. It does not reject true vendor-equivalent `>200 lot` ES prints, because
that data source is still absent locally.

## Post-True-VAP Campaign Result

`es_true_vap_aoi_breakout_continuation` tested the newly available true Sierra
volume-at-price profile lane after building
`data/cache/orderflow/es_sierra_footprint_vap_profile_1m_20101214_20260610_full_rth_ny.parquet`.
Its five predeclared variants were:

- `prior_high_true_vap_breakout_long_1200`
- `prior_low_true_vap_breakdown_short_1200`
- `prior_extreme_large10_true_vap_two_sided_1500`
- `opening_range_true_vap_two_sided_1130`
- `combined_large20_true_vap_two_sided_1500`

Result:

- Terminal stage: `limited_core_grid_test`
- Variants tested: 5
- Variants passed: 0
- Profitable combinations: `0/81` for every variant
- Benchmark-passing combinations: `0` for every variant
- Apex rule-violating iterations: `0`
- Campaign summary: `backtest-campaigns/es_true_vap_aoi_breakout_continuation/campaign_test_summary.json`

This rejects the local true VAP AOI breakout-continuation expression. It does
not reject true vendor-equivalent large-print sequencing, trade fragmentation
analysis, TBBO quote-liquidity sweeps, or depth-confirmed absorption, because
those data sources remain absent locally.

## Post-True-VAP Trap/Reversion Campaign Result

`es_true_vap_market_aoi_footprint_trap_reversion` tested the remaining local
true Sierra VAP trap/reversion lane after adding a combined market-AOI setup
mode before any PnL test. Its five predeclared variants were:

- `prior_vap_extreme_trap_two_sided_1500`
- `opening_vap_aoi_trap_two_sided_1500`
- `market_vap_aoi_trap_two_sided_1500`
- `market_vap_aoi_delta_trap_two_sided_1500`
- `market_vap_aoi_morning_trap_two_sided_1200`

Result:

- Terminal stage: `limited_core_grid_test`
- Variants tested: 5
- Variants passed: 0
- Profitable combinations: `0/81` for every variant
- Benchmark-passing combinations: `0` for every variant
- Apex rule-violating iterations: `0`
- Campaign summary: `backtest-campaigns/es_true_vap_market_aoi_footprint_trap_reversion/campaign_test_summary.json`

This rejects the local true VAP AOI footprint-trap/reversion expression. It does
not reject true vendor-equivalent large-print sequencing, trade fragmentation
analysis, TBBO quote-liquidity sweeps, or depth-confirmed absorption.

## Post-Overnight-VAP Trap/Reversion Campaign Result

`es_overnight_vap_footprint_trap_reversion` tested the remaining local branch
that combines completed overnight high/low AOIs with frozen prior true VAP
levels and completed-bar Sierra footprint absorption. Its five predeclared
variants were:

- `overnight_vap_immediate_open_trap_two_sided_1500`
- `overnight_vap_two_sided_trap_1530`
- `overnight_vap_confirmed_reclaim_two_sided_1530`
- `overnight_vap_deep_probe_two_sided_1530`
- `overnight_vap_morning_trap_two_sided_1200`

Result:

- Terminal stage: `limited_core_grid_test`
- Variants tested: 5
- Variants passed: 0
- Profitable combinations: `0/81` for four variants; `3/81` for the morning-only variant
- Benchmark-passing combinations: `0` for every variant
- Apex rule-violating iterations: `0`
- Campaign summary: `backtest-campaigns/es_overnight_vap_footprint_trap_reversion/campaign_test_summary.json`

This rejects the local completed-overnight-level plus prior true VAP
footprint-trap/reversion expression. It does not reject vendor-equivalent
large-print sequencing, trade fragmentation analysis, TBBO quote-liquidity
sweeps, or depth-confirmed absorption.

## Post-Overnight-VAP Breakout/Continuation Campaign Result

`es_overnight_vap_orderflow_breakout_continuation` tested the remaining local
continuation side of the completed overnight high/low plus prior true VAP
confluence idea. Its five predeclared variants were:

- `overnight_vap_immediate_breakout_two_sided_1500`
- `overnight_vap_two_sided_breakout_1530`
- `overnight_vap_morning_breakout_two_sided_1200`
- `overnight_large10_vap_breakout_two_sided_1530`
- `overnight_large20_vap_breakout_two_sided_1530`

Result:

- Terminal stage: `limited_core_grid_test`
- Variants tested: 5
- Variants passed: 0
- Benchmark-passing combinations: `0` for every variant
- Apex rule-violating iterations: `0`
- Campaign summary: `backtest-campaigns/es_overnight_vap_orderflow_breakout_continuation/campaign_test_summary.json`

This rejects the local completed-overnight-level plus prior true VAP
orderflow-breakout/continuation expression. It does not reject vendor-equivalent
large-print sequencing, trade fragmentation analysis, TBBO quote-liquidity
sweeps, or depth-confirmed absorption.

## Required Next Data Lanes

The next non-duplicate research path requires one of:

1. Complete and validate Databento ES `trades` for a campaign-shaped date range,
   then build true large-print features such as `large200_volume`,
   `large200_signed_volume`, and event-count fields.
2. Run the bounded ES TBBO/quote-liquidity pilot previously costed for a one-year
   RTH sample, then test quote-liquidity sweeps at PDH/PDL/ORH/ORL/profile levels.

Existing cost artifacts:

- `research_artifacts/databento_es_trades_20200101_20260609_cost_refresh_20260616.json`
  estimated the full ES `trades` RTH pull at about `$554.49`.
- `research_artifacts/databento_es_tbbo_20250609_20260609_cost_manifest_20260614.json`
  estimated a one-year ES RTH `tbbo` pilot at about `$14.88`.
- `research_artifacts/databento_es_tbbo_20250609_20260609_dry_run_manifest_20260622.json`
  is a no-download dry-run sample estimate for 262 RTH `tbbo` sessions. It
  estimated `$5.95` from 20 sampled sessions and did not create local DBN files.
- `research_artifacts/databento_es_trades_20200101_20260609_dry_run_manifest_20260622.json`
  is a no-download dry-run sample estimate for 1,680 RTH `trades` sessions. It
  estimated `$616.56` from 20 sampled sessions and did not create local DBN files.

## Decision

NEEDS MANUAL REVIEW.

Do not launch another local Sierra-only AOI/orderflow campaign unless a genuinely
new source-supported mechanism is identified outside the rejected profile/AOI
families above. The requested true `>200 lot` large-trade and quote/depth-liquidity
branches require explicit data approval before they can be tested under the full
staged methodology.

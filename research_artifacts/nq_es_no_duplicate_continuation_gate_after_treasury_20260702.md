# NQ/ES No-Duplicate Continuation Gate After Treasury Auction Campaign - 2026-07-02

Status: NEEDS MANUAL REVIEW.

Scope: after closing `nq_treasury_auction_pressure`, refresh the local NQ/ES
candidate inventory and the live Chart Fanatics strategy index to decide whether
another non-duplicate ES/NQ campaign can be launched under the current rules.

Current campaign closure:

- `nq_treasury_auction_pressure`: FAIL.
- Four of five variants failed `limited_core_grid_test`.
- `note_only_post_auction_short_1305` passed limited core and limited monkey,
  then failed `walk_forward_analysis` with early exit, stitched OOS profit
  factor `0.9392951721328173`, MAR `-0.14930931550666002`, net profit
  `-1490.0`, and trades/year `68.58247313416537`.
- No branch reached WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation,
  acceptance OOS, or candidate reporting.

Inputs checked:

- `research_ledger.csv` through `2026-07-02T00:45:07+08:00`.
- `campaigns/`: 181 `nq_*` campaign directories and 164 `es_*` campaign
  directories.
- `backtest-campaigns/`: 181 `nq_*` staged-result roots.
- `src/propstack/strategy_modules/entry/` NQ/ES entry-module inventory.
- Live Chart Fanatics strategy index at `https://www.chartfanatics.com/strategies`.
- Prior source gate:
  `research_artifacts/chartfanatics_remaining_strategy_source_gate_20260702_after_labor.md`.

Findings:

- Every `campaigns/nq_*` directory has at least one `research_ledger.csv`
  campaign row. No NQ campaign folder is currently unledgered.
- Older aggregate rows using `ALL`, blank `variant_id`, `campaign_review`, or
  `campaign_completed` are closed evidence rows, not untested campaigns.
- The apparent unused NQ tech module
  `nq_tech_relative_orderflow_confirmation` is a duplicate of the closed
  `nq_tech_relative_strength_intraday` and
  `nq_tech_nonleadership_orderflow_confirmation` families.
- ES-to-NQ transfer inventory found no non-profile/AOI ES family without an NQ
  counterpart or an explicit NQ closure.
- The unmatched ES VAP/AOI/footprint cluster is already represented by
  `es_nq_confirming_vap_aoi_breakout`,
  `es_nq_nonconfirming_vap_aoi_trap`,
  `es_video_aoi_lvn_orderflow_playbook`, prior-value-area, POC, LVN, AOI,
  absorption, and orderflow campaigns.
- `es_nq_confirming_vap_aoi_breakout` and
  `es_nq_nonconfirming_vap_aoi_trap` have staged ES evidence and ledger `FAIL`
  rows. Relaunching the same modules as NQ work would be a renamed AOI/VAP edge,
  not a fresh campaign.
- True NQ footprint/AOI absorption remains data-gated: prior artifact
  `research_artifacts/nq_footprint_absorption_initiation_data_gate_20260630.md`
  records that local caches contain ES footprint imbalance/VAP fields only and
  no NQ footprint imbalance cache under `data/cache/orderflow/`.
- The refreshed Chart Fanatics index did not introduce a new locally testable
  non-duplicate ES/NQ edge after the labor and Treasury auction campaigns.
  Remaining pages are already tested, duplicate of profile/AOI/orderflow/FVG/
  SMT/ORB/prior-level families, out of ES/NQ futures scope, framework-only, or
  require unavailable ETH/session/depth/tape/intraday-VIX data.

Conclusion:

No additional non-duplicate ES/NQ campaign can be launched from the current
local tree and Chart Fanatics source set without one of the following:

- a new external source that defines a distinct ES/NQ futures edge,
- new data that resolves an existing data gate such as NQ footprint/depth/tape
  or reliable intraday VIX,
- explicit permission to run a duplicate-adjacent sibling expression, or
- explicit permission for a post-result rescue of a failed campaign.

Fail-closed decision: NEEDS MANUAL REVIEW. No new campaign was launched from
this continuation gate.

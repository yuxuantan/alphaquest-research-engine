# Unified Live Trading Tracker

Updated: `2026-06-15`

This file is the single live-trading tracker for campaign-tested strategies. Do not keep live-trading tracker files inside individual campaign/variant report folders.

## Current Live Roster

No strategy is currently live-eligible under the active campaign test stack.

The active stack now ends with `acceptance_oos_test`: latest 6 months out-of-sample, trained on the 24 months immediately before that, with parameter selection by MAR. A strategy must pass that terminal gate and the 2026-06-14 screenshot benchmark before it can be listed as live-eligible here.

2026-06-14 shortlist benchmark refresh: `_archived/research_artifacts/campaign_benchmark_shortlist_refresh_20260614.{json,csv}` audited 194 report roots, archived 191 not-likely report roots under `data/reports/campaigns/archive_not_likely_20260614`, reran 3 likely shortlist candidates, and produced 2 shortlist-only passes. Acceptance OOS was intentionally excluded, so the live roster remains empty.

2026-06-15 acceptance OOS: `_archived/research_artifacts/acceptance_oos_shortlist_passes_20260615.{json,csv}` ran the terminal gate for the two shortlist-only passes. Both failed PF and MAR, so the live roster remains empty.

Acceptance OOS failures:

- `nq_intraday_momentum_priority` / `short_first_1030_weakness_1130_strength_long50`: PF `0.836`, MAR `-1.012`, trades `56`.
- `morning_orderflow_momentum` / `two_sided_signed_flow_1515_flatten_continuation`: PF `0.863`, MAR `-1.109`, trades `53`.

| Status | Campaign | Variant | Symbol | Timeframe | Report |
|---|---|---|---|---|---|
| none | n/a | n/a | n/a | n/a | n/a |

## Promotion Rule

Add a strategy to `Current Live Roster` only when its `campaign_tests/campaign_test_summary.json` has `passed: true` after `acceptance_oos_test` is included.

Each live row should link to:

- `campaign_tests/campaign_test_summary.json`
- `campaign_tests/acceptance_oos_test/stage_result.json`
- `campaign_tests/acceptance_oos_test/equity_curve.html`
- the selected parameter artifact used for live config

## Live Review Log

No active live strategy is being tracked.

| Review Date | Strategy | Window | Closed Trades | Net PnL | PF | Exp R | Win Rate | Max DD | Status | Action |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|

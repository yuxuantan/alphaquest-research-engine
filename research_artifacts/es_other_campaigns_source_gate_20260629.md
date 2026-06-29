# ES Other Campaigns Source Gate - 2026-06-29

Verdict: NEEDS MANUAL REVIEW

## Context

The user asked to try other ES strategies/campaigns after the PDH/PDL VAP absorption and opening VAP large-200 acceptance branches failed. The search remained under the existing methodology constraints:

- no post-result mechanics rescue unless explicitly approved;
- one campaign must have exactly five variants;
- do not relabel failed or near-miss branches as candidates;
- use local/no-paid data first;
- preserve `PASS`, `FAIL`, or `NEEDS MANUAL REVIEW` verdict labels.

## New Campaign Tried

`es_emv_macro_news_intraday` was authored as a five-variant ES campaign using lagged monthly FRED/Baker-Bloom-Davis EMV macro-news state with a month-end plus 21-calendar-day availability lag.

Result:

- campaign: `campaigns/es_emv_macro_news_intraday/campaign.yaml`
- summary: `backtest-campaigns/es_emv_macro_news_intraday/campaign_test_summary.json`
- stage reached: `limited_core_grid_test`
- decision: `FAIL`
- official variants tested: 5
- official limited-core combinations: 135
- profitable combinations: 7
- benchmark-passing combinations: 1
- Apex-rule-violating combinations: 0
- candidate report created: false

No variant reached WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

## Active ES Campaign Inventory

Current active ES campaign check after the EMV run:

- active ES campaign definitions under `campaigns/`: 164
- top-level ES `campaign_test_summary.json` files under `backtest-campaigns/`: 163
- top-level ES summaries with `FAIL`: 163
- top-level ES summaries with `PASS`: 0
- missing top-level ES summary: `es_archive_morning_orderflow_hold_retest`, already marked `FAIL` in source campaign metadata and archived by name

This supports the existing local-inventory conclusion: the active ES report tree has no unresolved local full-stage candidate.

## Source-Family Gate

Potential no-paid public-source follow-ups were checked against `_archived/research_campaign_ledger.md` and current `research_artifacts/` inventory before launching any new campaign.

Rejected or duplicate source families include:

- Chicago Fed NFCI/ANFCI financial conditions: explicitly rejected as a financial-conditions near miss and duplicate of the broader financial-stress/liquidity family.
- NFIB small-business sentiment: explicitly rejected before staged implementation.
- AAII investor sentiment, GDPNow, ADS, SPF Anxious Index, retail sales, JOLTS, housing cycle, HPSI, NY Fed SCE, capacity utilization, OECD CLI, CMDI, productivity/unit-labor-cost, BLS price pressure, Census trade, FHWA VMT, rail freight, CDC ILINet, USDM drought, lunar phase, EIA petroleum, and related public-source screens: already rejected or source-gated in prior audits.
- Local Sierra-only price-action/orderflow branches: exhausted by the active campaign tree and the local no-duplicate inventory gate.

Launching another simple state, rank, z-score, level, change, or fixed-time intraday variant from these families would violate the duplicate/retest guardrail rather than create a new independent campaign.

## Remaining Ranked Paths

The remaining credible ES paths are not executable under current local/no-paid constraints:

1. Longer ES+MES `trades` history for the predeclared ES/MES divergence validation protocol.
2. A bounded ES `tbbo` quote-liquidity pilot for quote-confirmed sweep/reclaim mechanics.

The refreshed ES `tbbo` dry-run manifest on 2026-06-29 estimated a bounded one-year RTH pilot at about `$5.95` with 262 sessions and 20 sampled sessions, but no TBBO DBN files or quote-liquidity feature cache exist locally. No paid data was downloaded.

## Decision

NEEDS MANUAL REVIEW

Reason: one new no-paid five-variant ES campaign was tried and failed, the active local ES campaign tree has no unresolved top-level pass, and the remaining non-duplicate paths require explicit data approval or manual authorization to revisit rejected families. No `candidate_strategy_report.md` should be created from this state.

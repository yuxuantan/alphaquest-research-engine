# ES Local-Only Strategy Inventory - 2026-06-29

Verdict: FAIL

## Request

Try other ES strategies that do not require data outside this project.

## Scope

- No new external data downloads.
- Use existing `campaigns/`, `backtest-campaigns/`, `data/cache/`, and `data/external/` artifacts only.
- Do not relabel an already rejected edge as a new campaign.
- Do not tune or rescue a failed family without explicit rescue/reopen approval.

## Checks Performed

### Active Campaign Coverage

- Active ES campaign directories under `campaigns/es_*`: 164.
- Top-level ES campaign summaries under `backtest-campaigns/es_*/campaign_test_summary.json`: 163.
- Top-level ES campaign summaries with a non-FAIL decision: 0.
- The one active campaign without a top-level aggregate summary is `es_archive_morning_orderflow_hold_retest`. Its `campaign.yaml` decision is `FAIL`, its five variants have per-run staged artifacts, and the ledger records all five variants failed `limited_core_grid_test`.

### Project-Local Data Families

The project already contains local ES data that can support no-new-data testing:

- ES Sierra completed-bar RTH OHLCV and aggregate orderflow.
- Sierra footprint imbalance, absorption, developing VAP, opening VAP, and large-200 proxy caches.
- Exact video AOI / LVN orderflow playbook caches.
- ES/MES flow-divergence, participation-crowding, and footprint-liquidity caches.
- ES/NQ cross-index lead-lag cache.
- ES term-structure lead-lag cache.
- Existing public/local feature CSVs under `data/external/`, including CBOE, FRED, credit ETF, OFR, EMV, seasonality/event, and related macro/market-state files.

### Already Rejected Or Gated

- OHLCV/calendar/technical families: opening range, opening gap, overnight drift/reversal/range, day-of-week, preholiday, Connors RSI2, daily reversal, time-series momentum, pivot structure, range compression, and related local price-action branches are already active FAIL or archive-rejected.
- Sierra aggregate orderflow and footprint/VAP families: signed/large-trade flow continuation/reversion, absorption/exhaustion, VAP AOI, opening VAP, prior levels, PDH/PDL VAP sweep, and exact video AOI/LVN variants are already failed.
- Cross-instrument local families: ES/MES flow divergence/crowding/sweep, ES/NQ lead-lag, and ES term-structure lead-lag have existing staged FAIL evidence.
- Public/local feature families: CBOE volatility/skew/put-call/correlation, default spread, credit ETF, OFR stress, EMV macro-news, CFTC, real-activity, sentiment, and related macro/market-state campaigns are failed or source/data-gated.
- The existing `credit_spread_state` entry module is not a valid new campaign path: the explicit HY/IG credit-spread state was data-gated because the usable ranked ES session span starts in 2023, which is too short for the default staged WFA methodology.

## Decision

No new five-variant campaign was launched. Under the requested local-only constraint, another ES campaign would either duplicate a failed family, reopen a failed branch without approval, or rely on a data-gated feature set that cannot pass the current staged methodology.

No `candidate_strategy_report.md` was created.

## Next Valid Actions

- Manual exception: explicitly approve reopening one named failed family or a one-time rescue, with the rescue scope defined before testing.
- New edge: provide a genuinely distinct project-data-only thesis and source support that is not covered by the failed families above.
- Data-gated path: excluded by this request, but the previously ranked paths remain longer ES/MES trade history or a bounded ES TBBO pilot after explicit approval.

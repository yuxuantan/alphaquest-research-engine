# ES Active Set Data-Gate Refresh - 2026-06-16

## Scope

This refresh checks the current active ES research set after the limited-core
period-reporting fix and the latest local-only campaigns. Archived tests remain
ignored for duplicate-edge checks.

## Active Evidence Inventory

Latest active sweep after `es_treasury_rate_shock_intraday`:

- Active campaigns: 39
- Source variants: 195
- Rescue configs: 195
- Raw variant-level reports: 408
- Passing reports: 0
- Active variants missing an original `run1` report: 2
- Active variants missing `rescue1`: 0

Every active failed variant has exactly one rescue run available under the
current per-failed-variant rescue rule. No active strategy has produced a
`candidate_strategy_report.md`.

The two apparent missing original `run1` reports are older
`es_prior_session_ibs_reversion` variants with original failure evidence under
`run2`, plus completed `rescue1` reports:

- `delayed_low_ibs_long_range_filtered`
- `delayed_high_ibs_short_range_filtered`

## Local Duplicate And Density Gate

Do not launch another local campaign that is only a renamed or lightly filtered
version of these active failed families. The active set now covers the major
local OHLCV, Sierra aggregate-orderflow, local ES/NQ, local term-structure,
public calendar, public volatility-state, and lagged realized-moment families.

Recent checks also confirm that sparse event-calendar branches generally fail
the trade-count requirement before WFA. Under the current rule to stop pursuing
ideas unlikely to reach at least 50 trades per year, a new sparse calendar
campaign is not justified without a materially stronger pre-test thesis.

## Required Data Still Missing

Present:

- `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv`
- `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`

Missing:

- `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`
- `data/cache/orderflow/es_mes_price_flow_divergence_1m_20200101_20260609.csv`
- `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`

The missing 2020-start ES/MES cache blocks the retained longer-history
ES/MES flow-divergence validation branch. The missing TBBO liquidity cache
blocks the quote-confirmed liquidity-sweep branch.

## Retained Branch Priority

1. Longer ES/MES `trades` validation remains the strongest retained branch.
   It is the only local-screened branch with meaningful one-year staged
   evidence, but it requires approved ES and MES `trades` data back to
   2020-01-01. The durable metadata-only estimate remains about `$949.34` and
   must be refreshed before any approved download.
2. ES `tbbo` quote-liquidity sweep remains a bounded pilot, not acceptance
   evidence. The existing metadata-only estimate is about `$14.88` for the
   one-year RTH pilot, but the user has already noted that one year is not very
   useful for final acceptance.

No paid data was downloaded in this refresh.

## Decision

FAIL for the current local active campaign set.

The overall goal remains unresolved: no ES candidate strategy has passed the
full staged methodology. Continuing without weakening the methodology now
requires either an approved external-data branch or a genuinely new dense,
point-in-time local data source that is not a duplicate of an active failed
edge.

## Post-EPU Update - 2026-06-16

After adding and completing `es_epu_policy_uncertainty_intraday`, the active
sweep is:

- Active campaigns: 42
- Source variants: 210
- Rescue configs: 210
- Raw variant-level reports: 438
- Aggregate passing reports: 0
- EPU variants missing an original `run1` report: 0
- EPU variants missing `rescue1`: 0

The EPU campaign used only free public Daily U.S. EPU data and local Sierra ES
RTH bars. No paid data was downloaded.

## Post-Consumer-Sentiment Update - 2026-06-16

After adding and completing `es_consumer_sentiment_state_intraday`, the active
sweep is:

- Active campaigns: 43
- Source variants: 215
- Rescue configs: 215
- Raw variant-level reports: 448
- Aggregate passing reports: 0
- Consumer-sentiment variants missing an original `run1` report: 0
- Consumer-sentiment variants missing `rescue1`: 0

The consumer-sentiment campaign used only free public FRED/University of
Michigan `UMCSENT` data and local Sierra ES RTH bars. No paid data was
downloaded.

## Post-Cboe-Put-Call Update - 2026-06-16

After adding and completing `es_cboe_put_call_sentiment_intraday`, the active
sweep is:

- Active campaigns: 44
- Source variants: 220
- Rescue configs: 220
- Raw variant-level reports: 458
- Aggregate passing reports: 0
- Cboe put/call variants missing an original `run1` report: 0
- Cboe put/call variants missing `rescue1`: 0

The Cboe put/call campaign used only free public Cboe CSVs and local Sierra ES
RTH bars. No paid data was downloaded.

# Local No-Duplicate ES Data-Gate Audit

Date: 2026-06-15

Status: FAIL

## Purpose

This audit records the local stop condition after the corrected engine/stage
audit and seven active ES campaigns. Archived tests are now explicitly ignored
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

Updated rescue policy: each failed variant can be rescued once. Rescue attempts
may change existing fixed parameters or tunable parameter space, but not the
core strategy mechanic. Completed parameter-only rescues for all 35 active
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
`data/reports/campaigns/archive*/`, `research_artifacts/*archive*`, and archived
report-refresh CSV/JSON manifests.

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

Continuation check on the long OHLCV cache: this cache is locally usable. Under
the active-only duplicate policy, archived OHLCV-only tests do not block a new
campaign. The active rejected OHLCV/bar families from this run remain
range-compression, prior-session IBS, Connors RSI2, RTH risk premium, and
overnight-intraday reversal. The active rejected Sierra aggregate-orderflow
families now include ES/MES micro-flow divergence and own-ES signed-orderflow
persistence.

Latest verification: `python3 -m research.preflight --skip-tests` passed with
108 active configs checked, and the active ES variant-level report sweep found
73 reports, 0 passes, and 0 `run1` variants missing `rescue1`.

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

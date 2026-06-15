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
- The long local Databento OHLCV cache was rechecked. It remains usable.
  Archived tests are ignored for duplicate-edge checks, so archived OHLCV-only
  families do not block a fresh campaign by themselves. Active rejected
  OHLCV/bar families from this run remain range-compression, prior-session IBS,
  Connors RSI2, RTH risk premium, and overnight-intraday reversal.
  Active rejected aggregate-orderflow families now include ES/MES micro-flow
  divergence and own-ES signed-orderflow persistence.

## Local Data State

Current ES orderflow-related local files:

- `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.validation.json`
- `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv`
- `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`
- `data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv`

Current ES price/volume local files:

- Long Databento 1-minute OHLCV parquet history under `data/cache/databento`.

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

## Current Blocked Confirmation

The earlier campaign-level blocker was superseded by the user clarification
that each failed variant can be rescued once. After applying that rule to every
active failed variant, the blocker is active again: no local variant-level
report passes, and every active failed variant has consumed its single allowed
rescue. This is a fail-closed campaign state, not a claim that only paid data
can move the goal forward.

Continuation recheck:

- Active ES variant-level summary count: `73` `campaign_test_summary.json`
  files.
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
  `73` files under `backtest-campaigns/*/*/ES/*/campaign_test_summary.json`.
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
  signed-orderflow persistence under a new active name.

Conclusion: FAIL, not blocked. No active strategy passes. Meaningful progress
requires either a fresh local edge outside the active rejected families, or an
approved and available longer ES/MES `trades` cache or ES `tbbo` liquidity
cache for the retained external-data branches.

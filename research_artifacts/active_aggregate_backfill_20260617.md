# Active Aggregate Backfill - 2026-06-17

Decision: INFRASTRUCTURE / BOOKKEEPING FIX.

After the staged core/monkey gate correction, active campaign bookkeeping was
refreshed without changing strategy mechanics, signal definitions, parameter
spaces, or data sources.

## Backfilled Missing Aggregates

The following active campaigns had complete original and rescue variant evidence
but no campaign-level `campaign_test_summary.json`. Aggregate summaries were
generated from existing run artifacts only:

- `backtest-campaigns/es_connors_rsi2_mean_reversion/campaign_test_summary.json`
- `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_test_summary.json`
- `backtest-campaigns/es_prior_session_ibs_reversion/campaign_test_summary.json`

All three aggregate decisions are `FAIL`. No run in these campaigns reached WFA,
Monte Carlo, simulated incubation, frozen validation, or candidate reporting
under corrected gates.

## Normalized Older Aggregates

Older aggregate summaries that already had `decision: FAIL` but no explicit
`status` were normalized to `status: completed`. Existing evidence was not
reinterpreted except where the corrected core gate makes old monkey-stage reports
fail earlier because `number_passing_benchmark=0`.

## Verification

- Active authored campaigns: `45`.
- Campaign aggregate summaries after backfill: `45`.
- All three newly written aggregate JSON files validate with `python3 -m json.tool`.
- Ledger rows were appended for the three backfilled aggregate decisions.

No paid data was downloaded.


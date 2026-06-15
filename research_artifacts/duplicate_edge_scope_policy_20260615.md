# Duplicate Edge Scope Policy

Date: 2026-06-15

Decision: NEEDS MANUAL REVIEW

## Rule

Archived tests are ignored when checking whether a proposed campaign is a
duplicate edge.

Duplicate-edge checks should compare only against active research surfaces:

- `campaigns/*/campaign.yaml`
- active variant configs under `campaigns/*/variants/`
- active reports under `backtest-campaigns/`
- current non-archived rows in `research_ledger.csv`

The following are historical evidence only and must not block a new campaign as
a duplicate edge:

- `_archived/`
- `configs/campaigns/archive*/`
- `data/reports/campaigns/archive*/`
- `research_artifacts/*archive*`
- archived report-refresh CSV/JSON manifests

## Practical Effect

The seven active ES campaign families remain rejected for the current run:

- `es_mes_micro_flow_divergence_reversion`
- `es_prior_session_ibs_reversion`
- `es_connors_rsi2_mean_reversion`
- `es_range_compression_breakout`
- `es_rth_intraday_risk_premium`
- `es_overnight_intraday_reversal`
- `es_signed_orderflow_persistence`

Those active failures still block relaunching the same edge under a new active
name. Archived-only families no longer block a new campaign solely because they
were tested before. They may be used as historical context, but the duplicate
gate must ignore them.

## Required Workflow

Before starting a new campaign:

1. Check active `campaigns/` and active `backtest-campaigns/` only.
2. If the proposed edge is not already active, it is not rejected by the
   duplicate-edge gate merely because an archived test exists.
3. Still create a fresh `campaign.yaml`, exactly five variants, predeclared
   parameter space, and the full staged validation artifacts.
4. Do not use archived results to tune mechanics or parameters.

## Research State

This policy changes the duplicate-edge scope. It does not promote any completed
strategy. All active variants and their one allowed rescues still failed under
the current methodology, including the later
`es_signed_orderflow_persistence` campaign.

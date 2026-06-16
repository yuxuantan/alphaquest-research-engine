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
- archived report-refresh CSV/JSON manifests under `_archived/research_artifacts/`

## Practical Effect

The twenty-four active ES campaign families remain rejected for the current run:

- `es_mes_micro_flow_divergence_reversion`
- `es_prior_session_ibs_reversion`
- `es_connors_rsi2_mean_reversion`
- `es_range_compression_breakout`
- `es_rth_intraday_risk_premium`
- `es_overnight_intraday_reversal`
- `es_signed_orderflow_persistence`
- `es_opening_drive_inventory_absorption`
- `es_turn_of_month_seasonality`
- `es_daily_time_series_momentum`
- `es_late_day_intraday_momentum`
- `es_volume_shock_liquidity_reversal`
- `es_prior_day_stop_run_reclaim`
- `es_vwap_pullback_continuation`
- `es_cftc_tff_hedging_pressure`
- `es_market_plumbing_liquidity_capacity`
- `es_bankruptcy_distress_regime_reversion`
- `es_prior_session_level_breakout_continuation`
- `es_vpin_toxicity_continuation`
- `es_overnight_return_late_day_momentum`
- `es_prior_level_delta_dislocation`
- `es_orderflow_absorption_exhaustion_reversal`
- `es_day_of_week_seasonality`
- `es_overnight_inventory_sweep_reversion`

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
`es_signed_orderflow_persistence` and
`es_opening_drive_inventory_absorption`, `es_turn_of_month_seasonality`,
`es_daily_time_series_momentum`, `es_late_day_intraday_momentum`,
`es_volume_shock_liquidity_reversal`, `es_prior_day_stop_run_reclaim`,
`es_vwap_pullback_continuation`, `es_cftc_tff_hedging_pressure`, `es_market_plumbing_liquidity_capacity`, `es_bankruptcy_distress_regime_reversion`, `es_prior_session_level_breakout_continuation`, `es_vpin_toxicity_continuation`, `es_overnight_return_late_day_momentum`, `es_prior_level_delta_dislocation`, `es_orderflow_absorption_exhaustion_reversal`, and `es_day_of_week_seasonality`
campaigns.

Latest verification: `python3 -m research.preflight --skip-tests` passed with 363 configs checked; active sweep found 115 source variants, 115 one-time rescue configs, 248 raw variant-level reports, 0 passes, and no active variants missing `rescue1`.


## 2026-06-16 Overnight Inventory Sweep Reversion Update

Archived tests remained ignored for duplicate-edge decisions. `es_overnight_inventory_sweep_reversion` was admitted as a fresh active campaign because it tested completed ETH overnight high/low sweep-reclaim mechanics, not active overnight gap/return reversal, overnight-return late-day continuation, or prior RTH high/low stop-run reclaim.

Result: FAIL. Five originals and five one-time parameter-space rescues completed; zero reports passed. This edge is now active rejected evidence and blocks relaunching the same completed-overnight-boundary sweep-reversion mechanic under a new active name.

Latest verification: `python3 -m research.preflight --skip-tests` passed with 378 configs checked; active sweep found 24 active campaigns, 120 source variants, 120 rescue configs, 258 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1` report.

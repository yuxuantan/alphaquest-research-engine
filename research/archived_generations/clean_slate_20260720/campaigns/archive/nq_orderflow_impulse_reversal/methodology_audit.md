# Methodology Audit: nq_orderflow_impulse_reversal

## Edge Definition

This campaign tests NQ completed-bar orderflow-impulse reversal. A signal requires an extreme prior-same-clock signed-flow rank and a same-direction completed rolling return at a fixed decision time. The trade fades that completed impulse at the next bar open.

## No-Lookahead Controls

- Same-clock ranks must be built from prior same-clock observations only.
- Rolling signed-flow and return windows use completed 1-minute bars only.
- A 10:00 ET decision uses the bar that closed at 10:00 ET and can enter no earlier than the next bar open.
- Stops are based on the completed signal-bar high/low plus a tick offset, not a future extreme.
- No final VWAP, final volume profile, future daily range, future session extreme, or post-entry orderflow is used.

## Data And Execution Controls

- Data source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.
- Timezone: `America/New_York`.
- Instrument economics: NQ tick size `0.25`, point value `$20`, tick value `$5`.
- Costs: `$2.50` commission per contract and one tick slippage.
- Same-bar stop/target ambiguity is handled by the existing staged engine rules.

## Duplicate Check

This campaign is not treated as independent because it uses signed flow somewhere. It is independent only because it fades a completed flow-plus-price impulse. It is distinct from signed-flow persistence, weak-displacement absorption/exhaustion, volume-ratio shock reversal, sell-flush VWAP/RSI capitulation, and impulse-pause continuation.

## Pre-Test Decision

Approved for preflight and density testing. The ES source failed, so any NQ result must clear the full staged workflow before being called a candidate strategy.

## Outcome

The pre-PnL density audit passed all 45 declared entry rows:
`research_artifacts/nq_orderflow_impulse_reversal_density_audit_20260630.md`.

The staged campaign failed at `limited_core_grid_test`. All five variants had
0/27 profitable combinations and 0 benchmark-passing combinations; no branch
reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or
candidate reporting. Aggregate evidence:
`backtest-campaigns/nq_orderflow_impulse_reversal/campaign_test_summary.json`.

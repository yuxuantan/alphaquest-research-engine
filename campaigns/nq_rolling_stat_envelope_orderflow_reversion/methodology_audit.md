# Methodology Audit: nq_rolling_stat_envelope_orderflow_reversion

## Edge Definition

This campaign tests NQ intraday rolling statistical-envelope reversion with same-side orderflow pressure. A signal uses only completed bars: the rolling close mean/std envelope is computed before the signal bar is recorded, and orderflow confirmation comes from the completed signal bar.

## No-Lookahead Controls

- Rolling envelope statistics exclude the signal bar and use prior completed closes only.
- Same-bar aggregate orderflow is available only after the signal bar closes.
- The engine must enter no earlier than the next bar open after a completed-bar signal.
- Stops are based on the completed signal-bar high/low plus a tick offset.
- No final VWAP, final range, final volume profile, future orderflow, or future return is used.

## Data And Execution Controls

- Data source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.
- Timezone: `America/New_York`.
- Instrument economics: NQ tick size `0.25`, point value `$20`, tick value `$5`.
- Costs: `$2.50` commission per contract and one tick slippage.
- Same-bar stop/target ambiguity is handled by the existing staged engine rules.

## Duplicate Check

The campaign is independent only because the primary trigger is an intraday rolling mean/std close envelope with same-bar orderflow pressure into the extension. It is distinct from prior daily Bollinger environment classification, low-toxicity extension fades, VWAP deviations, volume-shock reversals, same-clock impulse reversals, and absorption/exhaustion fades.

## Pre-Test Decision

Approved for preflight and density testing. The ES source failed, so any NQ result must clear the full staged workflow before being called a candidate strategy.

## Outcome

The pre-PnL density audit passed all 45 declared entry rows:
`research_artifacts/nq_rolling_stat_envelope_orderflow_reversion_density_audit_20260630.md`.

The staged campaign failed at `limited_core_grid_test`. All five variants had
0 profitable combinations and 0 benchmark-passing combinations; no branch reached
monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate
reporting. Aggregate evidence:
`backtest-campaigns/nq_rolling_stat_envelope_orderflow_reversion/campaign_test_summary.json`.

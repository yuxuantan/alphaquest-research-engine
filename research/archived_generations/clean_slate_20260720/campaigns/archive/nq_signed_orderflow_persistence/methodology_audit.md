# Methodology Audit: nq_signed_orderflow_persistence

## Edge Definition

This campaign tests native NQ completed-bar signed-flow persistence. The signal is not a price-pattern breakout, pullback, external ETF state, MES/NQ divergence, or seasonality effect. It asks whether completed rolling NQ signed-flow imbalance, confirmed by same-direction rolling return, continues after the decision time.

## No-Lookahead Controls

- Rolling flow and return features are built from completed 1-minute bars only.
- A 10:00 ET decision uses the bar that closed at 10:00 ET and can enter no earlier than the next bar open.
- No final VWAP, final volume profile, future daily range, future session extreme, or post-entry orderflow is used.
- All variants flatten intraday before the configured prop-firm cutoff.

## Data And Execution Controls

- Data source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.
- Timezone: `America/New_York`.
- Instrument economics: NQ tick size `0.25`, point value `$20`, tick value `$5`.
- Costs: `$2.50` commission per contract and one tick slippage.
- Same-bar stop/target ambiguity is handled by the existing staged engine rules.

## Duplicate Check

The campaign is not treated as independent because it uses signed flow somewhere. It is independent only because signed flow is the primary edge and is evaluated at fixed completed-bar decision times. Prior NQ failures that used signed flow as a confirmation layer remain distinct: MES divergence, impulse-pause continuation, wide-range continuation, prior-session breakout confirmation, and external-risk state campaigns.

## Pre-Test Decision

Approved for preflight and density testing. The ES source failed, so any NQ result must clear the full staged workflow before being called a candidate strategy.

## Outcome

The pre-PnL density audit is `research_artifacts/nq_signed_orderflow_persistence_density_audit_20260630.md`. The campaign failed before staged PnL because only 20/45 declared entry-grid rows passed the full-history, limited-core proxy, and latest-window density gates. No PnL, WFA, Monte Carlo, holdout, or candidate report was run.

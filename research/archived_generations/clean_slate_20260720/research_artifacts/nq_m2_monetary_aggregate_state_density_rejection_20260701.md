# NQ M2 Monetary Aggregate State Density Rejection - 2026-07-01

Verdict: FAIL

## Edge Screened

Strictly lagged broad money supply / real-money state as a liquidity and discount-rate regime proxy for NQ.

Primary public sources screened:
- FRED M2SL: https://fred.stlouisfed.org/series/M2SL
- FRED M2REAL: https://fred.stlouisfed.org/series/M2REAL
- Federal Reserve H.6 release family: https://www.federalreserve.gov/releases/h6/current/default.htm

## Pre-PnL Density Finding

Prototype features used a conservative 60-calendar-day availability lag and rolling ranks of nominal M2 and real M2 1/3/6/12-month changes plus 3-month-vs-12-month acceleration.

The density scan did not support an official five-variant campaign. Only one tail, `m2_change_3m_rank_120m high`, cleared all inspected density windows across the tested thresholds `[0.55, 0.60, 0.65]`, and the latest-window count was exactly at the minimum acceptable boundary. Other plausible M2 / real-M2 acceleration and contraction states were too sparse or failed at least one window.

## Duplicate / Integrity Decision

No PnL, stop, target, monkey, WFA, Monte Carlo, prop-rule, or holdout result was inspected. The edge is rejected before campaign launch because a single surviving density expression cannot honestly produce five distinct strategy variants without duplicated mechanics or forced parameter siblings.

Do not relaunch this edge under another name unless new data or a materially different monetary-liquidity mechanism is documented before any PnL testing.

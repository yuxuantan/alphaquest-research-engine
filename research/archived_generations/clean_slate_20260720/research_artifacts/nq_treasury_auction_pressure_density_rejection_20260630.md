# NQ Treasury Auction Pressure Density Rejection - 2026-06-30

Verdict: FAIL before NQ PnL.

## Edge

Preannounced nominal Treasury note/bond auction dates as an ex-ante cross-asset
supply-pressure event for NQ intraday trades. This is distinct from the already
tested NQ Treasury-rate shock campaign because it uses the auction calendar only,
not lagged Treasury yield or curve changes.

## Duplicate Review

No active top-level `nq_treasury_auction_pressure` campaign exists. The edge is
related to, but not a duplicate of, `nq_treasury_rate_shock_intraday`: auction
pressure is an event/supply calendar, while the rate-shock campaign uses lagged
yield and curve state.

## Density Gate

The source ES campaign, `es_treasury_auction_pressure`, used the official
FiscalData/Treasury coupon-auction calendar and reported only 100 to 121 total
full-history trades for the auction-day variants across 2011-2026. That is far
below the configured benchmark requirement of 50 trades per year. Because NQ
would use the same auction dates, an NQ port cannot satisfy the density gate
without changing the edge into a different event family.

No NQ PnL, stop, target, or trade outcome was inspected.

## Decision

FAIL. Do not create a staged NQ campaign for this edge unless the research
standard changes to explicitly permit sparse event studies with different gates.

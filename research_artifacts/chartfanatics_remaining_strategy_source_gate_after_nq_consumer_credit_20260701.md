# ChartFanatics Source Gate After NQ Consumer Credit State

Date: 2026-07-01

Verdict: FAIL

No new ChartFanatics ES/NQ campaign was launched after closing `nq_consumer_credit_state`.

## Live Pages Rechecked

- `https://www.chartfanatics.com/strategies`
- `https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy`
- `https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model`
- `https://www.chartfanatics.com/strategies/liquidity-inversion-model`
- `https://www.chartfanatics.com/strategies/order-flow-strategy`
- `https://www.chartfanatics.com/strategies/amd-model`
- `https://www.chartfanatics.com/strategies/smt-divergence-po3`
- `https://www.chartfanatics.com/strategies/futures-trading-strategy`
- `https://www.chartfanatics.com/strategies/auction-market-strategy`
- `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`
- `https://www.chartfanatics.com/strategies/market-dna-strategy`
- `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`
- `https://www.chartfanatics.com/strategies/universal-strategy`
- `https://www.chartfanatics.com/strategies/volume-profile-strategy`

## Duplicate And Data Gate

Already represented or rejected locally:

- 80/20 NQ price-ending reaction: `nq_20_80_price_ending_barrier`
- Measured-move pullback continuation: `nq_chartfanatics_measured_move_pullback`
- Daily Bollinger environment: `nq_chartfanatics_daily_bollinger_environment`
- SMT / PO3 midpoint reversion: `nq_chartfanatics_smt_po3_midpoint_reversion`
- AMD accumulation/manipulation/distribution: `nq_chartfanatics_amd_fomc_distribution`
- JadeCap session-liquidity / FVG: `nq_chartfanatics_jadecap_session_liquidity_fvg`
- Liquidity inversion / FVG: `nq_chartfanatics_liquidity_inversion_fvg`
- London trident / FVG continuation: `nq_chartfanatics_london_trident_fvg_continuation`
- Weekly stage / breakout bias: `nq_chartfanatics_weekly_stage_breakout_bias`
- Order-flow absorption, LVN/AOI, POC/value-area, VWAP, volume-profile, prior-session, and large-print ideas: already covered by local ES/NQ orderflow/profile families and the user-exact ES video AOI/LVN orderflow playbook.

Not locally testable without changing data scope:

- VIX futures strategy: requires intraday/current VIX confirmation against prior VIX highs/lows and ES/NQ previous-day level reactions. The local tested VIX features are prior-close/as-of daily features, not intraday VIX path data.
- Market DNA / Bookmap / depth-heavy tape strategies: require depth-of-book or Bookmap-style event semantics not available in the current Sierra 1-minute aggregate cache.
- Catalyst/tape discretionary support/resistance pages: not a single frozen, testable ES/NQ futures edge under the current cache without new event/catalyst data.

## Decision

Launching another ChartFanatics-named campaign from this source pass would duplicate a failed local edge or silently alter unavailable intraday/depth requirements into a different strategy. The no-duplicate-edge rule therefore rejects the ChartFanatics branch at source gate.

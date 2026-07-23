# ChartFanatics ES/NQ Strategy Gate After Real-Yield Campaign

Timestamp: 2026-07-01T00:25:00+08:00

Verdict: NEEDS MANUAL REVIEW for the ChartFanatics source pool; no new ES/NQ campaign was eligible for staged PnL without duplicating an already tested edge or using unavailable data.

Context:
- The current non-ChartFanatics NQ real-yield/breakeven campaign was tested and failed staged validation.
- The user requested a fresh ChartFanatics website review for ES/NQ strategies not yet tested.
- The ChartFanatics strategy index was refreshed from `https://www.chartfanatics.com/strategies`.

Website candidates reviewed:

1. The VIX Futures Strategy
- Source: `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`
- Local decision: data-gated for faithful testing and partially duplicate for broad VIX state.
- Reason: the described ES/NQ method compares same-moment ES/NQ prior-day-high/low behavior against VIX previous-day high/low or intraday VIX pressure. The repo has lagged daily VIX features and already failed ES/NQ VIX level, term-structure, VVIX, VIX expiration, and NQ VIX-pressure/orderflow families. A faithful ChartFanatics VIX level-confirmation campaign needs intraday VIX high/low/level data aligned to ES/NQ bars, not just prior Cboe daily closes.

2. Market DNA Strategy
- Source: `https://www.chartfanatics.com/strategies/market-dna-strategy`
- Local decision: data-gated.
- Reason: the method requires tape reading, Level II/depth, passive liquidity walls, catalysts, and real-time aggressive-vs-passive control shifts. The local Sierra cache has completed-bar aggregate trades/orderflow, not historical book depth or passive wall data. A mechanically degraded aggregate-orderflow substitute would not be the same edge.

3. Nasdaq ICT and Order Flow Scalping Strategy
- Source: `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`
- Local decision: duplicate/data-gated.
- Reason: the core components are liquidity sweeps, IFVG/FVG, structure shifts, VWAP/POC, and Bookmap/order-flow confirmation. Local ChartFanatics-derived SMT/PO3, liquidity inversion FVG, London/Unique-HRR FVG, prior POC, and sweep/reclaim families have already been tested or rejected. The Bookmap heatmap/depth requirement is unavailable.

4. Yush Order Flow Strategy / OrderFlow Trading Masterclass
- Sources:
  - `https://www.chartfanatics.com/strategies/order-flow-strategy`
  - `https://www.chartfanatics.com/strategies/orderflow-trading-masterclass`
- Local decision: duplicate/data-gated.
- Reason: large-lot thresholds, trapped buyers/sellers, absorption, delta shifts, POC/VWAP, and market-generated levels are already represented across ES AOI/VAP/LVN/orderflow campaigns and NQ orderflow transfer campaigns. Missing historical heatmap/DOM depth prevents faithful retesting of the Bookmap-style version.

5. Auction Market Theory / Auction Market Strategy / Volume Profile / Low Volume Node
- Sources:
  - `https://www.chartfanatics.com/strategies/auction-market-theory-strategy`
  - `https://www.chartfanatics.com/strategies/auction-market-strategy`
  - `https://www.chartfanatics.com/strategies/volume-profile-strategy`
- Local decision: duplicate.
- Reason: balance/imbalance, value acceptance/rejection, POC magnets, VAH/VAL, LVN/VAP, and edge-to-edge auction movement have already been tested through prior value-area, prior POC, LVN/VAP, opening VAP, and auction-style orderflow campaigns on ES/NQ.

6. Intraday Liquidity & Volatility Model / Liquidity Strategy / AMD Model / SMT + PO3
- Sources:
  - `https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model`
  - `https://www.chartfanatics.com/strategies/liquidity-strategy`
  - `https://www.chartfanatics.com/strategies/amd-model`
  - `https://www.chartfanatics.com/strategies/smt-divergence-po3`
- Local decision: duplicate.
- Reason: session liquidity raids, FVG/MSS confirmations, Turtle Soup/false breakout behavior, AMD/PO3, and SMT-style ES/NQ divergence have already been tested or source-gated through the ChartFanatics SMT/PO3, liquidity inversion FVG, London/Unique-HRR FVG, prior-day stop-run reclaim, and related sweep/reclaim campaigns.

7. Break & Retest
- Source: `https://www.chartfanatics.com/strategies/break-retest`
- Local decision: duplicate.
- Reason: the mechanical edge is a prior major level break, no entry on the break, then a completed retest/confirmation outside a no-trade zone. ES and NQ prior-session S/R flip retest campaigns and opening-range retest campaigns already tested this economic idea with stricter completed-bar/orderflow confirmation.

8. Trendline Strategy / Structure + OTE
- Sources:
  - `https://www.chartfanatics.com/strategies/trendline-strategy`
  - `https://www.chartfanatics.com/strategies/structure-ote`
- Local decision: not eligible under current staged intraday/no-overnight assumptions.
- Reason: both are higher-timeframe swing frameworks requiring discretionary trendlines, POIs/order blocks/breakers, and multi-session holds. Retooling them into same-day forced-flatten strategies would change the edge rather than test it.

Already tested ChartFanatics-derived ES/NQ campaigns:
- `nq_20_80_price_ending_barrier`
- `nq_chartfanatics_measured_move_pullback`
- `nq_chartfanatics_daily_bollinger_environment`
- `nq_chartfanatics_liquidity_inversion_fvg`
- `nq_chartfanatics_smt_po3_midpoint_reversion`
- `nq_chartfanatics_london_trident_fvg_continuation`
- `nq_prior_poc_orderflow_magnet`
- `nq_round_number_orderflow_barrier`
- ES/NQ LVN/VAP/AOI/orderflow and prior-session retest families relevant to the ChartFanatics orderflow/auction pages

Action taken:
- No new ChartFanatics ES/NQ staged campaign was launched from this refreshed review.
- Launching any remaining page would either duplicate a failed edge under a new name or require new historical data: intraday VIX, depth-of-book/heatmap/DOM, or explicit catalyst tape data.

Required to reopen:
- Intraday VIX OHLC or tick/minute history aligned to ES/NQ bars for the VIX confirmation playbook.
- Historical book-depth/heatmap or Level II liquidity-wall data for Market DNA and Bookmap-heavy orderflow playbooks.
- Explicit user authorization to test a degraded proxy version, with the artifact clearly marked as a proxy rather than the ChartFanatics strategy.

# ChartFanatics Remaining Strategy Source Gate After NQ Round-Number Orderflow - 2026-06-30

Status: NEEDS MANUAL REVIEW.

Scope: refreshed the live ChartFanatics strategy index on 2026-06-30 after closing `nq_round_number_orderflow_barrier`.

Live source URLs reviewed:

- https://www.chartfanatics.com/strategies
- https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy
- https://www.chartfanatics.com/strategies/order-flow-strategy
- https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy
- https://www.chartfanatics.com/strategies/auction-market-theory-strategy
- https://www.chartfanatics.com/strategies/the-vix-futures-strategy
- https://www.chartfanatics.com/strategies/futures-trading-strategy
- https://www.chartfanatics.com/strategies/volume-profile-strategy
- https://www.chartfanatics.com/strategies/auction-market-strategy
- https://www.chartfanatics.com/strategies/liquidity-strategy
- https://www.chartfanatics.com/strategies/unique-high-rr
- https://www.chartfanatics.com/strategies/amd-model
- https://www.chartfanatics.com/strategies/smt-divergence-po3
- https://www.chartfanatics.com/strategies/low-volume-node
- https://www.chartfanatics.com/strategies/market-auction-theory
- https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model
- https://www.chartfanatics.com/strategies/structure-ote

New campaign closed before this source-gate refresh:

- `nq_round_number_orderflow_barrier`: FAIL at `limited_core_grid_test`. All five predeclared variants failed the official profitable-iteration stability gate; best variant-level profitable rate was `24/54 = 0.444444`, below the required `0.70`. No WFA, Monte Carlo, incubation, acceptance OOS, or candidate report was reached.

Already represented by current local ChartFanatics campaigns:

- 80/20 Nasdaq Strategy -> `nq_20_80_price_ending_barrier` failed density.
- Measured Move Trend Strategy -> `nq_chartfanatics_measured_move_pullback` failed density.
- Anthony Crudele Futures Trend/Bollinger framework -> `nq_chartfanatics_daily_bollinger_environment` failed density.
- SMT/PO3 50% reversal -> `nq_chartfanatics_smt_po3_midpoint_reversion` failed density.
- Liquidity/FVG inversion -> `nq_chartfanatics_liquidity_inversion_fvg` failed density.
- Unique High RR / London Trident -> `nq_chartfanatics_london_trident_fvg_continuation` failed density.
- Auction/profile POC return-to-value -> `nq_prior_poc_orderflow_magnet` failed density.
- Fixed round-number with completed aggregate orderflow confirmation -> `nq_round_number_orderflow_barrier` failed limited core.

Remaining futures-relevant pages not launched:

| ChartFanatics source | Disposition | Reason |
| --- | --- | --- |
| Nasdaq ICT and Order Flow Scalping | DATA-GATED / DUPLICATE | Requires higher-timeframe discretionary context, Asia session, Bookmap/tape/heatmap confirmation, and seconds-scale entry refinement. The locally testable RTH liquidity/FVG subset overlaps `nq_chartfanatics_liquidity_inversion_fvg`, prior-day stop-run, opening-range, and orderflow confirmation families. |
| Trader Yush Order Flow Strategy | DUPLICATE / DATA-GATED | AOI, PDH/PDL/ONH/ONL, value area, LVN, big trades, delta, absorption, and trapped-trader mechanics overlap `es_video_aoi_lvn_orderflow_playbook`, ES/NQ profile/AOI campaigns, and the newly failed NQ round-number orderflow transfer. Strict large-print/depth/tape confirmation is not available for NQ in the current completed-bar aggregate cache. |
| VIX Futures Strategy | DUPLICATE / PARTIAL DATA-GATE | Repo already has ES/NQ VIX level, VIX term-structure, VXN/VIX dispersion, VVIX, variance-risk-premium, VIX-expiration, and NQ VIX-pressure/orderflow families. The page's live VIX-versus-ES/NQ prior-level confirmation would require reliable intraday VIX observations beyond the current lagged daily Cboe feature caches. |
| Auction Market Theory, Auction Market Strategy, Market Auction Theory, Volume Profile Strategy, Low Volume Node | DUPLICATE | Covered by prior POC magnet, prior value-area acceptance, pivot-filtered value-area, true VAP, LVN, AOI/LVN orderflow, and ES video AOI/LVN campaigns. A fresh implementation would be a sibling expression of the same profile/auction edge. |
| Liquidity Strategy, Intraday Liquidity & Volatility, AMD Model, Structure + OTE | DUPLICATE / DATA-GATED | These map to liquidity sweep, prior-level stop-run, FVG inversion, market-structure pullback, and macro-news displacement families already tested or density-gated. Full versions require ETH/Asian/London session structure, high-impact news context, or discretionary higher-timeframe POI selection. |
| Unique High RR | TESTED / DATA-GATED | The London Trident/FVG expression was already tested as `nq_chartfanatics_london_trident_fvg_continuation` and failed density. The source's London session and discretionary daily trend-management mechanics remain outside the current RTH-only local test lane. |
| Futures Trading Strategy | TESTED | Implemented as `nq_chartfanatics_daily_bollinger_environment`; rejected before PnL by density. |
| Broad/non-ES/NQ playbooks | NOT A SINGLE NONDUPLICATE ES/NQ EDGE | Market DNA, OrderFlow Masterclass, 5 Stage Trading Framework, options/psychology masterclasses, stock-specific first-red-day/parabolic/small-cap/episodic-pivot/support-resistance pages, and forex-specific PO3/OTE/ADR or trendline-break-pocket pages do not define a new mechanical ES/NQ futures edge under the current campaign rules. |

Conclusion: after closing `nq_round_number_orderflow_barrier`, no additional ChartFanatics ES/NQ campaign is eligible without violating the no-duplicate-edge rule, requiring unavailable depth/ETH/tape/intraday-VIX data, or materially changing the source mechanics. No new ChartFanatics campaign was launched from this refresh.

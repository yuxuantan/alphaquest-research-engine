# ChartFanatics Remaining Strategy Source Gate After NQ POC Magnet - 2026-06-30

Status: NEEDS MANUAL REVIEW.

Scope: refreshed the live ChartFanatics strategy index on 2026-06-30 after the current London Trident/FVG campaign and after testing the new NQ prior-POC magnet campaign.

New campaign launched from this pass:
- `nq_prior_poc_orderflow_magnet`: FAIL at pre-PnL density screen. Only 21/45 declared entry-grid rows and 1/5 variants passed all density gates; no PnL was inspected.

Already represented by current local ChartFanatics campaigns:
- 80/20 Nasdaq Strategy -> `nq_20_80_price_ending_barrier` failed density.
- Measured Move Trend Strategy -> `nq_chartfanatics_measured_move_pullback` failed density.
- Anthony Crudele Futures Trend/Bollinger framework -> `nq_chartfanatics_daily_bollinger_environment` failed density.
- SMT/PO3 50% reversal -> `nq_chartfanatics_smt_po3_midpoint_reversion` failed density.
- Liquidity/FVG inversion -> `nq_chartfanatics_liquidity_inversion_fvg` failed density.
- Unique High RR / London Trident -> `nq_chartfanatics_london_trident_fvg_continuation` failed density.
- Auction/profile POC return-to-value -> `nq_prior_poc_orderflow_magnet` failed density in this pass.

Remaining futures-relevant pages not launched:
- VIX Futures Strategy: duplicate of existing ES/NQ VIX pressure, VIX term-structure, VXN/VIX dispersion, variance-risk, and VIX-expiration families.
- Auction Market Strategy, Auction Market Theory Strategy, Market Auction Theory, Volume Profile Strategy, Low Volume Node: now covered or duplicate-adjacent to NQ prior-POC magnet, NQ prior value-area acceptance, ES prior POC/LVN, ES video AOI/LVN, and other profile/VAP campaigns. A new version would be a sibling expression rather than a new edge.
- Order Flow Strategy, Orderflow Trading Masterclass, Market DNA Playbook: require tape/depth/passive wall/aggressive order interaction or catalyst-specific real-time information not present in the current completed-bar Sierra aggregate cache. Local AOI/orderflow/large-print proxies have already been tested or data-gated.
- Intraday Liquidity & Volatility Model, Liquidity Playbook, AMD Model, Universal Strategy, Break & Retest, Structure + OTE, Trendline Strategy: overlap existing liquidity sweep, prior-level stop-run, market-structure, FVG-inversion, measured-pullback, trendline/retest, and orderflow confirmation families. Several also require ETH/Asian/London/session liquidity or higher-timeframe discretionary context not available in the current RTH-only test translation.
- Futures Trading Strategy: already represented by the daily Bollinger environment campaign.
- Non-ES/NQ or not market-behavior strategy pages: 5 Stage Trader Framework, psychology/options masterclasses, first-red-day/parabolic/small-cap/episodic-pivot/stock support-resistance pages, PO3 OTE ADR Forex, trendline break pocket Forex, and stock swing playbooks.

Conclusion: after the new NQ prior-POC magnet density failure, no additional ChartFanatics ES/NQ page was selected without violating the no-duplicate-edge rule, requiring unavailable depth/ETH/tape data, or materially changing the source mechanics. Next continuation should use a non-ChartFanatics source, a new data approval, or explicit user authorization to test a near-duplicate family.

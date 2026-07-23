# Chart Fanatics Remaining Futures Strategy Source Gate - 2026-06-30

Status: NEEDS MANUAL REVIEW as of 2026-06-30T12:32:12+08:00.

Scope: after completing the current NQ campaign and testing new Chart Fanatics-derived NQ campaigns, review remaining Chart Fanatics ES/NQ-relevant strategy pages for non-duplicate, locally testable campaign candidates.

Tested from this Chart Fanatics pass:
- `nq_20_80_price_ending_barrier`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_measured_move_pullback`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL at pre-PnL density screen.

Remaining futures pages reviewed and not launched:
- Break & Retest: duplicate of already rejected NQ prior-session high/low break/retest and ES opening/prior-session retest families. Local evidence includes `nq_prior_session_level_breakout_continuation` rejected before PnL and `es_prior_session_flip_retest_orderflow` / `es_opening_range_retest_orderflow` failed limited-core testing.
- Liquidity Inversion, Intraday Liquidity & Volatility Model, Liquidity Strategy, AMD Model, SMT/PO3/OTE: overlap existing liquidity-sweep, prior-level, market-structure, AOI/orderflow, and macro-event families. Several require FVG/order-block/discretionary confirmation or premarket/Asian/London session levels not present in the current RTH-only NQ cache.
- Unique High RR: data-gated because the stated London kill-zone window is 03:00-06:30 New York time, while the local NQ Sierra cache used here is RTH-only, 09:30-15:59 New York time.
- Trendline Strategy and Structure + OTE: swing/multi-day frameworks requiring 4-hour or daily/weekly top-down trendline/POI management and overnight exposure. Current prop-style configs force same-day flatten and no overnight positions; intraday-only translation would materially change the edge and overlap completed pivot/market-structure campaigns.
- Market DNA / OrderFlow masterclass pages: require tape, Level II/depth, aggressive/passive order interaction, or catalyst-specific real-time orderflow not available in the current Sierra aggregate-bar cache. Existing local AOI/orderflow/large-print proxies have already been rejected or data-gated.
- Algorithmic Strategy: methodology/process page for generating and filtering systems, not a single market-behavior edge suitable for a five-variant campaign.
- Auction Market Theory, Volume Profile, LVN, VIX futures, and broad orderflow pages: duplicate existing value-area/profile/LVN/VIX/orderflow campaign families already tested or rejected.

Conclusion: no further Chart Fanatics ES/NQ strategy was selected in this pass without violating the no-duplicate-edge rule or changing the source mechanics to fit the local RTH-only data. Next valid continuation requires either a new non-duplicate source outside Chart Fanatics, explicit approval to test a near-duplicate variant family, or new data approval for ETH/premarket/London/Asian-session or depth/tape-level features.

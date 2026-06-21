# ES Market-Structure Pivot Combination Queue - 2026-06-20

Standalone result: `es_market_structure_pivot_trend_bias` was tested as a pure completed swing-pivot HH/HL or LH/LL direction edge. Five original variants and five one-time parameter-space rescues all failed limited core. No WFA, Monte Carlo, incubation, frozen validation, or candidate report was reached.

Selection rule: combine the pivot structure only with dense price-action or aggregate-orderflow edges where the pivot state is a predeclared direction filter. Do not use it as a post-failure patch, do not make the pivot filter tunable after results, and reject before PnL if the combined signal density is unlikely to keep at least 50 trades/year.

Selected composite queue:

1. `es_mes_participation_crowding_reversion` -> `es_pivot_filtered_mes_participation_crowding_reversion`
   Status: completed failed. Reason: MES crowding fade can be treated as pullback-with-structure only when the fade direction agrees with confirmed pivots.

2. `es_prior_value_area_orderflow_acceptance` -> `es_pivot_filtered_prior_value_area_acceptance`
   Status: completed failed. Reason: prior value acceptance is a price-action/orderflow continuation edge where confirmed structure is a natural direction gate.

3. `es_vwap_pullback_continuation` -> `es_pivot_filtered_vwap_pullback_continuation`
   Status: completed failed. Reason: VWAP pullback continuation should only pass the composite gate when benchmark reclaim direction agrees with confirmed structure.

4. `es_opening_range_orderflow_breakout` -> `es_pivot_filtered_opening_range_orderflow_breakout`
   Status: queued next. Reason: opening-range breakout is a high-density price-action/orderflow edge and the pivot filter is a predeclared continuation direction gate.

5. `es_spx_0dte_expiration_pressure` -> `es_pivot_filtered_spx_0dte_expiration_pressure`
   Status: queued after density check. Reason: 0DTE pressure can be tested only if post-May-2022 full-week variants retain enough trade density after the structure gate; otherwise reject before PnL and replace with another dense price-action/orderflow base campaign.

Academic support used for the pivot leg: Lo, Mamaysky, and Wang (2000) for deterministic local-extrema technical-pattern definitions; Moskowitz, Ooi, and Pedersen (2012) and Hurst, Ooi, and Pedersen (2017) for trend persistence context across futures. Each composite still uses its base campaign's own primary-edge sources and must pass the unchanged staged gates.

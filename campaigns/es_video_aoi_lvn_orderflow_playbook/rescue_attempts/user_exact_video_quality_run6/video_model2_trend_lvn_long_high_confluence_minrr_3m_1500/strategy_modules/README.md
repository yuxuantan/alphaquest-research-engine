# video_model2_trend_lvn_long_high_confluence_minrr_3m_1500

Run6 quality-filter variant after run5 exact-video proxy failed limited core.

Mechanic: Long-only Model 2 trend LVN pullback with higher AOI confluence, optional directional delta threshold, minimum structural target distance, and fixed-R fallback.

Changes versus run5 are predeclared before testing run6:

- Higher AOI quality through `entry.params.min_aoi_confluences`.
- Trend variants optionally require stronger directional delta confirmation.
- `signal_price` keeps structural targets only when they meet the configured minimum target R; otherwise it uses the fixed-R fallback.
- Same Sierra developing VAP / overnight / large-200 cache, same 3-minute ES timeframe, same stop module, same costs, and same prop-rule settings.

This is not claimed to exactly match the video; it is a quality-filter rescue branch designed to test the run5 failure modes without changing the economic edge family.

# afternoon_large20_two_sided_rejection rescue1

Campaign: `es_prior_value_area_orderflow_rejection`

This is the single allowed rescue for the failed variant. It preserves the prior value-area rejection entry mechanic, orderflow confirmation, 5-minute timeframe, Sierra local data, costs, fill assumptions, validation gates, and prop-rule settings.

Allowed parameter-space change: test faster return-to-value exits with `sl.params.stop_offset_ticks: [0, 1, 2]` and `tp.params.target_r_multiple: [0.25, 0.4, 0.6]`. The rationale is that the original limited-core run had adequate tradable signal density but negative net PnL, so the only plausible same-mechanic rescue is to check whether the edge is a smaller, faster rejection move rather than a larger fixed-R reversal.

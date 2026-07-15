# or60_signed_pivot_flow_breakout_1200

Campaign: nq_pivot_filtered_opening_range_orderflow_breakout

Mechanic: 60-minute signed-flow opening-range breakout filtered by completed 15/30-minute pivot direction. The base opening-range breakout must emit first; the pivot filter cannot create trades by itself.

Rationale: NQ port of the ES pivot-filtered opening-range orderflow breakout using the ES rescue grid selected before any NQ PnL inspection. The base ORB signal must fire first; completed swing-pivot structure can only reject a signal.

Source ES config: campaigns/es_pivot_filtered_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/or60_signed_pivot_flow_breakout_1200/config.yaml

# three_slot_up_extension_fade_short

Campaign: nq_low_toxicity_orderflow_extension_fade

Mechanic: Three short-only slots fade upside extensions when same-clock orderflow imbalance is unusually low.

Rationale: NQ port of the ES low-toxicity orderflow extension-fade rescue grid selected before any NQ PnL inspection. Same-clock ranks use only prior sessions, and entries use completed five-minute bars.

Source ES config: campaigns/es_low_toxicity_orderflow_extension_fade/rescue_attempts/parameter_space_rescue_1/three_slot_up_extension_fade_short/config.yaml

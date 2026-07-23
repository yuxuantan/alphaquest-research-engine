# extreme_negative_pressure_short_1330

Campaign: `nq_cftc_tff_hedging_pressure`

Mechanic: At the completed 13:30 ET 5-minute bar, enter short when shifted SPX TFF open-interest change is below an extreme negative threshold; flatten at 15:55 ET unless stop or target is hit.

Source ES config: `campaigns/es_cftc_tff_hedging_pressure/variants/extreme_negative_pressure_short_1330/config.yaml`

Lookahead control: CFTC/TFF feature is shifted in the local feature file; signal uses the completed configured 5-minute bar; entry is next bar open or later.

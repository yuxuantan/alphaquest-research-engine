# high_positive_pressure_long_0935

Campaign: `nq_cftc_tff_hedging_pressure`

Mechanic: At the completed 09:35 ET 5-minute bar, enter long when shifted SPX TFF open-interest change is above a high positive threshold; flatten at 15:55 ET unless stop or target is hit.

Source ES config: `campaigns/es_cftc_tff_hedging_pressure/variants/high_positive_pressure_long_0935/config.yaml`

Lookahead control: CFTC/TFF feature is shifted in the local feature file; signal uses the completed configured 5-minute bar; entry is next bar open or later.

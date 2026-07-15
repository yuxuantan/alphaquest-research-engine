# broad_positive_pressure_long_1100

Campaign: `nq_cftc_tff_hedging_pressure`

Mechanic: At the completed 11:00 ET 5-minute bar, enter long when shifted SPX TFF open-interest change is above a broad positive threshold; flatten at 15:55 ET unless stop or target is hit.

Source ES config: `campaigns/es_cftc_tff_hedging_pressure/variants/broad_positive_pressure_long_1100/config.yaml`

Lookahead control: CFTC/TFF feature is shifted in the local feature file; signal uses the completed configured 5-minute bar; entry is next bar open or later.

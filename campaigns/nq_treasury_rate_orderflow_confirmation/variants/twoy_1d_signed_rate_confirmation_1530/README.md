# twoy_1d_signed_rate_confirmation_1530

A sharp prior-day 2-year yield move proxies front-end policy-rate repricing; NQ trades only when same-day price and signed flow confirm the direction. This variant uses 1-day 2-year yield change rank and signed_volume confirmation. The signal waits for a completed 5-minute NQ bar, enters on the next bar, and never uses same-session Treasury observations.

Pre-PnL density at fixed review settings was 864 full-sample signals, about 55.99/year, and 61.09/year in the limited-core reference window.

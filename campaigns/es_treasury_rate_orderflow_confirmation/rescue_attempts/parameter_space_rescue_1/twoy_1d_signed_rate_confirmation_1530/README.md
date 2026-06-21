# twoy_1d_signed_rate_confirmation_1530

A sharp prior-day 2-year yield move proxies front-end policy-rate repricing; ES trades only when same-day price and signed flow confirm the direction. This variant uses 1-day 2-year yield change rank and signed_volume confirmation. The signal waits for a completed 5-minute ES bar, enters on the next bar, and never uses same-session Treasury observations.

Pre-PnL density at fixed review settings was 864 full-sample signals, about 55.99/year, and 61.09/year in the limited-core reference window.

Rescue 1: parameter-space-only rescue. Rate threshold, orderflow threshold, and stop-distance grids were adjusted; TP remains at or above 1.0R and no mechanics were changed.

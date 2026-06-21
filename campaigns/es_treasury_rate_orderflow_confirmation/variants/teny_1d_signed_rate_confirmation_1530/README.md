# teny_1d_signed_rate_confirmation_1530

A sharp prior-day 10-year yield increase can pressure ES through discount-rate repricing; a sharp decrease can support ES if same-day price and signed flow agree. This variant uses 1-day 10-year yield change rank and signed_volume confirmation. The signal waits for a completed 5-minute ES bar, enters on the next bar, and never uses same-session Treasury observations.

Pre-PnL density at fixed review settings was 834 full-sample signals, about 54.05/year, and 70.19/year in the limited-core reference window.

# curve_1d_signed_rate_confirmation_1530

A sharp curve steepening can mark term-premium/inflation pressure while flattening can mark rate-relief dynamics; ES trades only with price/flow confirmation. This variant uses 1-day 10y-2y curve change rank and signed_volume confirmation. The signal waits for a completed 5-minute ES bar, enters on the next bar, and never uses same-session Treasury observations.

Pre-PnL density at fixed review settings was 800 full-sample signals, about 51.85/year, and 70.84/year in the limited-core reference window.

# teny_5d_signed_rate_confirmation_1530

A multi-day 10-year yield move may represent persistent discount-rate pressure or relief; ES continuation requires same-day price and flow confirmation. This variant uses 5-day 10-year yield change rank and signed_volume confirmation. The signal waits for a completed 5-minute ES bar, enters on the next bar, and never uses same-session Treasury observations.

Pre-PnL density at fixed review settings was 851 full-sample signals, about 55.15/year, and 72.79/year in the limited-core reference window.

Rescue 1: parameter-space-only rescue. Rate threshold, orderflow threshold, and stop-distance grids were adjusted; TP remains at or above 1.0R and no mechanics were changed.

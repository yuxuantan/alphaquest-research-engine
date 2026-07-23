# teny_1d_large10_rate_confirmation_1530

A prior-day 10-year shock should matter more when larger ES prints confirm same-day repricing pressure; the large-10 flow filter is the participation proxy. This variant uses 1-day 10-year yield change rank with large-10 flow confirmation and large10 confirmation. The signal waits for a completed 5-minute ES bar, enters on the next bar, and never uses same-session Treasury observations.

Pre-PnL density at fixed review settings was 897 full-sample signals, about 58.13/year, and 52.64/year in the limited-core reference window.

Rescue 1: parameter-space-only rescue. Rate threshold, orderflow threshold, and stop-distance grids were adjusted; TP remains at or above 1.0R and no mechanics were changed.

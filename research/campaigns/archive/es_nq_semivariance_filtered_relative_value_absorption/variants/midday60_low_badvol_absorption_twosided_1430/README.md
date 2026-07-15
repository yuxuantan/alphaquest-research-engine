# midday60_low_badvol_absorption_twosided_1430

From 13:00:00 through 14:30:00 ET, take the first completed one-minute bar per session where ES/NQ 60-minute relative-value divergence meets the configured spread threshold, ES signed-flow absorption over the same completed lookback is counter to the ES price leg, and the prior completed RTH session is in a low prior downside-semivariance regime. Entry is next bar open. Stop is percent from entry; target is fixed-R with reward:risk never below 1.0; unresolved trades flatten at 15:30:00 ET.

Pre-PnL density screen: all 6 entry-parameter corners cleared the 50 trades/year floor; limited-core minimum was 59.04/year and latest-year minimum was 56.04/year.

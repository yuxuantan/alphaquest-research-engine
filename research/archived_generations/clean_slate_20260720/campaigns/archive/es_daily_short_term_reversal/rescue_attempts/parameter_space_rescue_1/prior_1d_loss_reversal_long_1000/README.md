# prior_1d_loss_reversal_long_1000

Long ES at the 10:00 ET completed 5-minute bar when the prior completed one-session RTH close-to-close return is negative by at least the configured threshold. This is the long-side expression of the daily short-term reversal edge.

The signal uses only prior RTH closes recorded after completed sessions. The current session close is not part of the return calculation, and the engine must enter no earlier than the next bar open.

Rescue attempt 1 keeps the same side, lookback, signal time, modules, data, costs, and gates. It changes only the declared threshold, stop, and target parameter space plus matching fixed defaults.

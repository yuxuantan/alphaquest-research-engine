# high_1q_net_equity_short_1000

At 10:00 ET, short NQ when the 180-calendar-day-lagged one-quarter net equity issuance to market value rank is elevated.

Entry module: `corporate_equity_supply_state`. The module reads the strict-lag feature CSV, waits for the configured completed one-minute bar close, and relies on the engine for next-bar-open execution.

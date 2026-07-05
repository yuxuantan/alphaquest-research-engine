# high_4q_net_equity_short_1030

At 10:30 ET, short NQ when the 180-calendar-day-lagged four-quarter net equity issuance to market value rank is elevated.

Entry module: `corporate_equity_supply_state`. The module reads the strict-lag feature CSV, waits for the configured completed one-minute bar close, and relies on the engine for next-bar-open execution.

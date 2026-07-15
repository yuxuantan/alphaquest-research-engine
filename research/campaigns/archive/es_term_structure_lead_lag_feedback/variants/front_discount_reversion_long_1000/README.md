# front_discount_reversion_long_1000

Mechanic: at 10:00 ET, use only completed 09:30-09:59 front and next-contract ES bars. Go long front ES when the front contract has fallen enough and has underperformed the next contract by the configured spread gap.

This expresses the campaign edge as front-contract discount feedback during the first RTH half hour. The 1-minute timeframe preserves completed-bar feature timing and next-bar ES entry.

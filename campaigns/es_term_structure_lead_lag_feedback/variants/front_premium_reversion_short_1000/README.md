# front_premium_reversion_short_1000

Mechanic: at 10:00 ET, use only completed 09:30-09:59 front and next-contract ES bars. Go short front ES when the front contract has risen enough and has outperformed the next contract by the configured spread gap.

This expresses the campaign edge as front-contract premium feedback during the first RTH half hour. The 1-minute timeframe preserves completed-bar feature timing and next-bar ES entry.

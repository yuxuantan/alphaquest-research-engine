# morning_mes_buy_pressure_reversion_short

At 10:00 ET, go short NQ when completed 09:30-09:59 MES-minus-NQ signed-flow imbalance exceeds the threshold, then flatten at 11:31 ET unless stop or target is hit.

This NQ port uses MES as a cross-index micro-flow proxy, not native MNQ orderflow.

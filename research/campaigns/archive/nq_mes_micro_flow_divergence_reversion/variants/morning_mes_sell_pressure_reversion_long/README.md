# morning_mes_sell_pressure_reversion_long

At 10:00 ET, go long NQ when completed 09:30-09:59 NQ-minus-MES signed-flow imbalance exceeds the threshold, then flatten at 11:31 ET unless stop or target is hit.

This NQ port uses MES as a cross-index micro-flow proxy, not native MNQ orderflow.

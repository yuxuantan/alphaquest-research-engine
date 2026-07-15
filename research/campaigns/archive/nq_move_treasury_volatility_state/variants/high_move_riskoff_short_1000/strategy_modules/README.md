# high_move_riskoff_short_1000

Entry module: `move_treasury_vol_state`

Mechanic: At 10:00 ET, short NQ when the latest prior MOVE close is high in its 252-day rank and the five-day MOVE change is also high.

Stop module: `percent_from_entry`; take-profit module: `fixed_r`; forced flatten: `15:55:00` ET.

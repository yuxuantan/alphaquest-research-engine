# low_move_carry_long_1000

Entry module: `move_treasury_vol_state`

Mechanic: At 10:00 ET, long NQ when the latest prior MOVE close is low in its 252-day rank and the five-day MOVE change rank is also low.

Stop module: `percent_from_entry`; take-profit module: `fixed_r`; forced flatten: `15:55:00` ET.

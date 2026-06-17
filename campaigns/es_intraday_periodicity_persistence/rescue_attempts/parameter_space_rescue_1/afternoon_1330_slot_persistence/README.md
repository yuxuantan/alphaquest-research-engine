# afternoon_1330_slot_persistence

At 13:30 ET, trade the 13:30-14:00 slot in the same direction as the prior
same-slot rolling mean return when its absolute value clears the configured bps
threshold. The signal uses only prior sessions and exits no later than 14:00 ET.


Rescue attempt 1 changes only the fixed/default values and parameter grid: stricter prior-mean thresholds, tighter percent stops, and lower fixed-R targets. The slot, entry module, direction rule, data, timeframe, costs, and stage gates are unchanged.

# late_afternoon_1430_slot_persistence

At 14:30 ET, trade the 14:30-15:00 slot in the same direction as the prior
same-slot rolling mean return when its absolute value clears the configured bps
threshold. The signal uses only prior sessions and exits no later than 15:00 ET.


Rescue attempt 1 changes only the fixed/default values and parameter grid: stricter prior-mean thresholds, tighter percent stops, and lower fixed-R targets. The slot, entry module, direction rule, data, timeframe, costs, and stage gates are unchanged.

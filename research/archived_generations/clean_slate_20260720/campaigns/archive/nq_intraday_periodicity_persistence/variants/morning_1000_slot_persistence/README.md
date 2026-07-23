# morning_1000_slot_persistence

At 10:00 ET, trade the 10:00-10:30 slot in the same direction as the prior
same-slot rolling mean return when its absolute value clears the configured bps
threshold. The signal uses only prior sessions and exits no later than 10:30 ET.

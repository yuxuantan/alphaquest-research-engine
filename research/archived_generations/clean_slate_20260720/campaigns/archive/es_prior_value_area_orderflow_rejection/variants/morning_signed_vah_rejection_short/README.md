# morning_signed_vah_rejection_short

Morning vah probe that closes back inside prior value with sell/counterflow. The prior value profile is frozen from the completed previous RTH session; the signal requires a completed probe and close back inside value with counterflow, next-bar entry, signal-bar extreme stop, and fixed-R retracement target.

Pre-PnL density note: the 2-tick rejection buffer was excluded before any PnL testing because it fell below the 50 signals/year floor in the limited-core window. The tested grid keeps the same rejection mechanic with 0- and 1-tick buffers.

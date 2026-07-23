# yush_range_1

Fixed-mechanics POC requested by the user.

Implementation notes:
- Uses 3-minute ES bars for public levels, previous/current 3-minute sweep window, and ATR(14).
- Replays Sierra SCID records inside each 3-minute bar for entry timing.
- Builds the developing session volume profile from replayed SCID records with 1-point buckets.
- Requires POC in the middle third of the 70% value area and at most one LVN bucket inside value where volume is below 20% of POC volume.
- Requires a PDH, PDL, PDC, ONH, or ONL sweep in the previous completed 3-minute bar or current developing 3-minute bar.
- Requires price within 2 ATR of VAL for long or VAH for short.
- Long absorption is a 1-point bucket with cumulative delta <= -300 followed by 3 seconds with price above the bucket top. Short absorption is the inverse.
- Stop is exactly two ticks beyond the absorption bucket edge; target is fixed 2R.
- During candidate bars, the expensive range/profile gates are recomputed once per second while the underlying SCID state continues to update on every record.

Source-quality caveat: Sierra SCID records are not exchange MBO sequencing. This is a deterministic intrabar replay proxy, not queue-level or vendor-print-equivalent footprint truth.

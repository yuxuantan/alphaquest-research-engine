# Methodology Audit: NQ Prior-Session Breakout Orderflow Confirmation

Decision: FAIL

All five variants failed `limited_core_grid_test`. Pre-PnL density used prepared 5-minute bars with `pdh_pdl_sweep`; large-trade and retest variants were excluded before PnL for insufficient density. No rescue was run because no rescue was explicitly authorized.

| Variant | Profitable combos | Benchmark combos | Best net | Best PF | Best MAR |
|---|---:|---:|---:|---:|---:|
| all_day_signed_buffer_break_two_sided | 0/48 | 0 | -1715.00 | 0.546 | -0.667 |
| all_day_signed_high_volume_break_two_sided | 0/72 | 0 | -1885.00 | 0.522 | -0.667 |
| first_half_signed_no_buffer_break_two_sided | 0/24 | 0 | -1930.00 | 0.510 | -0.667 |
| morning_signed_no_buffer_break_two_sided | 0/24 | 0 | -1580.00 | 0.473 | -0.667 |
| opening_gap_hold_signed_continuation | 29/48 | 0 | 1837.50 | 1.277 | 0.919 |

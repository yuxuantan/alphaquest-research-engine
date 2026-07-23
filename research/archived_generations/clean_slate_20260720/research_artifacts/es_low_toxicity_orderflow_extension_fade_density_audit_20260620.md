# ES Low-Toxicity Orderflow Extension Fade Density Audit - 2026-06-20

Pre-PnL signal density was measured on local 5-minute Sierra ES RTH bars after building rolling trade-orderflow features and same-clock rank63 columns. No PnL, stop/target outcome, or parameter-performance information was inspected. Single-slot drafts were rejected before PnL for sub-50/year density; the selected multi-slot variants cleared the trade-count floor.

| variant | pre-PnL signals | approx signals/year | decision |
|---|---:|---:|---|
| `two_slot_morning_balanced_extension_fade` | 1878 | 121.71 | approve for testing |
| `two_slot_midday_balanced_extension_fade` | 1559 | 101.03 | approve for testing |
| `two_slot_late_balanced_extension_fade` | 1588 | 102.91 | approve for testing |
| `three_slot_up_extension_fade_short` | 2666 | 172.77 | approve for testing |
| `three_slot_down_extension_fade_long` | 2253 | 146.01 | approve for testing |

# ES Overnight Inventory Sweep Reversion

Decision: FAIL.

All five original variants and their single allowed rescues failed before WFA. `midpoint_low_sweep_reclaim_long/run1` passed the core grid at `0.8271604938271605` profitable combinations but failed `limited_monkey_test` with `0.26` profitable runs and median net `-601.25`. The other originals and all rescues failed `limited_core_grid_test`.

Best original by top core net: `morning_overnight_low_reclaim_long/run1` with top net `3997.5`, PF `1.1973586768699087`, trades `133`, and profitable-combo rate `0.1728395061728395`.

Best rescue by top core net: `midpoint_low_sweep_reclaim_long/rescue1` with top net `2996.875`, PF `2.8907728706624605`, trades `20`, and profitable-combo rate `0.6296296296296297`.

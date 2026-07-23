# ES Range Compression Orderflow Breakout Rescue Attempt 1

Date: 2026-06-17

Reason for rescue:
- All five original variants failed `limited_core_grid_test`.
- Best original profitable-combination rate was only `0.04938271604938271`.
- No original variant reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Rescue scope:
- One rescue is applied to each failed variant.
- The rescue is parameter-space-only.

Unchanged:
- Entry module: `range_compression_orderflow_breakout`
- Stop module: `percent_from_entry`
- Target module: `fixed_r`
- NR4 compression rule
- Breakout reference and source window
- Flow bucket and same-bar flow-confirmation rule
- Dataset and date window
- Costs, slippage, tick size, point value
- Session, flatten, prop-rule, and fill assumptions
- Stage criteria

Changed:
- Fixed stop default: `sl.params.stop_pct` from `0.004` to `0.0025`
- Fixed target default: `tp.params.target_r_multiple` from `1.5` to `0.75`
- Stop grid from `[0.0025, 0.004, 0.006]` to `[0.0015, 0.0025, 0.004]`
- Target grid from `[1.0, 1.5, 2.0]` to `[0.5, 0.75, 1.0]`

Rationale:
- Original top rows that were positive were rejected for concentration or weak robustness. The rescue tests whether range-compression breakouts with flow confirmation require faster realization and tighter risk to avoid dependence on isolated large days.
- This is not a mechanics change. Entry timing, compression state, breakout levels, flow direction, and data are unchanged.

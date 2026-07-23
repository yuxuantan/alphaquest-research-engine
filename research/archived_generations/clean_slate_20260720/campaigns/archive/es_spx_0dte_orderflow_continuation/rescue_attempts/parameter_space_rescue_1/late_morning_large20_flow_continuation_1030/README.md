# late_morning_large20_flow_continuation_1030 rescue1

This is the single allowed rescue for `late_morning_large20_flow_continuation_1030` in `es_spx_0dte_orderflow_continuation`.

It keeps the same `spx_0dte_orderflow_continuation` entry module, `percent_from_entry` stop module, `fixed_r` target module, 1-minute Sierra ES RTH data, SPX 0DTE calendar filter, signal time, flow mode, costs, fill assumptions, and validation gates.

Allowed rescue change: Rescue tests whether the late-morning large20 expression needs more inclusive first-hour displacement thresholds and a target range that gives continuation more room. The entry module, large20 flow mode, signal time, data window, costs, and validation gates are unchanged.

Forbidden in this rescue: changing the edge thesis, adding filters, changing modules, changing data windows, changing costs/fills, changing benchmark gates, or running another rescue for this failed variant.

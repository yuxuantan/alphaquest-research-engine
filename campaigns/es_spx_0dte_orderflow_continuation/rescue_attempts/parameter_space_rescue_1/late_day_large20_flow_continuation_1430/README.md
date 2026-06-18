# late_day_large20_flow_continuation_1430 rescue1

This is the single allowed rescue for `late_day_large20_flow_continuation_1430` in `es_spx_0dte_orderflow_continuation`.

It keeps the same `spx_0dte_orderflow_continuation` entry module, `percent_from_entry` stop module, `fixed_r` target module, 1-minute Sierra ES RTH data, SPX 0DTE calendar filter, signal time, flow mode, costs, fill assumptions, and validation gates.

Allowed rescue change: Rescue keeps the late-day cumulative large20 pressure entry grid and tests a moderate target band with slightly wider stop coverage to reduce reliance on one large late-session day. The entry module, calendar, signal time, flow mode, data window, costs, and validation gates are unchanged.

Forbidden in this rescue: changing the edge thesis, adding filters, changing modules, changing data windows, changing costs/fills, changing benchmark gates, or running another rescue for this failed variant.

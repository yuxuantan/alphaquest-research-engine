# midday_large20_flow_continuation_1330 rescue1

This is the single allowed rescue for `midday_large20_flow_continuation_1330` in `es_spx_0dte_orderflow_continuation`.

It keeps the same `spx_0dte_orderflow_continuation` entry module, `percent_from_entry` stop module, `fixed_r` target module, 1-minute Sierra ES RTH data, SPX 0DTE calendar filter, signal time, flow mode, costs, fill assumptions, and validation gates.

Allowed rescue change: Rescue keeps the midday cumulative large20 pressure entry grid but tests whether the original stops were too tight for a multi-hour source window. The entry module, calendar, signal time, flow mode, data window, costs, and validation gates are unchanged.

Forbidden in this rescue: changing the edge thesis, adding filters, changing modules, changing data windows, changing costs/fills, changing benchmark gates, or running another rescue for this failed variant.

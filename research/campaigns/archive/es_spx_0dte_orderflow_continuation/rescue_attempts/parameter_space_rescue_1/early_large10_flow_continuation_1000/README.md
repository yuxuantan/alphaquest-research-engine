# early_large10_flow_continuation_1000 rescue1

This is the single allowed rescue for `early_large10_flow_continuation_1000` in `es_spx_0dte_orderflow_continuation`.

It keeps the same `spx_0dte_orderflow_continuation` entry module, `percent_from_entry` stop module, `fixed_r` target module, 1-minute Sierra ES RTH data, SPX 0DTE calendar filter, signal time, flow mode, costs, fill assumptions, and validation gates.

Allowed rescue change: Rescue tests a tighter middle band for the early large10 displacement threshold and a wider risk/reward envelope. The large10 0DTE continuation mechanic, calendar, signal time, modules, data window, costs, and validation gates are unchanged.

Forbidden in this rescue: changing the edge thesis, adding filters, changing modules, changing data windows, changing costs/fills, changing benchmark gates, or running another rescue for this failed variant.

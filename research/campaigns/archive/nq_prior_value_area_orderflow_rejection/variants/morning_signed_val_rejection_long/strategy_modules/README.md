# Strategy modules

Entry: `prior_value_area_orderflow_rejection`
Stop-loss: `sweep_extreme`
Take-profit/exit: `fixed_r` plus configured same-day flatten.

This variant uses the shared repo modules rather than local copied code. The entry computes frozen prior-session VAH/VAL/POC from completed NQ RTH bars, then requires a completed current-session probe outside value, close back inside value, and counterflow before next-bar entry.

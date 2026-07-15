# NQ Wide Range Orderflow Continuation Methodology Audit

Verdict: FAIL.

Authored before NQ PnL inspection as a direct transfer of the ES wide-range orderflow continuation family. The original five variants, entry module, stop module, target module, timeframe, session windows, and declared parameter grid are preserved. Instrument metadata is changed only to NQ data, NQ point value, NQ tick value, and the available NQ cache end date.

Duplicate-edge screen: distinct from existing NQ morning momentum, midday range breakout, VWAP pullback, session-extreme delta divergence, volume-shock reversal, variance-ratio continuation, and opening-range failed-breakout families because this campaign requires a completed wide directional bar, close-location near the bar extreme, and same-bar aggregate orderflow alignment before next-bar entry.

Lookahead review: signal range, body, close location, volume ratio, and orderflow are read only after the completed 5-minute signal bar. Entry is no earlier than the next bar open. No future session high/low, VWAP, volume profile, final daily range, or future orderflow is used.

Pre-PnL density result: PASS. All 45 declared entry rows cleared the full-history, limited-core proxy, and latest-window density gates before any NQ PnL was inspected. Minimum full-history density was 140.62 signals/year, minimum limited-core density was 134.29 signals/year, and minimum latest-window count was 118.

Staged result: FAIL. All five variants failed `limited_core_grid_test`. Aggregate
core grid produced 38/270 profitable combinations and 25 benchmark-passing combinations,
with 0 Apex rule violations. The best top row was `morning_signed_range_expansion_long`
with net 5825.00 and PF 1.1885, but that variant reached only 29/54 profitable
combinations versus the required 70% profitable core-grid rate. No monkey, WFA,
Monte Carlo, simulated incubation, acceptance OOS, or candidate report was reached.

No rescue attempt is authorized after density or staged results.

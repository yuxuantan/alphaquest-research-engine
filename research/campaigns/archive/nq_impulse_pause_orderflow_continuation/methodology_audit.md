# NQ Impulse Pause Orderflow Continuation Methodology Audit

Verdict: FAIL.

Authored before NQ PnL inspection as a direct transfer of the ES impulse-pause orderflow continuation family. The five active ES variants, entry module, stop module, target module, timeframe, session windows, and declared parameter grid are preserved. Instrument metadata is changed only to NQ data, NQ point value, NQ tick value, and the available NQ cache end date.

Duplicate-edge screen: distinct from existing NQ wide-range, morning momentum, midday range breakout, VWAP pullback, session-extreme divergence, variance-ratio continuation, and opening-range failed-breakout families because this campaign requires three completed phases: directional impulse, shallow pause, and breakout close with same-bar aggregate orderflow confirmation.

Lookahead review: impulse and pause windows use only prior completed 5-minute bars. The breakout close and orderflow confirmation use only the completed signal bar. Entry is no earlier than the next bar open. No future high/low, VWAP, volume profile, final daily range, or future orderflow is used.

Pre-PnL density result: PASS. All 45 declared entry rows cleared the full-history, limited-core proxy, and latest-window density gates before any NQ PnL was inspected. Minimum full-history density was 142.43 signals/year, minimum limited-core density was 129.33 signals/year, and minimum latest-window count was 142.

Staged result: FAIL. Four variants failed `limited_core_grid_test`. The late-morning
large10 variant passed limited core and monkey, then failed `walk_forward_analysis`:
stitched OOS PF 1.0911 was below the 1.2 gate, stitched OOS MAR 0.2492 was below
the 0.4 gate, and only 5/10 OOS windows were profitable. No WFA OOS monkey, Monte
Carlo, simulated incubation, acceptance OOS, or candidate report was reached.

No rescue attempt is authorized after density or staged results.

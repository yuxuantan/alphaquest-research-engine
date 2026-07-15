# NQ Prior-Bar Key Reversal Orderflow Methodology Audit

Status: failed the pre-PnL density gate on 2026-06-30. No staged PnL was inspected.

- One campaign, one edge: immediately prior-bar failed micro-break reversal with completed aggregate orderflow confirmation.
- Duplicate screen: distinct from active NQ session-extreme, rolling-envelope, volume-shock, absorption/exhaustion, morning-extension reversal, and VWAP-deviation families.
- Instrument scaling: ES min_sweep_ticks [1, 2] scaled by the pre-PnL NQ/ES median 1-minute range ratio to [3, 6].
- Timing: prior-bar levels are known before the signal bar; signal-bar close/location/orderflow are used only after completion; entries are next 1-minute open or later.
- Parameter discipline: 18 combinations per variant, with two entry tunables, one stop tunable, and fixed 1R target.
- Rescue policy: no rescue authorized for this NQ search unless the user explicitly allows it after a failure.

Final density verdict: FAIL. All five variants had at least one sparse entry-grid row in the limited-core proxy window; the weakest row had 18.78 signals/year. Dropping sparse windows or grid corners after observing density would change the declared five-variant edge.

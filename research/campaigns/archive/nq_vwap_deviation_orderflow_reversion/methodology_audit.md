# NQ VWAP Deviation Orderflow Reversion Methodology Audit

Status: authored pending pre-PnL density and staged validation.

- One campaign, one edge: completed session-VWAP extension reversion with completed aggregate counterflow confirmation.
- Duplicate screen: distinct from active NQ VWAP pullback continuation, rolling statistical-envelope reversion, low-toxicity extension fade, daily Bollinger state, volume shock, and generic absorption/exhaustion families.
- Instrument scaling: ES deviation grid [8, 12, 16] ticks was scaled by the pre-PnL NQ/ES median RTH range ratio and rounded to [28, 40, 56] ticks.
- Timing: session VWAP, close-location, and counterflow are known only after the completed signal bar; entries are next-bar open or later.
- Parameter discipline: 27 combinations per variant, with two entry tunables, one stop tunable, and fixed 1R target.
- Rescue policy: no rescue authorized for this NQ search unless the user explicitly allows it after a failure.

## Pre-PnL Density Result

Decision: FAIL. Rejected before staged NQ PnL: 6/45 declared VWAP-deviation entry-grid rows failed the pre-PnL density gate. The sparse rows were in morning_large10_counterflow_1200 and morning_signed_counterflow_1200; the weakest limited-core proxy density was 29.79 signals/year. Dropping morning variants or strict deviation/counterflow corners after this screen would change the declared five-variant edge after observing signal availability. No NQ PnL was inspected.

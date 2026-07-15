# Strategy Modules

- Entry: `london_trident_fvg_continuation`
- Stop: `sweep_extreme`
- Target: `fixed_r`

The entry module waits for the long completed-bar London FVG/trident setup using EMA15 as the mid-stack EMA. Entry would be next 30-minute open, but staged PnL was not run after density failure.

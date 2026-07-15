# Strategy Modules

- Entry: `london_trident_fvg_continuation`
- Stop: `sweep_extreme`
- Target: `fixed_r`

The entry module waits for a completed London-window bearish FVG, a completed trident/doji pullback into the midpoint, and a completed confirmation candle. Entry would be next 30-minute open, but staged PnL was not run after density failure.

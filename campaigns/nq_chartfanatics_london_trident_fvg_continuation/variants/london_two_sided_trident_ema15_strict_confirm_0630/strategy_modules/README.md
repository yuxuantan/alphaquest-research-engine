# Strategy Modules

- Entry: `london_trident_fvg_continuation`
- Stop: `sweep_extreme`
- Target: `fixed_r`

The entry module allows two-sided completed-bar London FVG/trident setups using EMA15 and a one-tick stricter confirmation close. Entry would be next 30-minute open, but staged PnL was not run after density failure.

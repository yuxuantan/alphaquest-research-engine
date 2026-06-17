# ES Daily Short-Term Reversal Rescue Attempt 1

Date: 2026-06-17

Decision: FAIL.

## Rule

Each failed variant received exactly one rescue. Rescue changes were limited to
declared parameter space and matching fixed defaults. No rescue changed:

- entry module
- stop module
- target module
- direction mode
- lookback window
- signal time
- timeframe
- data source or data window
- costs, slippage, tick size, point value, fill assumptions, prop rules, or gates

## Rescue Change

The rescue made the same class of allowed change across variants:

- more selective return-pressure or z-score thresholds
- wider percentage stops
- smaller fixed-R targets

This was logged before rescue results were run.

## Results

| Variant | Run | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades | Terminal stage |
|---|---|---:|---:|---:|---:|---:|---|
| prior_1d_gain_reversal_short_1000 | run1 | 0.0 | 0 | -5320.625 | 0.5686562626672071 | 216 | limited_core_grid_test |
| prior_1d_gain_reversal_short_1000 | rescue1 | 0.0 | 0 | -3475.0 | 0.7378347793285552 | 215 | limited_core_grid_test |
| prior_1d_loss_reversal_long_1000 | run1 | 0.0 | 0 | -5607.5 | 0.511860718171926 | 194 | limited_core_grid_test |
| prior_1d_loss_reversal_long_1000 | rescue1 | 0.0 | 0 | -4841.25 | 0.6017071164129988 | 177 | limited_core_grid_test |
| prior_3d_two_sided_reversal_1130 | run1 | 0.0 | 0 | -3547.5 | 0.9100988342625443 | 342 | limited_core_grid_test |
| prior_3d_two_sided_reversal_1130 | rescue1 | 0.0 | 0 | -3547.5 | 0.9100988342625443 | 342 | limited_core_grid_test |
| prior_5d_two_sided_reversal_1330 | run1 | 0.0 | 0 | -8656.25 | 0.7740472461498303 | 340 | limited_core_grid_test |
| prior_5d_two_sided_reversal_1330 | rescue1 | 0.0 | 0 | -8200.0 | 0.8009104704097116 | 340 | limited_core_grid_test |
| vol_norm_5d_two_sided_reversal_1200 | run1 | 0.0 | 0 | -6270.0 | 0.7321085238196966 | 324 | limited_core_grid_test |
| vol_norm_5d_two_sided_reversal_1200 | rescue1 | 0.0 | 0 | -6570.0 | 0.7702797202797202 | 319 | limited_core_grid_test |

## Conclusion

All originals and all one-time rescues failed before monkey, WFA, Monte Carlo,
or frozen validation. No candidate strategy report was created.

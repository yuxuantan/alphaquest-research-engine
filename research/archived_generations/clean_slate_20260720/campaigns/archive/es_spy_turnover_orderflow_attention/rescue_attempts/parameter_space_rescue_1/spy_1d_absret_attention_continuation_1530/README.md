# spy_1d_absret_attention_continuation_1530

Two-sided ES continuation using prior SPY 1-day return direction and one-day absolute-return-times-volume attention rank. The signal uses prior-day SPY features only, then waits for completed ES price movement and signed aggregate orderflow before next-bar entry.

Pre-PnL density at the fixed review settings was 876 full-sample signals, about 56.77/year, and 63.69/year in the limited-core reference window.

Rescue 1: parameter-space-only rescue. Attention threshold, signed-flow threshold, and stop-distance grids were adjusted; TP remains at or above 1.0R and no mechanics were changed.

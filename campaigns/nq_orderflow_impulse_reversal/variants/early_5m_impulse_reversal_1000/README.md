# early_5m_impulse_reversal_1000

Fades a completed 5-minute NQ signed-flow and price impulse at 10:00 ET. The entry module waits for an extreme same-clock signed-flow rank and same-direction completed return, enters opposite the impulse on the next bar open, uses the signal-bar extreme plus offset as invalidation, and targets a short fixed-R retracement.

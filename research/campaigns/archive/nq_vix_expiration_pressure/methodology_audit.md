# Methodology Audit: nq_vix_expiration_pressure

This campaign is a pre-PnL NQ port of `es_vix_expiration_pressure`. The five variants preserve the ES source event calendar trigger, signal type, direction, entry time, stop module, target module, and 9-combination stop/target grid; only NQ data/economics and NQ-facing metadata were changed before any NQ PnL inspection.

Duplicate screen: distinct from tested NQ monthly OPEX, quarterly expiration, SPX 0DTE, VIX level/state, VIX term-structure, and VXN/VIX dispersion families because the signal is specifically the deterministic VIX derivatives settlement calendar.

Lookahead controls: the VIX settlement calendar is public before trading; entries use completed one-minute bars only and enter at next bar open; no SOQ, VIX level, VIX futures basis, option volume, final VWAP, or same-day high/low is used for signal decisions.

Risk caveat: event count is sparse and NQ exposure is indirect, so density, concentration, WFA, Monte Carlo, and prop-rule gates must fail closed.

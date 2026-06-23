# Methodology Audit - NQ Sector Opening Breadth Orderflow Continuation

Verdict: FAIL

## Edge And Source Contract
This campaign is a direct NQ port of the ES sector opening-breadth orderflow campaign. It uses same-day sector ETF raw opens, prior ETF raw closes, and completed NQ 5-minute price/orderflow confirmation.

## Lookahead Controls
- Sector open features for session D use only ETF raw Open on D and raw Close from the prior ETF trading day.
- Signals are no earlier than 10:00 ET after ETF opens are observable and NQ confirmation bars are complete.
- No same-day ETF close, ETF high/low, final NQ session high/low, final VWAP, future NQ return, or post-entry orderflow is used.

## Parameter Discipline
- Exactly five variants were authored before PnL testing.
- ES rescue parameter spaces were used as the starting NQ baseline.
- A pre-PnL density audit widened sector-count grids for sparse NQ variants before any NQ PnL, stop, target, WFA, Monte Carlo, or holdout result was inspected.
- No PnL-based rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `broad_down_morning_signed_short_1130`: max candidate sessions/year 41.27; below opportunity gate.
- `broad_two_sided_morning_large10_1130`: max candidate sessions/year 109.18; has at least one dense corner.
- `broad_up_early_signed_long_1000`: max candidate sessions/year 49.11; below opportunity gate.
- `cyclical_up_morning_signed_long_1130`: max candidate sessions/year 58.06; has at least one dense corner.
- `riskoff_cycdown_midday_signed_short_1230`: max candidate sessions/year 41.34; below opportunity gate.

## Final Decision
FAIL. The campaign failed closed at the pre-PnL density gate, so no candidate strategy report was created.

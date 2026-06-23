# Methodology Audit - NQ CBOE Put/Call Sentiment Intraday

Verdict: FAIL

## Edge And Source Contract
This campaign is a direct NQ port of the ES Cboe put/call sentiment campaign. It uses NQ Sierra 1-minute RTH bars and a feature file built from public Cboe daily put/call ratios mapped strictly before each NQ session date.

## Lookahead Controls
- Cboe daily ratios are merged strictly before the NQ session date; same-day Cboe totals are unavailable and not used.
- Rolling ranks use only lagged Cboe observations through the mapped observation date.
- Entry signals use the completed configured 1-minute bar; execution is next bar open or later.
- No final session high/low, final VWAP, future returns, or post-entry option volume is used.

## Parameter Discipline
- Exactly five variants were authored before testing.
- Each variant used one entry parameter, one stop parameter, and one target parameter.
- Each variant tested 27 combinations, inside the declared 8-120 range.
- No rescue, threshold pruning, date exclusion, or post-result mechanic change was used.

## Failure Evidence
- `falling_total_pc_long_1130` passed core and monkey, then failed WFA: stitched OOS net -2090.0, PF 0.8707482993197279, MAR -0.47633200537886, early_exit=True.
- `high_equity_pc_short_1030` passed core and monkey, then failed WFA: stitched OOS net -5335.0, PF 0.8344453064391001, MAR -0.5295516927947286, early_exit=True.
- `high_total_vs_equity_pc_short_1330` passed core (27/27) and failed monkey: median net -2035.0, profitable rate 0.19875, drawdown beat rate 0.702625.
- `low_equity_pc_long_1000` passed core (20/27) and failed monkey: median net -310.0, profitable rate 0.46825, drawdown beat rate 0.775375.
- `rising_total_pc_short_1200` passed core (21/27) and failed monkey: median net -2265.0, profitable rate 0.198375, drawdown beat rate 0.604375.

## Final Decision
FAIL. The edge did not satisfy the required robustness and walk-forward gates on NQ. No candidate strategy report was created.

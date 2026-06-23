# Methodology Audit - NQ Credit ETF Orderflow Risk-Appetite

Verdict: FAIL

## Edge And Source Contract
This campaign is a direct NQ port of the ES credit-ETF orderflow risk-appetite campaign. It uses NQ Sierra 1-minute RTH bars aggregated to 5-minute decision bars and a lagged daily HYG/LQD/SPY feature file keyed strictly before each NQ session date.

## Lookahead Controls
- An NQ session dated D uses only ETF observations strictly before D.
- Rolling HYG/LQD/SPY ranks are computed only from observations through the mapped prior ETF close.
- Intraday confirmation uses completed NQ 5-minute bars at 10:00, 10:30, 11:30, or 12:30 ET.
- Entry is next bar open or later; no same-bar signal-close entry is assumed.
- No intraday HYG/LQD prints, final NQ session high/low, final VWAP, future returns, or overnight exposure are used.

## Parameter Discipline
- Exactly five variants were authored before NQ testing.
- Each variant used two entry parameters, one stop parameter, and one take-profit parameter.
- Each variant tested 81 combinations, inside the declared 8-120 range.
- The ES rescue parameter space was adopted as the predeclared NQ baseline before any NQ PnL was inspected.
- No NQ rescue, date exclusion, threshold pruning, or post-result mechanics change was used.

## Failure Evidence
- `hyg_1d_strength_signed_long_1230` failed core (21/81); top net 580.0, PF 1.3109919571045576, trades 21, MAR 0.5408613804870601.
- `hyg_1d_weakness_signed_short_1230` failed core (22/81); top net 690.0, PF 1.0977337110481586, trades 79, MAR 0.3875606284858875.
- `hyg_1d_two_sided_signed_1230` failed core (7/81); top net 730.0, PF 1.0761606677099635, trades 111, MAR 0.38898613333040466.
- `hyg_3d_two_sided_signed_1230` failed core (27/81); top net 2320.0, PF 1.2479957242116515, trades 96, MAR 1.355412441287462.
- `hyg_5d_two_sided_signed_1230` failed core (35/81); top net 2705.0, PF 1.233390854184642, trades 145, MAR 1.4061338075199026.

## Final Decision
FAIL. The edge did not satisfy the required core profitability-density gate on NQ. No candidate strategy report was created.

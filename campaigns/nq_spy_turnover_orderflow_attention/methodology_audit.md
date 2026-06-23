# Methodology Audit - NQ SPY Turnover Orderflow Attention

Verdict: FAIL

## Edge And Source Contract
This campaign is a direct NQ port of the ES SPY turnover/orderflow attention edge. It uses NQ Sierra 1-minute RTH bars aggregated to 5-minute signals, local Yahoo SPY daily adjusted close/volume features mapped strictly before each NQ session date, and NQ aggregate signed-volume confirmation.

## Lookahead Controls
- SPY daily close/volume observations are merged with `allow_exact_matches=False`, so a session dated D only uses SPY data strictly before D.
- Rolling SPY attention ranks use only historical SPY rows through the mapped observation date.
- NQ price and signed-flow confirmation use completed 5-minute bars only; entry is next bar open or later.
- No same-day/future SPY close, final NQ high/low, final VWAP, or post-entry orderflow is used.

## Parameter Discipline
- Exactly five variants were authored before testing.
- Each variant used two entry parameters, one stop parameter, and one target parameter.
- Each variant tested 81 combinations, inside the declared 8-120 range.
- No rescue, date exclusion, or post-result mechanic change was used.

## Failure Evidence
- `spy_1d_absret_attention_continuation_1530` failed core: 6/81 profitable combinations; top net 545.0, top PF 1.0726666666666667.
- `spy_1d_volume_attention_continuation_1530` failed core: 13/81 profitable combinations; top net 550.0, top PF 1.073775989268947.
- `spy_3d_absret_attention_continuation_1530` passed core with 75/81 profitable combinations, then failed monkey: median net -1080.0, profitable rate 0.29575, max-drawdown beat rate 0.73975.
- `spy_3d_volume_attention_continuation_1530` failed core: 13/81 profitable combinations; top net 1590.0, top PF 1.2173615857826383.
- `spy_5d_volume_attention_continuation_1530` failed core: 49/81 profitable combinations; top net 3045.0, top PF 1.4087248322147652.

## Final Decision
FAIL. The edge did not satisfy the required robustness gates on NQ. No candidate strategy report was created.

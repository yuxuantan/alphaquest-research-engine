# ChartFanatics Post-Nikkei Strategy Gate

Date: 2026-07-01

Verdict: NEEDS MANUAL REVIEW

## Scope

After closing `nq_nikkei225_close_spillover`, I refreshed the ChartFanatics strategy index and spot-checked the remaining relevant ES/NQ futures pages.

## Sources Reviewed

- ChartFanatics strategy index: https://www.chartfanatics.com/strategies
- 80/20 Nasdaq Strategy: https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy
- Liquidity Strategy: https://www.chartfanatics.com/strategies/liquidity-strategy
- Measured Move Strategy: https://www.chartfanatics.com/strategies/measured-move-strategy
- Intraday Liquidity and Volatility Strategy: https://www.chartfanatics.com/strategies/intraday-liquidity-and-volatility-strategy

## Gate Results

- `80/20 Nasdaq Strategy` is an NQ day-trading strategy built around reactions at price endings in 20 and 80, plus discretionary structures such as Fork, H pattern, Cross-Section, and Repair. The economic edge maps to the already-authored `nq_20_80_price_ending_barrier` family, which has existing campaign/backtest artifacts and a failed verdict. Relaunching it with structural names would duplicate the same 20/80 price-ending edge.
- `Liquidity Strategy` is a liquidity-sweep/trap reversal model around respected highs and lows. This maps to already-tested stop-run reclaim, prior-session sweep, and rolling-range sweep-reversal families. Relaunching it would duplicate the liquidity-sweep/reclaim edge under different labels.
- `Measured Move Strategy` and `Intraday Liquidity and Volatility Strategy` remain covered by prior ChartFanatics measured-move, liquidity inversion/FVG, London/session-liquidity, and orderflow/liquidity-gate artifacts or require discretionary structure/depth inputs that are not available in the deterministic staged runner.

## Decision

No new ChartFanatics ES/NQ campaign launched from this refresh. The remaining pages are duplicate edge families, unavailable data lanes, or discretionary structure overlays rather than a clean, independent campaign edge.

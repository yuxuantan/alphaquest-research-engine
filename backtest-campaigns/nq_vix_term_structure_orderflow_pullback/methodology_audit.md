# nq_vix_term_structure_orderflow_pullback Methodology Audit

Verdict before staged PnL: PASS for source, duplicate, timing, and pre-PnL density gates. This is not evidence of profitability.

## Source and Edge

ChartFanatics lists VIX as a futures strategy theme, but this campaign does not rely on the practitioner page as standalone evidence. The tested edge is a local NQ transfer of the existing ES composite: prior-close Cboe VIX term-structure regime gates current-session NQ VWAP pullback/rejection entries with completed aggregate orderflow confirmation.

Primary evidence is Mixon (2007), Johnson (2017), Cont/Kukanov/Stoikov (2014), and official Cboe VIX maturity-index data. ChartFanatics is logged as the source that triggered this remaining-strategy review.

## Duplicate Check

This is not a duplicate of `nq_cboe_vix_term_structure_intraday`: that campaign used fixed-time VIX-term entries. Here, VIX term state only selects eligible sessions and direction; the actual entry requires same-session NQ VWAP pullback/rejection plus orderflow confirmation.

This is not a duplicate of `nq_vix_pressure_orderflow_confirmation`: that campaign used VIX level pressure and orderflow confirmation. This campaign uses VIX9D/VIX/VIX3M/VIX6M maturity ratios and VWAP pullback mechanics.

This is not a plain VWAP/orderflow duplicate because the prior-close term-structure state determines whether a session is eligible and whether long or short entries are allowed.

## Timing and Lookahead

- Cboe VIX maturity features come from `data/external/nq_cboe_vix_term_structure_features_20110103_20260612.csv`.
- Entry configs set `availability_market: NQ`; report fields state that the latest Cboe term-structure close must be strictly before `NQ session_date`.
- VWAP is computed from completed current-session RTH bars only.
- Entry signals are emitted only after a completed 1-minute bar; the engine fills on the next bar or later.
- Same-day Cboe closes, final session highs/lows, final session VWAP, future orderflow, and future returns are not used.
- Configs force same-day flattening and forbid overnight exposure through the shared prop-rule settings.

## Parameter Freeze

The NQ port uses the five original ES variant mechanics and grids, not ES rescue branches. Each variant has two entry tunables, one stop tunable, and one target tunable:

- `entry.params.term_rank_threshold`
- `entry.params.min_orderflow_imbalance`
- `sl.params.stop_offset_ticks`
- `tp.params.target_r_multiple`

Each variant has 81 declared combinations. No PnL was inspected before the density gate passed.

## Pre-PnL Density

The density audit is `research_artifacts/nq_vix_term_structure_orderflow_pullback_density_audit_20260701.md`.

Gate: at least one predeclared entry-grid row per variant must reach at least 50 signals/year on both the full configured NQ RTH subset and the canonical limited-core shortlist subset.

Result: PASS. Thirty-five of 45 entry rows passed, and all five variants had at least one passing row. The campaign may proceed to preflight and staged validation; density is not profitability evidence.

## Current Decision

Proceed to `research.preflight` and then staged validation with frozen mechanics and parameter space. If staged validation fails, reject unless the user explicitly authorizes a rescue.

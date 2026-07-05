# Methodology Audit - NQ Chart Fanatics Measured-Move Pullback

Verdict: FAIL as of 2026-06-30T12:17:35+08:00.

Source and duplicate review:
- Chart Fanatics Measured Move Trend Strategy was selected after the 80/20 Nasdaq strategy failed density and after rejecting overlapping VIX, SMT, value-profile, LVN, liquidity-sweep, and orderflow/trapped-trader ideas as duplicates of existing campaign families.
- This edge is distinct from prior pivot-bias, VWAP-pullback, range-compression, and daily-momentum campaigns because entry requires a completed measured pullback trigger break and the target is the signal-emitted measured projection.
- The Chart Fanatics measured-move rule is practitioner-originated. Lo/Mamaysky/Wang support objective local-extrema encoding, and Moskowitz/Ooi/Pedersen support futures trend persistence, but neither source validates this exact intraday NQ implementation.

No-lookahead and execution checks:
- Pivots are usable only after right-side confirmation bars complete.
- Entry signals use completed 5-minute bars and the engine fills no earlier than the next bar open.
- The measured target and sweep-extreme stop are computed from completed structure available at signal time.
- No final session high/low, final VWAP, future volume profile, or post-entry price path is used to define entry, stop, or target.

Pre-PnL density result:
- Detail CSV: `research_artifacts/nq_chartfanatics_measured_move_pullback_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_chartfanatics_measured_move_pullback_density_summary_20260630.csv`
- Only 21/45 entry-grid corners passed all required windows.
- Every variant failed because its minimum limited-core signal density was below 50 signals/year.
- Staged PnL testing was intentionally not run after this failure.

Variant density summary:
- `late_morning_15_30_two_sided_measured_continuation`: 6/9 corners pass; min full 89.77/y, min limited-core 41.50/y, min latest252 126.95/y.
- `late_morning_5_15_two_sided_measured_continuation`: 6/9 corners pass; min full 95.21/y, min limited-core 27.89/y, min latest252 147.78/y.
- `midday_5_15_two_sided_measured_continuation`: 6/9 corners pass; min full 97.87/y, min limited-core 19.45/y, min latest252 182.49/y.
- `morning_5_15_long_measured_breakout`: 3/9 corners pass; min full 47.15/y, min limited-core 14.92/y, min latest252 78.35/y.
- `morning_5_15_short_measured_breakdown`: 0/9 corners pass; min full 35.75/y, min limited-core 8.43/y, min latest252 49.59/y.

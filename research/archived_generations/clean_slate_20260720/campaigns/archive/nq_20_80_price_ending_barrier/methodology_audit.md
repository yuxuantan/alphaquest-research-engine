# Methodology Audit - NQ 20/80 Price-Ending Barrier

Verdict: FAIL as of 2026-06-30T12:25:00+08:00.

Source and duplicate review:
- Chart Fanatics 80/20 Nasdaq Strategy was selected after reviewing futures strategy pages and rejecting overlapping VIX, SMT, value-profile, LVN, liquidity-sweep, and orderflow/trapped-trader ideas as duplicates of existing campaign families.
- This edge is distinct from prior NQ/ES round-number campaigns because it uses fixed modulo-100 terminal endings 20 and 80, not 25/50/100-point handles.
- The practitioner 20/80 rule is not treated as academic evidence; Donaldson/Kim and Osler only support the broader price-barrier mechanism.

No-lookahead and execution checks:
- Levels are fixed before each bar by price arithmetic.
- Entry signals use completed 5-minute bars and the engine fills no earlier than the next bar open.
- Pivot structure uses right-side-confirmed completed pivots only.
- Fixed-dollar stops map to fixed NQ point risk through configured tick value; no future levels are used.

Pre-PnL density result:
- Detail CSV: `research_artifacts/nq_20_80_price_ending_barrier_density_audit_20260630.csv`
- Summary CSV: `research_artifacts/nq_20_80_price_ending_barrier_density_summary_20260630.csv`
- All five variants failed the density screen because 0/9 entry-grid corners per variant passed all windows.
- Staged PnL testing was intentionally not run after this failure.

Variant density summary:
- `late_morning_20_80_two_sided_reclaim_pivot`: min full 57.45/y, min limited-core 28.53/y, min latest252 88.27/y.
- `morning_20_80_downside_breakout_pivot_short`: min full 23.71/y, min limited-core 14.27/y, min latest252 25.79/y.
- `morning_20_80_resistance_reject_pivot_short`: min full 34.46/y, min limited-core 16.21/y, min latest252 34.71/y.
- `morning_20_80_support_reclaim_pivot_long`: min full 43.40/y, min limited-core 24.64/y, min latest252 56.53/y.
- `morning_20_80_upside_breakout_pivot_long`: min full 30.96/y, min limited-core 16.21/y, min latest252 48.60/y.

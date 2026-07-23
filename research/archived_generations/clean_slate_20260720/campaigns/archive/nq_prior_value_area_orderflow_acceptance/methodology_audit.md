# Methodology Audit - NQ Prior Value-Area Orderflow Acceptance

Verdict: FAIL.

Pre-test structure:
- One campaign expressed one bounded edge: prior-session approximate value-area acceptance with completed-bar aggregate orderflow confirmation on NQ.
- Exactly five variants were authored before NQ PnL testing, reusing ES mechanics only where locally portable.
- Entry used completed 5-minute bars with signal-on-close and next-bar-open execution; prior VAH, VAL, and POC were computed only from the previous completed RTH session.
- All variants used NQ point value 20.0, tick size 0.25, one tick slippage, commissions, intraday flattening, and configured prop rules.
- No rescue was authorized.

Pre-PnL density:
- `research_artifacts/nq_prior_value_area_orderflow_acceptance_density_audit_20260622.md` approved all five variants for limited-core and full-history signal density before PnL review.

Testing outcome:
- `afternoon_large20_two_sided_acceptance`: failed limited core grid gate: profitable_combos=0/81; top_net=-2535.0; top_pf=0.8588922905649875; top_trades=189; top_mar=-0.6040325565826263.
- `late_morning_large10_two_sided_acceptance`: failed limited core grid gate: profitable_combos=0/54; top_net=-510.0; top_pf=0.9590525893215576; top_trades=175; top_mar=-0.18678333219090318.
- `midday_signed_two_sided_acceptance`: failed limited core grid gate: profitable_combos=0/27; top_net=-855.0; top_pf=0.9338747099767981; top_trades=175; top_mar=-0.2004388476283451.
- `morning_signed_vah_acceptance_long`: failed limited core grid gate: profitable_combos=18/54; top_net=1145.0; top_pf=1.09439406430338; top_trades=125; top_mar=0.496150181908971.
- `morning_signed_val_acceptance_short`: failed limited core grid gate: profitable_combos=5/54; top_net=1320.0; top_pf=1.093319194061506; top_trades=116; top_mar=0.2956263856401449.

No rescue was authorized or attempted. No `candidate_strategy_report.md` was created.

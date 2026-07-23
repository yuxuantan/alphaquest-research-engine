# Methodology Audit: nq_day_of_week_seasonality

Verdict before PnL: APPROVE FOR DENSITY/PREFLIGHT ONLY.

This campaign is a direct NQ test of the day-of-week calendar anomaly, using the same five frozen mechanics as the existing ES campaign but with NQ contract specs and NQ data. ES failure is not treated as NQ evidence, but it raises prior skepticism.

## Edge Definition

The tradable state is the known weekday of the RTH session. Monday variants test negative weekend-effect continuation; Friday variants test positive pre-weekend drift; the paired variant tests both directions in one rule.

## No-Lookahead Contract

- Weekday is known before the RTH session opens.
- The signal only fires after the configured completed 5-minute bar.
- Entry occurs at the next bar open through the staged engine.
- No future session high, low, close, VWAP, volume profile, or final range is used.
- Stops, targets, costs, flatten time, and prop-rule checks are declared in each config.

## Duplicate Review

Checked against NQ RTH intraday risk premium, preholiday, turn-of-month, turn-of-year, quarterly expiration, VIX expiration, and FOMC pre-announcement campaigns. This campaign uses weekday as the primary state variable, not event or monthly calendar timing.

## Density Review

Pre-PnL density passed: 15/15 variant-window rows passed. The weakest single-weekday density was Monday with 42.304649 sessions per year in the limited-core proxy and 49 eligible sessions in the latest 252-session window. See `research_artifacts/nq_day_of_week_seasonality_density_audit_20260701.md`.

## Failure Rules

If density, preflight, limited core, monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS fails, the campaign is FAIL. No rescue is authorized.

## Final Staged Verdict

Verdict: FAIL.

All five frozen NQ weekday variants passed density and preflight, then failed `limited_core_grid_test` in `run1`. Each variant tested 9 official stop/target combinations. Profitable-iteration rates ranged from 0.0 to 0.4444444444444444, below the required 0.70 stability threshold. The paired Monday-short/Friday-long variant had 1/9 benchmark-passing cells, but isolated cells do not satisfy the staged stability gate. No variant reached limited monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

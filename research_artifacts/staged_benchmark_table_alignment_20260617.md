# Staged Benchmark Table Alignment - 2026-06-17

Decision: INFRASTRUCTURE FIX.

The staged campaign runner has been aligned to the user-provided benchmark table before any further ES strategy search.

## Applied Defaults

- Step 3 limited core grid: all parameter combinations on a seeded random 10% contiguous period, excluding the latest 10% holdout and the configured Covid range. Pass requires valid combo count, at least 70% profitable combinations, and zero Apex/flatten violations. The previous `number_passing_benchmark >= 1` gate was removed.
- Step 4 limited monkey: select the core-grid run closest to median net profit among all profitable limited-core rows. Pass requires core-vs-random beat rates of at least 90% for net profit and max drawdown.
- Step 5 WFA: first 90% of available data, unanchored 4-year IS / 1-year OOS / 1-year step. In-sample selection is max MAR from rows with trades/year > 50. Early exit triggers if the selected IS PF is below 1.0. Stitched OOS pass requires PF >= 1.2, MAR >= 0.4, trades/year >= 50, and zero Apex/flatten violations.
- Step 6 WFA OOS monkey: stitched WFA OOS trades, 80% net-profit beat rate and 80% max-drawdown beat rate.
- Step 7 WFA OOS Monte Carlo: stitched WFA OOS trades, default prop-style target is chance of $50,000 profit before $10,000 drawdown greater than 50%.
- Step 8 simulated incubation: latest 1-year OOS after prior 4-year IS, max MAR train selection from rows with trades/year > 50. OOS pass requires PF >= 1.0, MAR >= 1.0, trades/year >= 50, and zero Apex/flatten violations.
- Step 9 simulated incubation monkey: incubation OOS trades, 80% net-profit beat rate and 80% max-drawdown beat rate.
- Step 10 live acceptance: latest 0.5-year OOS after prior 2-year IS, max MAR train selection from rows with trades/year > 50. OOS pass requires PF >= 1.0, MAR >= 1.0, trades/year >= 50, and zero Apex/flatten violations.

## Notes

- Actual trade-path stress remains generated for monkey stages as diagnostic evidence for worse slippage, entry delay, missed trades, time-window trims, and same-bar stop/target ordering. It is not a default benchmark-table pass/fail gate.
- Apex/flatten violations remain hard fail-closed invariants even when not listed as performance benchmarks in the sheet.
- Existing historical run artifacts keep their original criteria. The corrected behavior applies to new staged runs and canonicalized run-level configs.
- WFA, simulated incubation, and acceptance train-selection now treat `trades/year > 50` as a hard eligibility rule. If all in-sample parameter rows are too sparse, WFA early-exits with `no_in_sample_rows_after_selection_filter`; incubation/acceptance train selection raises a stage error instead of silently selecting a sub-threshold row.

## Verification

- `python3 -m pytest tests/test_campaign_stages.py tests/test_monte_carlo.py -q` passed: 57 tests.
- `python3 -m pytest tests/test_wfa.py tests/test_monkey.py -q` passed: 25 tests.
- Combined focused regression pass passed: `python3 -m pytest tests/test_campaign_stages.py tests/test_monte_carlo.py tests/test_wfa.py tests/test_monkey.py -q` passed 82 tests.
- Engine/preflight focused regression pass passed: `python3 -m pytest tests/test_backtest_engine.py tests/test_preflight.py -q` passed 43 tests.
- Final combined focused regression pass passed: `python3 -m pytest tests/test_campaign_stages.py tests/test_monte_carlo.py tests/test_wfa.py tests/test_monkey.py tests/test_backtest_engine.py tests/test_preflight.py -q` passed 125 tests.
- Post-selection-filter enforcement regression pass: `python3 -m pytest tests/test_campaign_stages.py tests/test_wfa.py tests/test_monte_carlo.py tests/test_monkey.py tests/test_backtest_engine.py tests/test_preflight.py -q` passed 127 tests.
- `python3 -m py_compile src/propstack/research/campaign_stages.py src/propstack/research/wfa.py src/propstack/research/monkey.py src/propstack/research/monte_carlo.py src/propstack/prop/rules.py src/propstack/prop/simulator.py` passed.
- `python3 -m py_compile src/propstack/research/wfa.py src/propstack/research/campaign_stages.py src/propstack/prop/rules.py src/propstack/prop/simulator.py` passed after the strict-selection patch.
- Repo-wide `python3 -m research.preflight --skip-tests --json` was manually interrupted after about 90 seconds while scanning data duplicate checks. It did not produce a pass/fail result.

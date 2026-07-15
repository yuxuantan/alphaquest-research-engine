# Methodology Audit: NQ VPIN Toxicity Continuation

Decision: FAIL

## Pre-Test Controls

- Campaign has exactly five variants.
- Each variant has 54 combinations with 2 entry parameters, 1 stop parameter, and 1 target parameter.
- VPIN features are shifted prior-session ranks; current-session return is known only through the completed 13:25-13:30 ET bar.
- Pre-PnL density counted only entry-condition sessions. No PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected before freezing configs.

## Results

| Variant | Terminal stage | Core profitable combos | Benchmark combos | Best net | Best PF | Best MAR |
|---|---|---:|---:|---:|---:|---:|
| baseline_high_toxicity_positive_ret_long_1330 | limited_core_grid_test | 17/54 | 1 | 405.00 | 1.087 | 0.269 |
| drawdown_rank_confirmed_long_1330 | limited_core_grid_test | 19/54 | 2 | 630.00 | 1.125 | 0.465 |
| fast_bucket_toxicity_long_1330 | limited_core_grid_test | 32/54 | 6 | 1265.00 | 1.248 | 1.197 |
| medium_bucket_toxicity_long_1330 | limited_core_grid_test | 14/54 | 1 | 590.00 | 1.151 | 0.461 |
| slow_bucket_toxicity_long_1330 | walk_forward_analysis | 43/54 | 8 | 1525.00 | 1.309 | 0.689 |

## Verdict

FAIL. The slow-bucket NQ VPIN variant was the only one to reach WFA, and it failed the first WFA train-window early-exit criterion. No variant reached Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No rescue was run because no rescue was explicitly authorized.

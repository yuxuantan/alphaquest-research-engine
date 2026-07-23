# NQ Taiwan Semiconductor Spillover Methodology Audit

Date: 2026-07-01

Final verdict: FAIL

## Edge Definition

One campaign equals one edge: same-date Taiwan cash-market and local TSMC state, available before NQ RTH, as a semiconductor supply-chain spillover signal for NQ. The five variants express the same edge through broad TAIEX strength/weakness, local TSMC relative strength/weakness, and Taiwan volatility stress.

## Leakage Controls

- Taiwan observations are joined as-of the NQ session date and must be no older than three calendar days.
- Taiwan cash trading closes before all configured NQ decision times.
- Rolling ranks use only completed Taiwan daily observations.
- NQ signals use a completed 1-minute RTH bar and request next-bar execution.
- The strategy uses same-day flattening and no overnight exposure.

## Duplicate Check

This is not the already-rejected Nikkei 225 close spillover, U.S. SMH/SOXX semiconductor leadership, China technology ETF sentiment, Europe close spillover, or any ChartFanatics orderflow/AOI campaign. It is still economically adjacent to semiconductor leadership, so the rejection should remain attached to future duplicate checks.

## Pre-PnL Density

Density artifact: `research_artifacts/nq_taiwan_semiconductor_spillover_density_audit_20260701.md`

Result: PASS, 45/45 declared density rows passed before any NQ PnL was inspected.

## Staged Validation

All five variants failed limited_core_grid_test. Four variants had zero profitable combinations; the best breadth was twii_1d_strength_long_1000 with profitable-combination rate 0.5185185185185185 (14/27), below the required 0.70 gate, and only 7/27 benchmark-passing combinations. No branch reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Profitable Rate | Benchmark Passing | Top Net | Top PF | Top Trades |
|---|---|---:|---:|---:|---:|---:|
| twii_1d_strength_long_1000 | limited_core_grid_test | 0.518519 | 7/27 | 2530.0 | 1.133403638281044 | 143 |
| twii_1d_weakness_short_1000 | limited_core_grid_test | 0.000000 | 0/27 | -265.0 | 0.9791502753737215 | 129 |
| tsmc_1d_relative_strength_long_1030 | limited_core_grid_test | 0.000000 | 0/27 | -1740.0 | 0.8950226244343892 | 132 |
| tsmc_3d_relative_weakness_short_1030 | limited_core_grid_test | 0.000000 | 0/27 | -945.0 | 0.9536764705882353 | 163 |
| taiwan_1d_volatility_short_1130 | limited_core_grid_test | 0.000000 | 0/27 | -365.0 | 0.9805747738158594 | 139 |

## Downstream Gates

Limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, and candidate reporting were not reached because every variant failed limited_core_grid_test.

## Rescue Policy

No rescue was authorized. The campaign is closed as FAIL.

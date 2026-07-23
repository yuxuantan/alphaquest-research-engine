# Methodology Audit: es_aoi_vap_acceptance_retest

Decision: FAIL

Date: 2026-06-22

## Pre-Test Contract

- Edge: accepted retests of market-generated AOIs near frozen prior true VAP, confirmed by completed-bar same-direction orderflow and footprint imbalance.
- Variants: 8 predeclared variants in `campaigns/es_aoi_vap_acceptance_retest/campaign.yaml`; expansion rationale is documented before testing.
- Parameter space per variant: 81 combinations; 2 entry parameters, 1 stop parameter, 1 take-profit parameter.
- Data: completed RTH 1-minute Sierra footprint/VAP/overnight-AOI cache.
- Entry timing: completed-bar signal, next-bar intended entry timestamp.

## Results

All variants failed the first staged gate, `limited_core_grid_test`.

- Profitable-combination rate: 0/81 for every variant.
- Benchmark-passing combinations: 0 for every variant.
- Apex rule violating iterations: 0 for every variant.
- Best top-row by net profit: `overnight_high_vap_acceptance_long_1500`, net `-445.0`, PF `0.875`, trades/year `29.4`.

## Rejection Reason

The edge was directionally negative or too sparse across all market-generated AOI variants under the frozen parameter space. Because the first gate failed with zero profitable combinations, no WFA, Monte Carlo, simulated incubation, acceptance OOS, rescue, or candidate report is justified.

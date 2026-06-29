# ES Opening VAP Large-200 Acceptance Methodology Audit
Decision: FAIL
Verdict date: 2026-06-29

## Scope
Official staged validation used five predeclared variants from the local corrected Sierra `_ny` opening VAP large-200 cache. The sixth dense acceptance candidate, `ovap60_large_lvn_accept_1500`, was archived before official testing because it had the lowest strict pre-PnL density; its generated artifacts remain historical/non-promotional.

## Validation
- Focused tests: `PYTHONPATH=src python3 -m pytest -q tests/test_opening_vap_large_record_reaction.py tests/test_sierra_trade_orderflow_cache.py tests/test_footprint_features.py tests/test_campaign_stages.py` passed 66 tests.
- Preflight: `PYTHONPATH=src python3 -m research.preflight --skip-tests --config <five official configs>` passed for 5 configs.
- Staged command per variant: `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config <config> --skip-validation --fast-runtime-defaults`.
- No `[Errno 1] Operation not permitted` runtime failure occurred in the five official runs.

## Results
| Variant | Stage | Profitable / Total | Top net | Top PF | Top MAR | Top trades/year | Apex violations | Failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `ovap30_large_value_accept_1500` | limited_core_grid_test | 0/54 | -7077.5 | 0.747 | -0.593 | 241.66 | 0 | min_total_net_profit;max_consecutive_losses |
| `ovap30_large_poc_accept_1500` | limited_core_grid_test | 0/54 | -9225.0 | 0.680 | -0.631 | 243.04 | 0 | min_total_net_profit;max_consecutive_losses |
| `ovap30_large_lvn_accept_1500` | limited_core_grid_test | 0/54 | -8187.5 | 0.738 | -0.632 | 236.13 | 0 | min_total_net_profit;max_consecutive_losses |
| `ovap60_large_value_accept_1500` | limited_core_grid_test | 0/54 | -11695.0 | 0.641 | -0.690 | 238.86 | 0 | min_total_net_profit;max_consecutive_losses |
| `ovap60_large_poc_accept_1500` | limited_core_grid_test | 0/54 | -9850.0 | 0.698 | -0.680 | 242.96 | 0 | min_total_net_profit;max_consecutive_losses |

All five official variants failed the limited-core profitable-iteration gate with 0/54 profitable combinations. Monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, and acceptance OOS were correctly skipped after first-stage failure. No candidate strategy report was created.

## Data And Lookahead Controls
- Signals used completed-bar opening VAP, same-side large-200 aggregate proxy, and completed footprint/orderflow fields from `data/cache/orderflow/es_sierra_footprint_opening_vap_large200_1m_20120103_20260609_rth_ny.parquet`.
- Opening30 levels are unavailable before 10:00 ET and opening60 levels before 10:30 ET; entries occur after the completed signal bar.
- ES costs, tick value, prop-rule flattening, and stop/target fill assumptions were unchanged from the source configs.

## Final Decision
FAIL. The local five-variant campaign is exhausted. Per the search plan, do not relabel local near-misses or start external data work without explicit approval.

# ES Opening VAP Absorption Reaction

Verdict: FAIL.

All eight predeclared opening VAP absorption/reaction variants failed limited_core_grid_test. Across 432 core combinations, only 4 were profitable and 0 passed benchmarks; no branch reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. Best top row was ovap60_poc_reclaim_1500: net 302.5, PF 1.0438564697354114, MAR 0.09474234839420437, failure max_consecutive_losses;max_best_day_concentration.

All runs used the predeclared 54-combination grid: `entry.params.min_probe_ticks` [0, 1], `entry.params.min_orderflow_imbalance` [0.0, 0.01, 0.03], `sl.params.stop_offset_ticks` [1, 2, 4], and `tp.params.target_r_multiple` [1.25, 2.0, 3.0]. No rescue was run.

| variant | profitable/total | benchmark pass | top net | top PF | top MAR | top trades/year | top failure |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ovap60_poc_reclaim_1500 | 4/54 | 0 | 302.5 | 1.0438564697354114 | 0.09474234839420437 | 73.16831781551517 | max_consecutive_losses;max_best_day_concentration |
| ovap30_value_trap_1500 | 0/54 | 0 | -192.5 | 0.9823475469967905 | -0.04625809087627423 | 95.36615111013965 | min_total_net_profit;max_consecutive_losses |
| ovap60_lvn_trap_1500 | 0/54 | 0 | -980.0 | 0.8677462887989204 | -0.3967140571748509 | 67.32855426389995 | min_total_net_profit |
| ovap30_lvn_trap_1500 | 0/54 | 0 | -1282.5 | 0.8594135379556043 | -0.29866372891121257 | 78.72701933042858 | min_total_net_profit |
| ovap30_poc_reclaim_1500 | 0/54 | 0 | -2195.0 | 0.7824578790882062 | -0.5618220495997207 | 82.9525540528681 | min_total_net_profit;max_consecutive_losses |
| ovap60_value_trap_1500 | 0/54 | 0 | -2947.5 | 0.7144587067086462 | -0.48553250504452833 | 83.85526015159923 | min_total_net_profit;max_consecutive_losses |
| ovap60_value_acceptance_1500 | 0/54 | 0 | -8177.5 | 0.6772570300937346 | -0.6458759972853161 | 242.44347749789603 | min_total_net_profit;max_consecutive_losses |
| ovap30_value_acceptance_1500 | 0/54 | 0 | -9320.0 | 0.7466358570069321 | -0.601853789826882 | 243.08504867038465 | min_total_net_profit;max_consecutive_losses |

Detail CSV: `backtest-campaigns/es_opening_vap_absorption_reaction/campaign_variant_results.csv`

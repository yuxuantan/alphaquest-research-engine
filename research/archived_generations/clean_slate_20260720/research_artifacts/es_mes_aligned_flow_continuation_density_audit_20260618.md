# ES/MES Aligned-Flow Continuation Density Audit

Date: 2026-06-18

Purpose: pre-PnL density and mechanics audit before staged testing.

Data: `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`.

Limited-core window resolved from the runner's default shortlist rule:

- mode: `random_fraction`
- fraction: `0.10`
- seed: `31`
- avoid last fraction: `0.10`
- avoid range: `2020-02-01` through `2021-06-30`
- resolved period: `2021-07-13` through `2022-03-28`

Eligible mechanics:

- The signal uses completed ES return ticks and completed MES imbalance ending at the signal bar close.
- The signal is a confirmation/continuation setup, not a MES divergence fade or MES crowding fade.
- Strict corners for the declared grids remain plausibly above 50 trades/year in the key testing windows, except intentionally rejected extreme signed-flow imbalance thresholds that were not included in the configs.

Density summary for declared strict corners:

| Variant | Strict corner checked | Limited random 10% signals/year | Full signals/year | WFA first 90% signals/year | Latest 1y signals/year |
| --- | --- | ---: | ---: | ---: | ---: |
| `morning15_mes_signed_1030` | `min_es_return_ticks=8`, `min_mes_flow_imbalance=0.02` | 115.64 | 144.86 | 145.50 | 145.70 |
| `late_morning30_mes_signed_1130` | `min_es_return_ticks=8`, `min_mes_flow_imbalance=0.02` | 115.64 | 135.28 | 136.11 | 135.72 |
| `midday30_mes_large10_1230` | `min_es_return_ticks=8`, `min_mes_flow_imbalance=0.05` | 80.38 | 100.61 | 99.77 | 101.79 |
| `afternoon60_mes_signed_1400` | `min_es_return_ticks=8`, `min_mes_flow_imbalance=0.02` | 132.56 | 123.02 | 124.67 | 123.75 |
| `late_day60_mes_large20_1500` | `min_es_return_ticks=8`, `min_mes_flow_imbalance=0.10` | 84.61 | 92.58 | 89.90 | 112.77 |

Rejected before testing:

- Signed-flow thresholds at `0.10` were rejected for signed MES variants because the density audit showed they are sparse in several windows and would not represent the edge robustly.
- Additional time-of-day variants were not added because the campaign must contain exactly five variants.

Pre-test decision: approve the five declared variants for staged testing.

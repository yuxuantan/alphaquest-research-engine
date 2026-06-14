# ES/MES Flow-Divergence Validation Protocol

Date: 2026-06-14

## Status

This is the current best independent ES mean-reversion lead, but it is not live
eligible yet.

Candidate:

- Campaign: `mes_es_flow_divergence_reversion`
- Primary variant: `afternoon_mes_large20_buy_pressure_short`
- Config:
  `configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/afternoon_mes_large20_buy_pressure_short.yaml`
- Predeclared 2020-start validation config:
  `configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start.yaml`
- Current one-year report:
  `data/reports/campaigns/mes_es_flow_divergence_reversion/ES/es_mes_trade_orderflow_1m_20250610_20260608/1m/afternoon_mes_large20_buy_pressure_short/campaign_tests`

## Edge Thesis

Trade ES short at 14:00 ET when completed 13:55-13:59 MES large-trade buy
pressure is strong, but ES has not confirmed with more than the configured
five-minute price cap. The hypothesis is temporary liquidity demand in the
smaller-notional contract, expressed as ES mean reversion after MES flow
diverges from ES.

This is distinct from the accepted ES signed-flow trend-following campaigns:
MES is only a state variable, ES is the traded instrument, and the direction is
contrarian to the smaller-contract pressure.

Academic support:

- Kaniel, Saar, and Titman (2008), "Individual Investor Trading and Stock
  Returns", Journal of Finance. Individual-investor flow can act as
  short-horizon liquidity provision and has return information.
- Barber, Odean, and Zhu (2009), "Do Retail Trades Move Markets?", Review of
  Financial Studies. Small-trade order imbalance is informative about retail-like
  coordinated flow and later returns.
- Hasbrouck (1995), "One Security, Many Markets", Journal of Finance. Closely
  linked markets can differ in price-discovery contribution, leaving room for
  transitory divergence.

Evidence directness is moderate. MES is not an account-classified retail feed,
but it is a smaller-notional futures contract with true aggressor-side prints,
so it is a better proxy than OHLCV or price-only sweep labels.

## Current Evidence

Existing local data covers only 2025-06-10 through 2026-06-08 after aligning ES
and MES trade-side bars.

The primary variant passed the first two staged gates on that limited sample:

- Limited core: 100/100 profitable iterations, zero Apex violations.
- Top limited-core row: 69 trades, net `$14,248.75`, PF `2.238`, MAR `6.207`,
  expectancy `0.240R`.
- Limited monkey: net-profit beat rate `97.6%`, max-drawdown beat rate `98.8%`.
- WFA failed formal density/window gates only: 8 windows versus required 10 and
  stitched OOS 31 trades versus required 500. Stitched OOS economics were strong:
  net `$11,007.50`, PF `3.275`, MAR `8.659`, expectancy `0.391R`, win rate
  `67.7%`, zero Apex violations, and 75% profitable OOS windows.

The one-year result is enough to justify a longer-data validation run. It is not
enough to trade.

Additional engine-timing robustness audit:

- Scratch script:
  `/private/tmp/es_mes_flow_divergence_primary_robustness.py`.
- Output files:
  `/private/tmp/es_mes_flow_divergence_primary_robustness_grid.csv`,
  `/private/tmp/es_mes_flow_divergence_primary_robustness_trades.csv`, and
  `/private/tmp/es_mes_flow_divergence_primary_robustness_summary.json`.
- The scratch path used the same signal timing as the engine: completed 13:59
  bar, 14:00 entry, 15:30 bar close for the 15:31 flatten, 1-tick entry/exit
  slippage, and `$2.50` commission per side.
- The primary parameter row exactly reproduced the staged core-grid metrics:
  50 trades, net `$11,437.50`, PF `2.4659`, average `0.195R`, max drawdown
  `$2,275`, with 44 flat exits, 5 targets, and 1 stop.
- The exact row remained profitable under extra round-turn costs: PF `2.216`
  at +`$25` and PF `1.996` at +`$50`. It also kept worst leave-one-month-out PF
  `2.026`, excluding March 2026.
- The caveat is month breadth: the exact row had only `58.3%` positive months,
  so it did not pass the stricter scratch `supportive_shape` flag.
- Two nearby stricter rows did pass the scratch split/month/cost flag:
  threshold `0.20`, stop `0.0025`, target `1.0R` and threshold `0.175`, stop
  `0.0025`, target `1.0R`. Both had 45-47 trades, positive 2025/Q1/Q2 PF,
  `75%` positive months, +`$50` cost-stress PF above `1.83`, and worst
  leave-one-month-out PF above `2.04`.

Interpretation: the one-year evidence is not a single exact stop/target
accident, but it is still too short and too month-concentrated to accept. This
audit supports buying or otherwise obtaining longer ES+MES `trades` history; it
does not support live trading from the one-year sample.

## Required Data

Do not download paid data without explicit approval.

If approved, obtain only Databento `trades` for:

- Dataset: `GLBX.MDP3`
- Symbols: `ES.FUT` and `MES.FUT`
- `stype_in=parent`
- Schema: `trades`
- Session: RTH bars, 09:30-16:00 America/New_York, completed through 15:59
- Range: 2020-01-01 through 2026-06-09, or the same end date used for both ES
  and MES

Dry-run estimate already logged:

- Durable manifest:
  `research_artifacts/databento_es_mes_trades_20200101_20260609_cost_manifest_20260614.json`.
- Scope: 2020-01-01 through 2026-06-09 RTH history, 1,680 requested sessions,
  24 sampled sessions per symbol.
- Estimated sampled cost: `$554.49` for ES and `$394.85` for MES, combined
  `$949.34`.
- No paid files were downloaded during that estimate.
- Treat this as a metadata estimate only; rerun a final cost check immediately
  before any approved download.

## Predeclared Build Commands

After approved data exists locally, build ES and MES trade-orderflow caches
separately:

```bash
PYTHONPATH=src python3 -m propstack.build_trade_orderflow_cache \
  --raw-dir data/raw/ES/databento-es-trades-2020-2026 \
  --out-csv data/cache/orderflow/es_trade_orderflow_1m_20200101_20260609.csv \
  --monthly-cache-dir data/cache/orderflow/es_trade_orderflow_monthly_20200101_20260609 \
  --root-symbol ES \
  --contract-symbol-regex '^ES[HMUZ][0-9]$'
```

```bash
PYTHONPATH=src python3 -m propstack.build_trade_orderflow_cache \
  --raw-dir data/raw/MES/databento-mes-trades-2020-2026 \
  --out-csv data/cache/orderflow/mes_trade_orderflow_1m_20200101_20260609.csv \
  --monthly-cache-dir data/cache/orderflow/mes_trade_orderflow_monthly_20200101_20260609 \
  --root-symbol MES \
  --contract-symbol-regex '^MES[HMUZ][0-9]$'
```

Then build the merged ES/MES feature cache:

```bash
PYTHONPATH=src python3 -m propstack.build_es_mes_flow_divergence_cache \
  --es-csv data/cache/orderflow/es_trade_orderflow_1m_20200101_20260609.csv \
  --mes-csv data/cache/orderflow/mes_trade_orderflow_1m_20200101_20260609.csv \
  --out-csv data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv
```

The predeclared validation sibling is already present and must only be run after
the approved cache exists:

```bash
PYTHONPATH=src python3 -m propstack.run_campaign_stages \
  --config configs/campaigns/mes_es_flow_divergence_reversion/variants/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start.yaml \
  --skip-validation
```

It encodes the 2020-start raw CSV, 2020-2024 pre-incubation window,
2025-2026 simulated incubation window, 24-month train / 3-month test / 3-month
step WFA, and the standard 500-WFA-trade live-candidate gate. If the longer MES
history still produces fewer than 500 stitched WFA OOS trades, this branch
cannot be called a full-stage live candidate under the current policy.

## Predeclared Validation Rules

The first rerun must be `afternoon_mes_large20_buy_pressure_short`.

Do not lower gates after seeing the longer-data result. If the standard staged
pipeline passes unchanged, this branch can be treated as the next independent ES
candidate.

Hard requirements:

- No future bars in features; signal uses only completed 13:55-13:59 bars before
  the 14:00 entry.
- Limited core must pass profitable-iteration rate and zero Apex violations.
- Limited monkey must pass both net-profit and max-drawdown beat-rate gates.
- WFA must not early-exit.
- WFA must have at least 10 OOS windows.
- WFA stitched OOS must keep PF at or above `1.5`, expectancy at or above
  `0.20R`, positive-window rate at or above `70%`, and zero Apex violations.
- If WFA total OOS trades remain below the default 500 because MES history starts
  in 2020, the branch cannot be called a standard full-stage live candidate. It
  can only be kept as an incubation/paper candidate unless the user explicitly
  approves a separate short-history acceptance policy before the rerun.
- WFA OOS monkey, Monte Carlo, simulated incubation, and incubation monkey must
  all pass before any live-trading tracker is created.

Failure conditions:

- Any early WFA train-window failure.
- WFA PF below `1.5` or expectancy below `0.20R`.
- 2020-start results depend on only one year, one quarter, or one month.
- 2025-2026 incubation weakens materially versus the one-year screen.
- A broader public-data source or quote/depth sweep variant is substituted after
  seeing longer ES/MES results.

## Branch Priority

1. ES/MES micro-flow divergence is the first longer-data candidate because it is
   independent, mean-reverting, already packaged in the repo, and has the best
   limited-sample staged evidence.
   `midday_es_mes_price_dislocation_fade` is a secondary rejected probe: it had
   attractive top-row one-year economics but failed limited core with only 40%
   profitable grid iterations, so it must not replace the primary 14:00 flow
   branch in the first longer-history rerun.
2. ES quote/depth liquidity sweep remains the only liquidity-sweep branch worth
   testing, but only as a bounded one-year `tbbo` pilot after explicit approval.
   Do not rerun price-only or trade-side-only sweep/reclaim mechanics.
3. No further no-cost public macro/news/factor/calendar screens should be
   treated as higher priority unless a genuinely new point-in-time source is
   introduced. The current ledger already rejects the common public families.

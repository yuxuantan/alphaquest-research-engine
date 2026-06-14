# ES Quote-Liquidity Sweep Pilot Protocol - 2026-06-14

## Status

Data-gated pilot. No quote/depth files have been downloaded, and no strategy is
accepted or live eligible from this branch.

## Objective

Test the only liquidity-sweep version still distinct from rejected local
price-only and trade-side-only sweep/reclaim branches: ES failed liquidity demand
confirmed by top-of-book refill after a known-level sweep.

## Academic Thesis

- Cont, Kukanov, and Stoikov, "The Price Impact of Order Book Events":
  top-of-book order-flow imbalance and depth are directly tied to short-horizon
  price impact.
- Hendershott and Menkveld, "Price Pressures": liquidity-demand shocks can
  create temporary price pressure that later mean-reverts.
- Chordia, Roll, and Subrahmanyam, "Order Imbalance, Liquidity, and Market
  Returns": order imbalance is a liquidity and return-state variable.

Translation to ES:

- A downside sweep is not enough. A long setup must sweep a known downside level,
  reclaim quickly, show bid-side refill, keep spreads contained, and optionally
  show recent aggressive selling that failed to continue.
- An upside sweep is the mirror image: sweep above a known upside level, reclaim
  quickly, show ask-side refill, contained spread, and optionally failed
  aggressive buying.

## Current Implementation

Added reusable TBBO plumbing:

- `src/propstack/data/tbbo_liquidity.py`
- `src/propstack/build_tbbo_liquidity_cache.py`
- `src/propstack/strategy_modules/entry/quote_liquidity_sweep_reversion.py`
- `tests/test_quote_liquidity_sweep_reversion.py`

Added data-gated pilot config:

- `configs/campaigns/quote_liquidity_sweep_reversion/campaign.yaml`
- `configs/campaigns/quote_liquidity_sweep_reversion/variants/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim.yaml`

The config expects the cache:

`data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`

Build command after an approved TBBO download:

```bash
PYTHONPATH=src python3 -m propstack.build_tbbo_liquidity_cache \
  --raw-dir data/raw/ES/databento-es-tbbo-20250609-20260609 \
  --out-csv data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv \
  --monthly-cache-dir data/cache/orderflow/es_tbbo_liquidity_monthly \
  --windows 3,5 \
  --tick-size 0.25
```

Pilot run command after the cache exists:

```bash
PYTHONPATH=src python3 -m propstack.run_campaign_stages \
  --config configs/campaigns/quote_liquidity_sweep_reversion/variants/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim.yaml \
  --skip-validation
```

## Pilot Mechanics

Primary variant:

`tbbo_failed_pdh_pdl_or30_sweep_reclaim`

Levels:

- Previous RTH low: long only after a downside sweep and reclaim.
- Previous RTH high: short only after an upside sweep and reclaim.
- 30-minute opening-range low: long only after a downside sweep and reclaim.
- 30-minute opening-range high: short only after an upside sweep and reclaim.

Default signal filters:

- Minimum sweep: `2` ES ticks.
- Reclaim window: `3` completed 1-minute bars.
- Quote window: `3` completed 1-minute bars.
- Refill ratio: bid refill for longs or ask refill for shorts must be at least
  `2.0`.
- Quote imbalance: at reclaim close, top-of-book imbalance must support the
  reversal direction by at least `0.20`.
- Spread sanity: rolling max spread must be no more than `2.0` ticks.
- Failed demand: require recent aggressive selling for longs or aggressive
  buying for shorts with magnitude at least `0.20`.
- Stop: one tick beyond the sweep extreme.
- Target: signal-level fixed R, default `1.5R`.
- Flatten: `15:45 ET`.
- Max trades: one per session.

## Data-Gate Policy

Do not run a paid download from this protocol without a fresh metadata/cost
check and explicit approval.

2026-06-14 metadata-only refresh:

- Manifest:
  `research_artifacts/databento_es_tbbo_20250609_20260609_cost_manifest_20260614.json`.
- Scope: `GLBX.MDP3`, `ES.FUT`, RTH windows, `2025-06-09` through
  `2026-06-09`, `stype_in=parent`.
- Availability: `262` RTH sessions checked, `262` available.
- `tbbo` 8-session sample: estimated one-year RTH cost `$14.88`, estimated
  billable size `8.08 GB`, with only `1/8` sampled sessions returning nonzero
  cost despite all sampled sessions returning nonzero billable size.
- `mbp-1` 8-session comparison: estimated one-year RTH cost `$19.81`,
  estimated billable size `159.85 GB`, with the same nonzero-size/mostly-zero
  cost pattern.
- Interpretation: use `tbbo` first because it is far smaller than `mbp-1` for
  this pilot. Treat the sampled cost as a metadata estimate, not spend approval;
  rerun a final cost check immediately before any download.

Recommended first data pull if approved:

- Dataset: `GLBX.MDP3`
- Symbol: `ES.FUT`
- Schema: `tbbo`
- Scope: RTH only, `2025-06-09` through `2026-06-09`
- Output: one-year pilot only

Do not start with full-history depth, `mbo`, or `mbp-10`. Escalate beyond `tbbo`
only if the one-year pilot produces simple split-stable candidates whose failure
modes clearly require deeper book reconstruction.

## Promotion Rules

This branch is not accepted if it only passes a one-year pilot. Promotion path:

1. One-year TBBO pilot must produce simple candidates with positive train,
   validation, and holdout behavior after current ES costs.
2. If the pilot passes, predeclare the full-history or expanded-history
   validation plan before buying more data.
3. Full acceptance still requires the repo's staged validation chain:
   limited core grid, limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated
   incubation, and Apex-rule audit.
4. If the one-year TBBO pilot fails, reject this branch as quote-confirmed
   liquidity sweep and do not rerun price-only, trade-side-only, ICT/SMC/FVG, or
   plain PDH/PDL/opening-range sweep variants.

# Footprint Absorption-Initiation Edge Feasibility

Date: 2026-06-18

## User Concept

Use footprint-chart absorption and initiation as confluence for price-action areas of interest:

- Sell pressure absorbed: a bar closes above a bid-side imbalance level, where bid volume at a price is materially larger than diagonal ask volume.
- Buy pressure absorbed: a bar closes below an ask-side imbalance level, where ask volume at a price is materially larger than diagonal bid volume.
- CVD-style absorption: materially more sell volume below price without downside continuation, or materially more buy volume above price without upside continuation.
- Context examples: area of interest, break-and-retest, liquidity sweep.

## Local Data Check

The canonical ES cache currently has bar-level aggregate columns:

- `buy_volume`
- `sell_volume`
- `signed_volume`
- `large10_signed_volume`
- `large20_signed_volume`
- `large10_volume`
- `large20_volume`

That supports CVD/aggregate absorption approximations, but not true footprint diagonal imbalance.

The local raw Sierra ES parquet records include:

- `scid_datetime_us`
- `close`
- `volume`
- `bid_volume`
- `ask_volume`
- `num_trades`

This may support a local no-cost footprint-derived feature build by grouping records by minute and price, but that data contract still needs validation. The important question is whether each record is granular enough to represent volume at traded price rather than a coarser bar interval. Do not treat diagonal footprint imbalance as validated until this is tested.

## Eligible Campaign Shape

This is eligible only if framed as a distinct edge:

> Footprint or CVD absorption at objective price-action areas followed by initiation in the absorbed direction.

It should not be relaunched as another generic bar-level absorption campaign, because several active aggregate-orderflow absorption variants already failed. The differentiator must be the footprint-derived imbalance level or a clearly specified CVD absorption-initiation sequence.

## Proposed Mechanics

Long absorption-initiation:

1. Price reaches an objective AOI using only already-known levels.
2. A completed bar contains a sell-pressure footprint imbalance below or inside the bar.
3. The bar closes above that sell-imbalance price, indicating selling did not move price lower.
4. Initiation is confirmed by a completed close above the absorption bar high, or by a same-direction completed CVD/orderflow turn.
5. Entry occurs no earlier than the next bar open.
6. Stop goes below the absorption bar low or liquidity-sweep low.
7. Target uses fixed R or nearest pre-known level, not future VWAP/session range/profile.

Short absorption-initiation is symmetric.

## Feature Definitions To Validate

Potential footprint feature definitions from local raw Sierra records:

- `max_sell_imbalance_price`: price where `bid_volume_at_price >= ratio * ask_volume_at_price_plus_tick`.
- `max_buy_imbalance_price`: price where `ask_volume_at_price >= ratio * bid_volume_at_price_minus_tick`.
- `sell_imbalance_below_close`: true when a sell imbalance exists below the close.
- `buy_imbalance_above_close`: true when a buy imbalance exists above the close.
- `absorption_bar_long`: sell imbalance exists and the bar closes above the imbalance price.
- `absorption_bar_short`: buy imbalance exists and the bar closes below the imbalance price.
- `cvd_absorption_long`: negative signed volume with close in upper range or above an AOI reclaim.
- `cvd_absorption_short`: positive signed volume with close in lower range or below an AOI rejection.

The imbalance ratio should be fixed or have one entry tunable, for example `[3, 4, 5]`, with a fixed minimum at-price volume floor or one additional entry tunable if the AOI type is fixed.

## Candidate Variant Family

Exactly five variants, if the feature gate passes:

1. Prior RTH high/low sweep plus footprint absorption-initiation.
2. Opening range boundary break-and-retest plus footprint absorption-initiation.
3. Rolling intraday liquidity sweep plus footprint absorption-initiation.
4. Round-number rejection plus footprint absorption-initiation.
5. EMA/VWAP pullback area plus footprint absorption-initiation, only if it does not duplicate an active failed VWAP/EMA campaign mechanic.

The variants must still be one edge: footprint absorption-initiation at objective AOIs. AOI choice is the context, not a separate independently tuned edge.

## Gate Before Any PnL

Before creating a campaign:

1. Validate raw Sierra record granularity against a small hand-audited sample.
2. Build deterministic 1-minute or 5-minute footprint feature cache from local raw files only.
3. Add data-quality tests for price tick alignment, bid/ask volume conservation, timezone/session handling, and roll boundaries.
4. Run a pre-PnL density audit requiring plausible `>= 50` signals/year before staged testing.

No paid data download is allowed for this branch without explicit user permission.

## 2026-06-18 Local Feature-Build Update

Status: local 1-minute feature cache built and validated for research gating.

New code/tests:

- `src/propstack/data/footprint.py`
- `tools/build_sierra_footprint_feature_cache.py`
- `tests/test_footprint_features.py`
- `tests/test_sierra_trade_orderflow_cache.py`

Validation commands/results:

- `PYTHONPATH=src:. python3 -m pytest tests/test_footprint_features.py tests/test_sierra_trade_orderflow_cache.py -q`: 8 passed.
- Full local cache build command:
  `PYTHONPATH=src:. python3 tools/build_sierra_footprint_feature_cache.py --output-parquet data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet --report-json data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.validation.json --batch-size 2000000`

Output cache:

- `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`
- `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.validation.json`

Build/report metrics:

- Rows: `1489410`
- First timestamp: `2010-12-29 09:30:00`
- Last timestamp: `2026-06-09 15:59:00`
- Duplicate timestamps: `0`
- Active roll periods built: `62`
- Long absorption bars: `181133`
- Short absorption bars: `175581`

Normal pipeline validation on the 2011-01-03 to 2026-06-09 RTH research subset:

- Rows: `1488630`
- Duplicate count: `0`
- Invalid OHLC rows: `0`
- Missing session segments: `0`
- Footprint feature columns preserved at 1-minute timeframe: `12`
- Long absorption bars: `181039`
- Short absorption bars: `175479`

Important limitation:

- The cache is validated for 1-minute footprint features. A 5-minute `prepare_data` call aggregates OHLCV/orderflow and drops footprint columns. Do not use this cache for 5-minute footprint research unless 5-minute footprint features are built directly from raw prints or timeframe aggregation is explicitly extended and tested for the intended semantics.

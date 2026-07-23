# Local No-Duplicate Edge Inventory Gate - 2026-06-20

Status: no eligible untested local price-action/orderflow edge selected.

Context:
- Active duplicate checks ignore `_archived`.
- Paid data is not allowed without explicit user permission.
- Future tests must use `target_r_multiple >= 1.0`; TP rescues may only raise sub-1R targets to `1.0R`.
- Trade frequency must plausibly support at least 50 trades/year before a campaign is authored.

Active campaign inventory:
- Active ES campaign definitions checked: 128.
- Top-level active campaign summaries found: 128.
- Top-level active campaign decisions: 128 FAIL, 0 PASS.
- The footprint absorption/imbalance concept is already tested as `es_footprint_absorption_initiation`.
  It used local Sierra at-price bid/ask footprint imbalance at prior RTH extremes, session open,
  opening range, rolling range, and round-number AOIs.
  It was rerun after the footprint-cache correction and failed all five originals plus all five
  one-time rescues before WFA.

Unused active entry modules after scanning all active campaign YAML:

| module | eligibility decision | reason |
|---|---|---|
| `cftc_tff_tiered_hedging_pressure` | duplicate / deprioritized | Same CFTC/TFF hedging-pressure family as completed `es_cftc_tff_hedging_pressure`; not price-action/orderflow priority. |
| `intraday_momentum_priority` | duplicate | Same economic edge family as completed intraday momentum / Gao last-half-hour / morning momentum campaigns. |
| `liquidity_risk_capacity_priority` | duplicate / composite exhausted | Combines already-tested CFTC, RRP, and volatility/liquidity state families; not a fresh primary edge. |
| `morning_intraday_momentum` | duplicate | Covered by active morning orderflow momentum and late-day intraday momentum families. |
| `opening_range_filtered_breakout` | duplicate | Covered by opening-range breakout, trend-filtered ORB, NQ-confirmed ORB, retest ORB, and failed-breakout ORB campaigns. |
| `opening_range_inverse_breakout` | duplicate | Covered by failed-breakout / opening-range fade/reclaim families. |
| `orderflow_recent_pocket_combo` | duplicate / stale feature wrapper | Uses precomputed recent-pocket orderflow boolean columns, overlapping signed-flow and time-slot orderflow pressure families. |
| `quote_liquidity_sweep_reversion` | data-gated | Requires quote/TBBO/depth liquidity fields not available in the approved Sierra aggregate-orderflow lane. |
| `rth_gap_fade` | duplicate | Covered by opening gap, overnight/intraday reversal, and opening gap orderflow absorption/continuation campaigns. |
| `trade_orderflow_multi_pressure` | duplicate wrapper | Multi-slot wrapper around bar-level trade orderflow pressure, covered by signed-flow persistence, orderflow impulse/reversal, and low-toxicity state-rank campaigns. |
| `trade_orderflow_state_rank` | duplicate | Covered at the edge level by low-toxicity same-clock orderflow state and other orderflow state-rank campaigns. |

Conclusion:
- Do not launch another local Sierra-only campaign from the remaining unused modules without a new
  source-supported mechanism that is not one of the completed active edge families above.
- The next viable research step is either:
  1. bring in a new no-paid-data source with enough history and a non-duplicate mechanism, or
  2. explicitly approve a data-gated lane such as TBBO/quote/depth liquidity after a cost check, or
  3. perform manual chart/trade-log review of the strongest failed partials before deciding whether any
     narrowly missed campaign deserves a specifically authorized methodological exception.

Decision for current local-edge inventory: FAIL. No new candidate strategy was promoted.

Follow-up after impulse-pause test:
- `es_impulse_pause_orderflow_continuation` was authored as an additional price-action-first edge after this
  inventory note, using completed impulse, completed pause, completed breakout, and same-direction Sierra
  aggregate orderflow confirmation.
- The campaign passed pre-PnL density after one pre-PnL reformulation, then all five originals and all five
  allowed per-variant rescues failed `limited_core_grid_test` with zero profitable parameter combinations.
- Treat impulse-pause-breakout continuation as tested and failed for active duplicate checks. The local
  Sierra-only price-action/orderflow inventory remains exhausted unless a genuinely new source-supported
  mechanism or approved data lane is introduced.

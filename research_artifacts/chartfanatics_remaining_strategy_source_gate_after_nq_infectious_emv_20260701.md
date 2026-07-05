# ChartFanatics Remaining Strategy Source Gate After NQ Infectious EMV

Review date: 2026-07-01

Status: FAIL for launching another ChartFanatics-derived ES/NQ campaign under the current no-duplicate-edge and data-availability rules.

Trigger: after closing `nq_infectious_disease_emv_state`, the live ChartFanatics strategy index was refreshed for ES/NQ futures strategies that were not already represented in the local research tree.

Live pages reviewed:
- Trading Strategies index: `https://www.chartfanatics.com/strategies`
- Auction Market Strategy: `https://www.chartfanatics.com/strategies/auction-market-strategy`
- Anthony Crudele Futures Trading Strategy: `https://www.chartfanatics.com/strategies/futures-trading-strategy`
- SMT Divergence + PO3: `https://www.chartfanatics.com/strategies/smt-divergence-po3`
- Liquidity Strategy: `https://www.chartfanatics.com/strategies/liquidity-strategy`
- AMD Model: `https://www.chartfanatics.com/strategies/amd-model`
- VIX Futures Strategy: `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`
- Order Flow Strategy: `https://www.chartfanatics.com/strategies/order-flow-strategy`
- Nasdaq ICT and Order Flow Scalping Strategy: `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`

Existing local ChartFanatics-derived or directly overlapping tests:
- `nq_20_80_price_ending_barrier`: 80/20 Nasdaq, density FAIL.
- `nq_chartfanatics_measured_move_pullback`: measured-move trend, density FAIL.
- `nq_chartfanatics_daily_bollinger_environment`: Anthony Crudele daily Bollinger environment, density FAIL.
- `nq_chartfanatics_liquidity_inversion_fvg`: liquidity inversion/FVG, density FAIL.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: SMT + PO3 midpoint reversion, density FAIL.
- `nq_chartfanatics_amd_fomc_distribution`: AMD/news distribution, staged FAIL.
- `nq_chartfanatics_jadecap_session_liquidity_fvg`: session-liquidity FVG, staged/density evidence exists.
- `nq_chartfanatics_london_trident_fvg_continuation`: Unique High RR/London trident FVG, density FAIL.
- `nq_chartfanatics_weekly_stage_breakout_bias`: weekly stage analysis, staged FAIL.

Duplicate and data-gate decisions:

| Page or family | Decision | Reason |
|---|---|---|
| Auction Market Strategy / Market Auction Theory / Low Volume Node / Volume Profile | Duplicate | The page centers on balance vs imbalance, POC/LVN/value-area location, and orderflow aggression. Local campaigns already cover prior value area, VAP/profile, LVN, POC magnet, auction acceptance/rejection, and ES video AOI/LVN orderflow families. |
| Anthony Crudele Futures Trading Strategy | Tested/duplicate | The locally auditable subset is daily Bollinger environment state plus trend/mean-reversion execution, already represented by `nq_chartfanatics_daily_bollinger_environment`. |
| SMT Divergence + PO3 | Tested | Represented by `nq_chartfanatics_smt_po3_midpoint_reversion`; rejected before PnL by density. |
| Liquidity Strategy / AMD Model / Nasdaq ICT | Tested or duplicate-adjacent | The mechanical subset reduces to liquidity sweeps, manipulation/reversal, FVG retrace, market-structure shift, or prior/session liquidity targeting. Those overlap prior stop-run, FVG inversion, AMD/news, session-liquidity, opening-range, and SMT/PO3 campaigns. |
| VIX Futures Strategy | Duplicate/data-gated | The local tree already includes ES/NQ VIX level, term-structure, VXN/VIX dispersion, VVIX, VIX-pressure/orderflow, VIX expiration, and variance-risk families. The ChartFanatics version requires live/intraday VIX versus ES/NQ prior-level confirmation; current local VIX features are daily/prior-close, not reliable intraday VIX observations. |
| Order Flow Strategy | Duplicate/data-gated | The source requires AOI confluence, value area/LVN, big trades, delta, absorption, and trapped-trader behavior. These overlap existing ES/NQ AOI/orderflow/profile campaigns, and full tape/depth/Bookmap semantics are unavailable in the completed-bar cache. |

Conclusion: no additional ChartFanatics ES/NQ campaign was launched. Launching one would either duplicate an already tested edge family or require data not currently available in the local staged workflow. Under the active no-duplicate-edge instruction, this source refresh is closed as FAIL.

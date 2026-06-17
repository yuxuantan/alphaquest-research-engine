# ES Trade Fragmentation Liquidity Reversion - Rescue Attempt 1

Date: 2026-06-17

Decision: FAIL.

## Scope

Campaign: `es_trade_fragmentation_liquidity_reversion`

Data scope: local Sierra ES RTH aggregate trade-orderflow cache only. No paid
data was downloaded.

The campaign tested high same-clock trade-count rank plus low same-clock
average-trade-size rank as a completed-bar trade-fragmentation proxy, then
faded a completed 15, 30, or 60 minute price move with next-bar execution.

## Rescue Rule

Each failed original variant received exactly one rescue run. The rescue changed
only fixed threshold values and the declared parameter space inside the existing
modules.

Unchanged across rescue:

- `trade_fragmentation_liquidity_reversion` entry module
- `percent_from_entry` stop module
- `fixed_r` target module
- core economic edge
- variant side, time slot, lookback window, and return mode
- 1-minute timeframe and Sierra RTH data window
- commission, slippage, tick size, point value, fill rules, session rules, prop rules, and staged validation gates

## Results

All five originals failed `limited_core_grid_test`. All five rescues also failed
`limited_core_grid_test`. No run reached monkey, WFA, WFA OOS monkey, Monte
Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combos | Benchmark combos | Top net | Top PF | Top trades/year |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `morning_15m_fragmented_up_fade_short` | `run1` | 0/81 | 0 | -1984.375 | 0.7422052614485223 | 73.89549742423229 |
| `morning_15m_fragmented_up_fade_short` | `rescue1` | 0/81 | 0 | -4041.25 | 0.40547995586612723 | 102.86569578857457 |
| `morning_15m_fragmented_down_fade_long` | `run1` | 0/81 | 0 | -4456.875 | 0.4256604381443299 | 75.5958654317588 |
| `morning_15m_fragmented_down_fade_long` | `rescue1` | 0/81 | 0 | -3925.0 | 0.4130841121495327 | 101.65645848190185 |
| `midday_30m_fragmented_up_fade_short` | `run1` | 0/81 | 0 | -2121.875 | 0.6537127702978376 | 69.807619766126 |
| `midday_30m_fragmented_up_fade_short` | `rescue1` | 0/81 | 0 | -3881.25 | 0.26386913229018494 | 100.65944881889764 |
| `midday_30m_fragmented_down_fade_long` | `run1` | 0/81 | 0 | -3273.125 | 0.645285830398266 | 94.47652853720757 |
| `midday_30m_fragmented_down_fade_long` | `rescue1` | 0/81 | 0 | -3803.75 | 0.45854092526690393 | 116.4337866857552 |
| `day_60m_fragmented_two_sided_fade` | `run1` | 0/81 | 0 | -3865.0 | 0.7506853733268828 | 144.98761505278014 |
| `day_60m_fragmented_two_sided_fade` | `rescue1` | 0/81 | 0 | -7023.75 | 0.2914249684741488 | 188.91164694297072 |

Best original by top-combo net profit:
`morning_15m_fragmented_up_fade_short/run1`, top net `-1984.375`, top PF
`0.7422052614485223`, top trades/year `73.89549742423229`.

Best rescue by top-combo net profit:
`midday_30m_fragmented_down_fade_long/rescue1`, top net `-3803.75`, top PF
`0.45854092526690393`, top trades/year `116.4337866857552`.

## Artifacts

- Aggregate summary: `backtest-campaigns/es_trade_fragmentation_liquidity_reversion/campaign_test_summary.json`
- Aggregate CSV: `backtest-campaigns/es_trade_fragmentation_liquidity_reversion/campaign_results.csv`
- Source campaign: `campaigns/es_trade_fragmentation_liquidity_reversion/campaign.yaml`
- Density audit: `research_artifacts/es_trade_fragmentation_liquidity_reversion_density_audit_20260617.md`

## Conclusion

This edge is rejected in active scope. It should not be relaunched under a new
active campaign name without a materially different thesis approved before
testing.

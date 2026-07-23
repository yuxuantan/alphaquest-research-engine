# Methodology Audit - ES Large200 Record AOI Profile Reaction

Final decision: FAIL

## Source Translation

The supplied video notes describe orderflow entries at predefined areas of interest:
prior highs/lows, opening-range levels, and volume-profile levels, with emphasis on
large ES trades above 200 lots and trapped traders. This campaign converted that
idea into deterministic completed-bar rules using a strict Sierra SCID large-record
proxy, not true vendor print data.

## Data Gates

- True vendor-equivalent ES prints above 200 lots were not available locally.
- The tested fields are `large200_record_*` proxy fields built from Sierra SCID rows
  with `volume >= 200`, `num_trades == 1`, and exact side-volume coverage.
- The source-quality audit excluded older bad large-record clusters and used the
  merged 2012-01-03 through 2026-06-09 RTH proxy cache.
- Prior profile levels are approximate OHLCV-derived levels, not true volume-at-price.
- Any passing result would have required manual due diligence and independent
  print-source verification; no variant passed.

## Leakage Controls

- Prior VAH, VAL, POC, LVNs, prior RTH high, and prior RTH low were computed only
  from completed prior RTH sessions.
- Opening-range levels were unavailable until the first 30 completed RTH one-minute
  bars had closed.
- Large-record proxy flow and bar direction checks used only the completed signal bar.
- The entry module scheduled intended execution at the next one-minute timestamp.
- No final current-session VWAP, final profile, final range, future high/low, or
  future orderflow was used.

## Stage Result

All five variants failed `limited_core_grid_test`; none reached monkey, WFA, Monte
Carlo, simulated incubation, or acceptance OOS.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| combined_aoi_profile_large200_reaction_1500 | 0/27 | 0 | 0 | -5267.5 | 0.801432 | -0.507811 | 196.57 | min_total_net_profit;max_consecutive_losses |
| market_aoi_large200_two_sided_continuation_1500 | 0/27 | 0 | 0 | -6892.5 | 0.761773 | -0.614767 | 210.14 | min_total_net_profit;max_consecutive_losses |
| market_aoi_large200_two_sided_trap_1500 | 0/27 | 0 | 0 | -7970.0 | 0.490328 | -0.656219 | 153.23 | min_total_net_profit;max_consecutive_losses |
| profile_value_large200_two_sided_continuation_1500 | 0/27 | 0 | 0 | -2515.0 | 0.791977 | -0.655798 | 135.81 | min_total_net_profit;max_consecutive_losses |
| profile_value_large200_two_sided_trap_1500 | 0/27 | 0 | 0 | -4142.5 | 0.640798 | -0.580812 | 97.79 | min_total_net_profit;max_consecutive_losses |

## Verdict

FAIL. The large-record AOI/profile proxy campaign did not produce a candidate
strategy under the staged ES methodology. No candidate strategy report was created.

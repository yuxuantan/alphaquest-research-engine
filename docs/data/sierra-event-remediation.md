# Sierra event-data remediation

Verdict: **NEEDS MANUAL REVIEW**

The eight data remediation actions are implemented:

1. Sierra FIRST/LAST component groups are reconstructed into price/side trade events.
2. `(timestamp, source_ordinal)` is preserved through loading, engine replay, and validation export.
3. Sierra's 1 ms timestamp uncertainty is explicit; 100 ms use is allowed only on sessions whose trigger sequence matched Databento.
4. A per-session, per-capability manifest separates minute OHLCV, profile/delta, and full-strategy event use.
5. The purchased year routes important reruns directly through the Databento ZIP.
6. A clean Databento 09:30-11:00 1-minute cache was rebuilt; event triggers remain event-stream calculations.
7. The range trigger now uses strict `>200`, same-price/same-side uninterrupted 100 ms aggregation, post-tap qualification, persistent big-trade snapshots, developing delta revalidation, and OR trigger semantics.
8. Older Sierra history is sensitivity-only. Event-sensitive production loading fails closed outside the independently verified era/window.

## Generated-run remediation

- 121 old raw-SCID execution run roots were deleted after retaining authored configs and ledger history.
- 53 completed-bar run roots dependent on the invalid raw-component `large200` proxy were deleted.
- Four important raw-SCID roots were rerun on direct Databento and retained.
- Stale `results_index.yaml` and `runs_index.csv` pointers were removed.

Detailed path inventories are under:

- `data/reports/data_quality/ES/sierra_scid_backtest_remediation_20260714/`
- `data/reports/data_quality/ES/sierra_large200_proxy_backtest_remediation_20260714/`

## Direct-data rerun outcomes

| Variant | Window | Trades | Net | PF | Verdict |
|---|---:|---:|---:|---:|---|
| Current range POC (`yush_range_27`) | 2026-05 | 11 | -$542.50 | 0.298 | FAIL |
| `yush_trend_47` | 2025-09 to 2026-02 | 67 | -$3,720.00 | 0.652 | FAIL |
| `yush_trend_52` | 2026-03 to 2026-05 | 31 | -$2,190.00 | 0.646 | FAIL |
| Intrabar implementation POC (`run11`) | 2026-05 | 18 | +$1,947.50 | 2.345 | NEEDS MANUAL REVIEW |

The retained positive result is a one-month implementation POC, not a candidate pass.
It has no staged WFA/Monte Carlo/acceptance evidence.

## Remaining strategy-level blockers

Data plumbing is no longer the main blocker for the purchased year, but a faithful range
strategy verdict still requires a durable high-impact USD event calendar and a fresh run
with the T-5m through T entry block/flatten rule. The accepted AOI eligibility and
post-loss direction-alternation mechanics also need a final implementation audit before
any staged campaign. Do not promote the current POC result.

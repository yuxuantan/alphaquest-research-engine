# Sierra versus Databento full-session ES order-flow audit

**Verdict: NEEDS MANUAL REVIEW**

This audit compares the selected Sierra/MotiveWave-Rithmic ES contract with the
identical Databento contract across ETH (prior 16:00 through 09:30 ET) and RTH
(09:30 through 16:00 ET). It validates the canonical reconstructed event stream
and representative deterministic order-flow features, not only the strategy's
09:30-11:00 entry window.

## Outcome

- Sessions compared: **235**
- Event-equivalent sessions: **0**
- Reference-gap-only sessions: **215**
- Non-equivalent sessions: **19**
- Errors: **1**
- Session-level ETH/RTH OHLC exact: **468 / 468**
- Session-level ETH/RTH volume exact: **466 / 468**
- Last processing pass: **retry_errors**, **6.7 seconds**

## Coverage

The fail-closed event criterion requires exact ordered price, size, and aggressor
side after Sierra FIRST/LAST reconstruction, timestamps within 1 ms of Databento,
exact minute OHLC and side-volume fields, exact 1-tick and 4-tick profiles, exact
60/180/300-second bucketed volume and delta, exact large-10/large-20 aggregates,
and the strategy's exact uninterrupted same-price/same-side `>200` / 100 ms
trigger sequence.

When the canonical ordered payload is exact, deterministic features based on
price, size, aggressor side, and source order inherit the same equivalence.
Timestamp-window features can still differ at a 1 ms boundary, so each new
boundary-sensitive feature needs an explicit concordance check.

## Exceptions

| session_date | segment | sierra_contract | comparison_status | failure_reason |
| --- | --- | --- | --- | --- |
| 2025-07-22 | RTH | ESU25 | NOT_EVENT_EQUIVALENT | event_payload_sequence_mismatch |
| 2025-08-21 | ETH | ESU25 | NOT_EVENT_EQUIVALENT | aggressor_side_mismatch |
| 2025-08-27 | ETH | ESU25 | NOT_EVENT_EQUIVALENT | aggressor_side_mismatch |
| 2025-08-28 | RTH | ESU25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-09-22 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-10-10 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-10-15 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-10-20 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-10-21 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-11-05 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-11-14 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-11-18 | RTH | ESZ25 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-12-16 | RTH | ESH26 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2025-12-30 | RTH | ESH26 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2026-02-02 | RTH | ESH26 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2026-03-13 | ETH | ESH26 | NOT_EVENT_EQUIVALENT | aggressor_side_mismatch |
| 2026-05-18 | RTH | ESM26 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2026-06-01 | RTH | ESM26 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2026-06-02 | RTH | ESM26 | NOT_EVENT_EQUIVALENT | feature_mismatch:large_200_100ms_exact,large_200_100ms_reference_comparable_exact |
| 2026-06-10 | FULL_SESSION | ESM26 | ERROR | ValueError: Sierra source timestamps invert; refusing to reorder an ambiguous event stream. |

## Historical interpretation

Only 2025-07-14 through 2026-06-10 is directly
cross-vendor validated. Sierra history before the overlap remains
`EXTRAPOLATED_NOT_CROSS_VENDOR_VALIDATED`: a full modern overlap PASS gives strong
evidence for the reconstruction method, but it cannot prove that older files had
identical capture behavior. Older sessions therefore remain subject to intrinsic
marker, side, timestamp-order, continuity, and session-completeness gates.

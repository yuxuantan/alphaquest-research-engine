# ES Intraday Periodicity Persistence Density Audit - 2026-06-17

Decision: TEST

This pre-test density audit used only local Sierra ES RTH 1-minute bars and the
derived same-clock feature file. No PnL, stop, target, or result feedback was
used.

Feature file:

- `data/external/es_intraday_periodicity_features_20110103_20260609.csv`
- rows: 19085 slot-date rows
- valid 20-day mean rows: 18995
- date range: 2011-01-03 to 2026-06-09

Frozen slots:

| Variant | Slot | Entry | Flatten |
|---|---|---:|---:|
| `morning_1000_slot_persistence` | `slot_1000_1030` | 10:00 | 10:30 |
| `morning_1030_slot_persistence` | `slot_1030_1100` | 10:30 | 11:00 |
| `late_morning_1130_slot_persistence` | `slot_1130_1200` | 11:30 | 12:00 |
| `afternoon_1330_slot_persistence` | `slot_1330_1400` | 13:30 | 14:00 |
| `late_afternoon_1430_slot_persistence` | `slot_1430_1500` | 14:30 | 15:00 |

Parameter space:

- `entry.params.lookback_days`: 10, 20, 40
- `entry.params.min_mean_return_bps`: 0.5, 1.0, 1.5
- `sl.params.stop_pct`: 0.001, 0.0015, 0.0025
- `tp.params.target_r_multiple`: 0.75, 1.0, 1.25
- combinations per variant: 81

Density conclusion:

- At thresholds 0.5 and 1.0 bps, every slot/lookback pair is above 140
  prospective signals/year before fills.
- This clears the user's rule to avoid edges unlikely to reach 50 trades/year.
- The campaign is eligible for a frozen five-variant test.

Lookahead controls:

- Slot features are computed with `shift(1)` inside each slot, so a row for
  session D only uses completed same-clock slot returns from sessions before D.
- The feature file does not include current-session slot outcomes.
- A signal at HH:MM is emitted only after the HH:MM completed bar and is filled
  by the engine on the next bar open.

# ES Credit Spread State Intraday Data Gate - 2026-06-17

Decision: FAIL at data-feasibility gate before campaign scaffolding.

## Edge

Explicit HY/IG credit-spread state using ICE BofA/FRED option-adjusted spread series:

- HY OAS: `BAMLH0A0HYM2`
- IG OAS: `BAMLC0A0CM`

The planned campaign would have tested lagged high-yield spread level, low-spread complacency, high-yield spread widening/tightening, and HY-minus-IG spread widening as ES intraday state variables.

## Work Completed

- Added `tools/build_es_credit_spread_features.py`.
- Added `src/propstack/strategy_modules/entry/credit_spread_state.py`.
- Registered `credit_spread_state` in the entry registry.
- Added `tests/test_credit_spread_state.py`.
- Verified with:
  `python3 -m pytest tests/test_credit_spread_state.py tests/test_strategy_modules.py tests/test_preflight.py -q`
  (`145` tests passed).
- Built `data/external/es_credit_spread_features_20110103_20260609.csv` from local ES Sierra RTH sessions plus free public FRED graph CSVs.

## Data Findings

- `data/external/fred_bamlh0a0hym2.csv`: 793 rows, `2023-06-19` to `2026-06-15`.
- `data/external/fred_bamlc0a0cm.csv`: 793 rows, `2023-06-19` to `2026-06-15`.
- Derived ES session feature file: 3,817 rows, `2011-01-03` to `2026-06-09`.
- Valid rank rows for both HY OAS level and one-day change: 680 rows, `2023-09-13` to `2026-06-09`.

## Gate Result

Although some thresholds would clear a rough 50 signals/year density screen over the short valid period, the public FRED/ICE credit-spread history currently cached here is too short for the configured staged methodology:

- WFA requires at least 10 windows.
- The staged runner uses 48-month train / 12-month test / 12-month step by default.
- The valid ranked feature span is only about 2.7 years.

No five-variant campaign was launched because this data span cannot satisfy the WFA evidence requirement without changing methodology or sourcing a longer no-cost history.

## Lookahead Control

The feature builder maps each ES session to the latest credit-spread observation on or before `session_date - 2 business days`. That conservative lag avoids using same-day or uncertain publication-time credit-spread data for intraday ES signals.

## Final Decision

FAIL. Data-gated before campaign testing; no candidate strategy report was created.

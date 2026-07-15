# Methodology audit: ES completed-bar TPO value-edge auction rejection

Verdict: **FAIL**.

## Implementation and timing

- The developing 70% TPO profile assigns one time-price opportunity to every ES tick between each completed one-minute
  bar's low and high. It does not use volume, bid/ask assignment, trade size/count, or event timestamps.
- The profile, opening range, VAH/VAL AOI, range-expansion test, and POC-location test used for a rejection bar are frozen
  before that bar begins. The rejection decision occurs only after the bar closes, with entry at the next bar open.
- The current range may be at most 20% wider than the range known one-third of elapsed session time earlier. Developing
  POC must be in the middle third of the price range.
- A valid AOI is anchored by developing TPO VAL plus ORL for longs, or TPO VAH plus ORH for shorts, and is capped at three
  points. The parameter grid tests 1.5- and 3-point caps and zero- or one-tick probes.
- The target is the opposite developing TPO edge frozen at signal time, subject to the engine's predeclared one-R minimum.
  The stop is two or four ticks outside the AOI and is rejected above five points. Reaching the frozen value midpoint can
  move the stop to entry plus/minus 1.25 points when that stop is mechanically behind the trigger and before the target.
- The strategy flattens at 11:00 ET, allows at most three trades per day, and requires the opposite direction after an
  actual full stop. Non-stop exits do not impose alternation.

## Data and execution

- The derived price-only lane contains 322,200 one-minute bars across 3,580 internally screened regular sessions from
  2011-08-15 through 2026-06-09. Every admitted session contains all 90 bars from 09:30 through 10:59 ET and passes the
  existing Sierra raw-structure gate.
- Older Sierra dates are internally screened structural/minute-bar sensitivity data, not independently verified trade
  events. This is acceptable only because the implemented features are completed-bar OHLC/TPO features.
- The test uses one ES contract, $2.50 commission per side, $50 per point, and zero modeled slippage per the user's exact-fill
  instruction. Same-bar stop/target ambiguity is resolved pessimistically stop-first. Monte Carlo would add adverse
  slippage, but no variant earned access to that stage.
- A historical high-impact USD event calendar is unavailable. The required T-5m through T entry block therefore was not
  represented. This limitation cannot rescue the result and prevents any claim of exact original-strategy fidelity.

## Predeclared testing and outcome

- Five distinct variants were fixed before PnL: two-sided rejection, strong-close rejection, two-bar confirmation,
  VAL-long rejection, and VAH-short rejection.
- Each variant tested eight combinations: two probe depths, two AOI widths, and two stop offsets. There were no post-result
  parameter changes or rescue attempts.
- The objective density gate was three trades per week, represented as 156 trades per year. The best shortlist density was
  112.70 trades/year. None of the five variants met it.
- All 40 shortlist combinations lost money; zero passed benchmarks. The official pipeline therefore stopped at
  `limited_core_grid_test`, as required. WFA, monkey, Monte Carlo, simulated incubation, and acceptance were skipped rather
  than consuming evidence after an objective first-stage rejection.
- Diagnostic full-history fixed-configuration runs also failed: 579-1,264 trades, 39.85-85.51 trades/year, profit factors
  0.599-0.676, and net losses from $8,637.50 to $18,882.50.

This campaign is rejected. The completed-bar proxy neither achieved the requested activity rate nor showed positive
economics. It is not a candidate strategy and must not be described as ready to trade.

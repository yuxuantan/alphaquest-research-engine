# NQ Consumer Credit State Methodology Audit

Date: 2026-07-01

Final verdict: FAIL

## Edge Definition

This campaign tested one edge: strictly lagged household consumer-credit growth and credit-burden state as a proxy for household leverage, deleveraging pressure, and balance-sheet capacity. It used Federal Reserve/FRED G.19 consumer-credit series plus disposable personal income with a 60-calendar-day lag.

## Duplicate Edge Check

No existing campaign or ledger row was found for G.19 consumer-credit balance/burden state. Adjacent but distinct campaigns include consumer sentiment, FINRA margin leverage, credit ETF risk appetite, retail inventory demand, Treasury term premium, inflation, productivity/unit-labor-cost, and corporate equity supply.

## Density Audit

The initial high-credit-growth/high-credit-burden expressions failed pre-PnL density. Before any NQ PnL was inspected, the official five were repaired to low total-credit growth, low revolving-credit growth, and low credit-burden expressions. The final audit passed 45/45 declared density rows.

## Staged Validation

Four variants failed limited_core_grid_test with 0/27 profitable combinations. total_credit_3m_contraction_short_1000 passed core breadth at 19/27 profitable combinations (13/27 benchmark-passing) but failed limited_monkey_test because core_beats_monkey_max_drawdown_rate=0.88425 was below the 0.90 gate. No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Profitable Rate | Benchmark Passing | Top Net | Top PF | Top Trades | Monkey DD Beat Rate |
|---|---|---:|---:|---:|---:|---:|---:|
| total_credit_3m_contraction_short_1000 | limited_monkey_test | 0.703704 | 13/27 | 3312.5 | 1.254709727028066 | 103 | 0.884250 |
| revolving_credit_3m_relief_long_1030 | limited_core_grid_test | 0.000000 | 0/27 | -2530.0 | 0.9014797507788161 | 271 |  |
| total_credit_to_income_low_long_1130 | limited_core_grid_test | 0.000000 | 0/27 | -1715.0 | 0.94512 | 371 |  |
| revolving_credit_to_income_low_long_1200 | limited_core_grid_test | 0.000000 | 0/27 | -2750.0 | 0.9197548876568428 | 371 |  |
| revolving_credit_1m_relief_long_1330 | limited_core_grid_test | 0.000000 | 0/27 | -1245.0 | 0.9003202562049639 | 173 |  |

## Downstream Gates

WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, and candidate reporting were not reached because no variant passed limited_monkey_test. No rescue was authorized.

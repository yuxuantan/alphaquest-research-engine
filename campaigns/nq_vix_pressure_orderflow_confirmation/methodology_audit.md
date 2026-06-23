# Methodology Audit - NQ VIX Pressure Orderflow Confirmation

Verdict: FAIL

Pre-PnL controls:
- Five variants were fixed before PnL testing after density-only screening.
- The VIX feature file uses only observations strictly before the NQ session date.
- NQ confirmation uses completed RTH bars through the signal bar close; engine entry occurs no earlier than the next-bar boundary.
- Tunable grid per variant: one entry parameter, one stop parameter, one target parameter, 27 total combinations.

Staged outcome:
- 3 variants failed limited_core_grid_test.
- 2 variants passed core but failed limited_monkey_test.
- 0 variants reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

Failure interpretation:
The orderflow confirmation did not solve the VIX-state drawdown/randomness problem. Core-passing branches had weak net edge and failed randomized-entry robustness, so the campaign is rejected without rescue.

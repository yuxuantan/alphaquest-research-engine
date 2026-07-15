# NQ Pre-Holiday Effect Methodology Audit

Verdict: FAIL.

Authored before NQ PnL inspection as a direct transfer of the ES preholiday effect family. The holiday signal calendar is deterministic and unchanged; early-close sessions remain excluded.

Duplicate-edge screen: distinct from existing NQ weekday, turn-of-month, turn-of-year, Halloween, FOMC, OPEX, and volatility-managed seasonality families because the signal is specifically the final regular RTH session before a full NYSE holiday.

Pre-PnL density result: FAIL. Only 3 of 9 declared entry rows cleared the sparse-event full-history, deterministic limited-core proxy, and latest-window density gates. No NQ PnL, stop/target outcome, equity, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was inspected.

Failure reason: the unconditional rows were dense enough, but every low-range and momentum-confirmed row was too sparse. Dropping those filtered variants after this screen would be post-result narrowing of the declared five-variant edge.

No rescue attempt is authorized after density or staged results.

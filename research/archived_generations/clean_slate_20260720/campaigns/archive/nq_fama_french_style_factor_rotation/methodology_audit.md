# NQ Fama-French Style Factor Rotation Methodology Audit

This campaign was selected after checking the active NQ tree and ledger for duplicate factor-state campaigns. It is distinct from the failed AQR BAB, technology-sector leadership, semiconductor leadership, QQQ/QQQE concentration, small-cap rotation, and NQ own-price momentum families.

Signals use the public Kenneth French daily five-factor file with a 45-calendar-day availability lag. For a session dated D, the feature builder joins only the latest factor observation on or before D minus 45 calendar days. Intraday entries use a completed one-minute NQ RTH bar and may fill no earlier than the next bar open.

Each of the five variants has one tunable entry parameter, one stop parameter, and one take-profit parameter. No rescue is authorized after staged results.

Pre-PnL density-only reform: the initial `hml_21d_growth_strength_long_1030` 0.25 HML low-tail threshold had only 48 latest-252-session signals against the 50-session floor. Before any PnL was run, that threshold was replaced with 0.40 while preserving the same HML low-tail growth-leadership mechanic.

Final staged decision: FAIL. Four variants failed `limited_core_grid_test`. The only core-passing branch, `hml_21d_value_strength_short_1000`, failed `limited_monkey_test` with `core_beats_monkey_max_drawdown_rate=0.653875` below the 0.90 gate. No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

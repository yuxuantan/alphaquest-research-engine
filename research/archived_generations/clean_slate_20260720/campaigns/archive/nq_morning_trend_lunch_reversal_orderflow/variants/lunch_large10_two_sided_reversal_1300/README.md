# lunch_large10_two_sided_reversal_1300

Campaign: `nq_morning_trend_lunch_reversal_orderflow`

Entry module: `morning_trend_lunch_reversal_orderflow`.
Stop module: `sweep_extreme`.
Target module: `fixed_r`.

Mechanic: two-sided lunch fade after a morning extension, opposite-colored completed signal bar, and large-10-lot counterflow between 10:30:00 and 13:00:00; enter at the next 5-minute bar open after the completed reversal/counterflow bar.

Source ES config: `campaigns/es_morning_trend_lunch_reversal_orderflow/variants/lunch_large10_two_sided_reversal_1300/config.yaml`

Lookahead controls: the RTH open anchor is available from the first completed bar; extension, signal-bar body, and counterflow are computed only from completed 5-minute bars; entry is next-bar open or later; no future high/low, final VWAP, final range, or future orderflow is used.

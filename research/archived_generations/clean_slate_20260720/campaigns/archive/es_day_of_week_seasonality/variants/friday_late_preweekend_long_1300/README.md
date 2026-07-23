# friday_late_preweekend_long_1300

Campaign: `es_day_of_week_seasonality`

## Mechanic
After the completed 12:55-13:00 ET bar on Fridays, go long ES to test whether pre-weekend strength is concentrated after midday. The signal uses only the known weekday and the completed 5-minute bar ending at `13:00:00`; the engine enters at the next bar open and flattens by `15:55:00` ET unless the stop or target is hit first.

## Modules
- Entry: `calendar_session_bias`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 9.

```yaml
sl.params.stop_pct: [0.0025, 0.004, 0.006]
tp.params.target_r_multiple: [1.0, 1.5, 2.0]
```

## Lookahead Controls
Weekday is known before the RTH session. No future price, session high/low, VWAP, range, volume, or daily close is used. The signal uses the completed bar only and relies on next-bar execution with configured ES costs, slippage, tick size, point value, pessimistic same-bar stop/target ordering, and forced flattening.

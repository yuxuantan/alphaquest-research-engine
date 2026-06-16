# slow_bucket_toxicity_long_1330

Campaign: `es_vpin_toxicity_continuation`

## Mechanic
Enter long after the completed 13:25-13:30 ET 5-minute bar when a slower VPIN proxy bucket construction has elevated shifted prior-session rank and current-session return is positive.

## Modules
- Entry: `vpin_toxicity_continuation`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.vpin_rank_cutoff:
- 0.45
- 0.55
- 0.65
entry.params.min_session_return:
- 0.00025
- 0.0005
- 0.001
sl.params.stop_pct:
- 0.0015
- 0.0025
- 0.004
tp.params.target_r_multiple:
- 0.75
- 1.0
- 1.5
```

## Lookahead Controls
VPIN rank columns are shifted prior-session rolling ranks; the same-session return is known only after the completed 13:25-13:30 ET bar, and the engine enters at the next bar open.

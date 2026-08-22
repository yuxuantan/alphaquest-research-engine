# v02 strategy implementation

This variant executes through the generic canonical-event runner. Its durable
implementation is:

- `src/alphaquest/strategy_modules/event/yush_failed_auction_reclaim.py`
- strategy ID: `yush_failed_auction_reclaim`
- implementation version: `1`
- certification manifest:
  `src/alphaquest/strategy_certifications/yush_failed_auction_reclaim.yaml`

Do not copy or edit executable Python under this campaign directory. Any
execution-affecting source change requires a new implementation version,
required test reruns, recertification, regenerated mechanics evidence, and
fresh manual mechanics approval.

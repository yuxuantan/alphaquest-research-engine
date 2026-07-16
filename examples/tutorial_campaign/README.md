# 15-Minute Studio Tutorial

This isolated walkthrough teaches the same intake → data review → mechanics approval → five-variant test → staged-result flow used by Research Studio. It exercises the real backtest engine and randomized-entry benchmark with deterministic synthetic ES-like bars.

It is not research evidence. It never reads or writes a real campaign, attempt, evidence root, or production ledger, and it is permanently ineligible for promotion.

Run it with:

```bash
make tutorial
```

Generated files are written under `examples/tutorial_campaign/generated/`:

- a governed manifest for ten explicitly synthetic sessions
- five materially distinct example variant configs
- a trade log, daily results, and strict metrics JSON for every variant
- a deterministic randomized-entry benchmark with seed `1729`
- a five-variant `stage_matrix.csv`, detailed criteria, tutorial report, and manifest

## Fifteen-minute route

1. **Research declaration — 2 minutes.** Read the falsifiable teaching claim and its known failure modes.
2. **Duplicate decision — 1 minute.** Confirm this is an isolated synthetic lesson, not a production idea.
3. **Data intake — 2 minutes.** Inspect timezone, bar-open timestamps, quality checks, and the constructed-trend warning.
4. **Execution assumptions — 2 minutes.** Confirm costs, session, entry cutoff, forced flatten, and no overnight exposure.
5. **Mechanics approval — 2 minutes.** Confirm a completed-bar decision enters on the next bar and that self-review concerns implementation, not profitability.
6. **Five variants — 2 minutes.** Compare the frozen mechanic signatures before seeing PnL.
7. **Staged results — 4 minutes.** Start with the first failed gate in the matrix. Do not rank by best PnL.

The mixed outcomes are intentional. Some variants fail the core gate through losses or inadequate sample size. The lead variant passes core with positive after-cost PnL, but fails because matched seeded random entries perform better. Later gates are not run after the first failure.

Operational `PASS` means only that the tutorial executed and produced its teaching artifacts. The final research verdict is always `FAIL`: positive backtest PnL did not demonstrate timing skill, and synthetic data can never produce a candidate strategy.

**FAIL**

# Campaign Authoring

One campaign represents one economic edge. A normal campaign declares exactly five distinct mechanical variants before PnL is inspected.

Create a scaffold:

```bash
propstack campaign new my_campaign --symbol ES --edge-family my_edge
```

Then complete:

- source title, authors, year, and link or DOI
- hypothesis and expected market mechanism
- data availability and timestamp semantics
- lookahead risks
- variant-specific entry, stop, target, timeframe, and session rationale
- parameter limits and total combinations
- commissions, slippage, tick size, point value, and prop rules

Validate before execution:

```bash
propstack campaign validate my_campaign
```

Do not silently change mechanics after OOS. An authorized rescue must preserve the edge, be declared as an attempt, and record its parent variant and rationale.

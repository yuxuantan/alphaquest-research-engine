# Davey methodology alignment

AlphaQuest uses Kevin J. Davey's *Building Winning Algorithmic Trading Systems*
as a process reference, not as a promise that a backtest can establish
tradeability. The book's development sequence is goals and objectives, a
market-grounded idea, limited testing, walk-forward analysis, Monte Carlo and
incubation, diversification and sizing, documentation, deployment, and live
monitoring. AlphaQuest keeps that sequence but adds stricter provenance,
mechanics certification, and fail-closed review gates for futures research.

Primary reference: Kevin J. Davey, [*Building Winning Algorithmic Trading
Systems: A Trader's Journey from Data Mining to Monte Carlo Simulation to Live
Trading*](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118778944),
Wiley, 2014, DOI `10.1002/9781118778944`.

## Repository mapping

| Davey process concern | AlphaQuest control | Fail-closed boundary |
|---|---|---|
| Define goals and reasons to stop before development | `ResearchObjectivesV1` is completed before the idea and is embedded, hashed, and displayed read-only in the campaign protocol. Repository policy supplies minimum floors; a campaign may only be stricter. | A current Studio PnL run without a matching objective contract is `NEEDS MANUAL REVIEW`. Objectives are not retrofitted to a legacy result. |
| Begin with a logical trading idea and reject weak ideas early | Source, expected mechanism, economic-edge fingerprint, duplicate review, one initial variant, limited grid, and sequential stage gates are frozen before PnL. | The runner stops at the first scientific failure. A later variant requires the immediately prior reviewed `FAIL`. |
| Treat every development attempt as part of the record | `experiment_registry.jsonl` reserves every PnL-bearing attempt before execution and counts completed, failed, and cancelled trials by economic edge. | The SHA chain and atomic head receipt detect mutation, reordering, and tail deletion. A missing objective, parent, config, data, grid, or edge identity prevents reservation. |
| Verify the trading rules, costs, and data before performance | Certified modules, manual mechanics sampling, timestamp/session validation, commissions, slippage, contract specifications, pessimistic ambiguous fills, and forced flatten are mandatory. | Mechanics approval gates every PnL-bearing stage and never carries across source, config, or data hash drift. |
| Use limited testing as a cheap filter | Limited core-grid and monkey stages operate before expensive robustness work, with centrally owned windows, seeds, run counts, and criteria. | Campaign configs cannot weaken or reorder repository methodology. |
| Challenge whether each claimed rule contributes | A component-attribution contract can be sealed before PnL and evaluated with certified neutral replacements under the identical data, window, grid, costs, and engine contract. | Leave-one-out output is inspection-only; it cannot approve a strategy or authorize post-OOS rule deletion. |
| Build out-of-sample evidence with walk-forward analysis | Each window selects parameters from in-sample data and evaluates a complete subsequent half-open OOS interval. OOS windows and trades must be unique, complete, chronological, and non-overlapping before stitching. | Partial end windows, early-exit fragments, overlapping windows, and unavailable evaluation-period annualization fail the WFA gate. |
| Think in probability with Monte Carlo | Monte Carlo runs at least the repository/objective minimum and reports net-profit, drawdown, breach, ruin, loss-cluster, and prop-lifecycle probabilities over a fixed horizon. | Futures trades are sampled in whole-session blocks, retaining within-session order; an insufficient source horizon fails instead of silently shortening the simulation. |
| Keep unseen historical validation separate from incubation | The former `simulated_incubation_*` compatibility IDs are presented as **Secondary Historical OOS Holdout** stages. | Historical replay is never described as chronological forward evidence. |
| Incubate after historical validation | A forward plan starts only from a hash-valid `PASS` result plus an independent approved-candidate review. Paper/shadow observations are uploaded into content-addressed storage and appended to a hash-chained journal. | At least 90 calendar days and 30 trades, or stricter frozen objectives, produce only `ELIGIBLE_FOR_REVIEW`. Breaches or predeclared abandonment rules produce `FAILED`; no event can produce PASS. |
| Diversify rather than stack correlated systems | Portfolio review intersects candidates' hash-bound, complete acceptance-OOS evaluation calendars, zero-fills proven no-trade sessions, and reports PnL/return correlations, overlapping loss days, combined drawdown, marginal drawdown contribution, and concentration. | Two or more current finalized candidates plus their exact acceptance summary, session calendar, and trade log are required. The review remains `NEEDS MANUAL REVIEW`. |
| Decide sizing and deployment explicitly | A human deployment record binds current forward evidence, account and instrument contract limits, requested allocation, rollback/kill criteria, and monitoring thresholds. | The service has no order-routing capability. Approval means `APPROVED_FOR_MANUAL_DEPLOYMENT`, not an executed deployment. |
| Monitor real-time performance and know when to stop | Append-only monitoring evaluates daily loss, drawdown, losing streak, rolling expectancy, and slippage against the frozen deployment thresholds. | Status is `HEALTHY`, `ALERT`, `RETIREMENT_REVIEW`, or `NEEDS MANUAL REVIEW`; the service cannot automatically retire a strategy or send an order. |
| Document the full process | Campaign definitions, immutable attempts, mechanics evidence, stitched WFA trades, Monte Carlo summaries, ResultBundleV2, research ledger, forward journal, portfolio review, deployment decision, and monitoring journal retain hashes and provenance. | Candidate convenience artifacts are suppressed whenever evidence or finalization is incomplete. |

## Deliberate differences from the book

- AlphaQuest does not copy example return, drawdown, efficiency, or incubation
  thresholds from the book. Repository policy supplies conservative floors and
  the researcher freezes stricter business objectives before PnL.
- The Monte Carlo implementation uses whole-session blocks instead of blindly
  shuffling individual trades. This preserves observable intraday dependence
  and is more conservative for clustered futures losses.
- Manual mechanics reconciliation and certified execution modules precede the
  book-style performance funnel. A statistically attractive result with
  ambiguous fills or timing remains unresolved.
- A historical `PASS` is only a candidate. Forward incubation, portfolio
  effects, human deployment review, operational monitoring, and external due
  diligence remain separate decisions.

## Implementation entry points

- Objectives and compilation: `src/alphaquest/authoring/models.py`,
  `src/alphaquest/authoring/compiler.py`
- Repository-owned methodology: `config/research_settings.yaml`,
  `src/alphaquest/research/policy.py`
- WFA and Monte Carlo: `src/alphaquest/research/wfa.py`,
  `src/alphaquest/research/monte_carlo.py`
- Trial accounting and attribution inspection:
  `src/alphaquest/research/experiment_registry.py`,
  `src/alphaquest/research/attribution.py`
- True forward lifecycle: `src/alphaquest/studio/forward_incubation.py`
- Portfolio, deployment, and monitoring: `src/alphaquest/studio/portfolio.py`

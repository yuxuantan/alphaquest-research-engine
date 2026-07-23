# Research Studio

AlphaQuest Research Studio is the local, single-researcher interface for completed-bar ES and NQ research. After one administrator installs the workspace, launch it by double-clicking `AlphaQuest Studio.command`. You do not edit Python, YAML, hashes, or artifact paths.

## How Studio runs

The novice interface is a committed React application served by FastAPI at a workstation-only address. The browser talks to the same governed Python services used by the expert CLI; it does not reimplement campaign, data, approval, attempt, or result rules. A separate durable local worker owns long-running mechanics and performance jobs, so refreshing or closing the browser does not stop research.

Researchers do not need Node.js. The launcher uses the committed production bundle under `src/alphaquest/studio/web_assets/`, waits for both HTTP and worker health, and only then opens the local URL. The application has no hosted counterpart or CDN dependency and can operate offline with local data. Optional AI drafting is disabled by default and is the only Studio feature that makes an external API request when explicitly configured and used.

Operators can inspect or stop the managed pair without opening the interface:

```bash
alphaquest studio status
alphaquest studio stop
```

The old Streamlit Studio is retained only as an explicit migration fallback for expert operators. It is not the novice workflow. The separate Streamlit validation dashboard likewise remains an expert artifact-inspection tool.

## The seven gates

1. Declare the source, falsifiable hypothesis, causal mechanism, holding horizon, and known failure modes before PnL.
2. Review deterministic matches from active definitions, archived definitions, and `research_ledger.csv`. Close a duplicate as pre-PnL `FAIL`, or write a substantive economic distinction.
3. Select governed bars or import CSV/Parquet. Map timestamp/OHLCV/contract columns and declare timezone, timestamp meaning, and roll policy. The original file is quarantined; hashes, coverage, gaps, duplicates, ordering, invalid OHLC, transformations, and every dropped row are disclosed.
4. Confirm session, costs, sizing, entry cutoff, forced flatten, overnight prohibition, roll policy, and one certified prop profile. Studio freezes the profile's complete challenge, drawdown, consistency, payout, and lifecycle rules into every variant; a typed label is never treated as a rule set.
5. Select a certified recipe, build a bounded visual completed-bar rule, select a certified event-replay strategy package, or generate an engineering handoff.
6. Edit and confirm one initial variant card. For certified event strategies, each manifest-declared parameter is shown as a fixed reviewed value; entering a predeclared grid makes only that parameter tunable. Suggestions use the frozen brief and certified catalog—never observed PnL.
7. Read the plain-language protocol, run strict validation, and freeze. Publication rechecks data and duplicate fingerprints, runs preflight, atomically installs the initial-variant source tree, appends planned ledger rows, and refreshes generated views.

Drafts autosave under `research/drafts/` and remain outside active discovery until publication. Home reads drafts directly, so new work never disappears while an index is stale.

## What Studio refuses

Studio supports governed completed-bar ES/NQ research and explicitly certified trade-event packages. Arbitrary expressions, browser-entered Python, `eval`, negative lags, centered/future windows, session-final values, uncertified features, intrabar approximation, and unregistered event replay remain prohibited.

Unsupported ideas produce `research/handoffs/<campaign_id>/engineering_handoff.json` with a causal timeline, one initial proposed mechanic, data granularity, fill/ambiguity rules, required module contract, and tests. Their verdict is `NEEDS MANUAL REVIEW`, and they cannot be submitted until engineering certifies the implementation.

## Mechanics and performance

The current variant requires mechanics approval before every performance or optimization stage. Using the variant's declared default parameters, compare 5 deterministic random entries (seed 0), or all entries if the mechanics window contains fewer than 5, plus the required first, last, best, worst, forced-flatten, same-bar ambiguity, warning, and edge-case samples against charting software. Every sample must be marked correct and every automated check must pass. Self-review means only “implementation matches the frozen specification.” Studio derives every hash automatically; config or data drift makes approval stale.

Parameter selection is not an alternative to mechanics approval. A variant may declare a predeclared parameter grid or an empty grid. An empty `parameters: {}` mapping means every stage evaluates exactly one combination: the variant's frozen default config. WFA still uses chronological train/test windows, but it has nothing to optimize and carries the same fixed config into each unseen test window. Incubation and acceptance apply the same rule.

For certified event packages, `strategy.event.params` is the executable source of truth. Studio permits only parameters declared tunable by the strategy certification, requires each grid to include its reviewed default, applies the entry/stop/target tunable caps by certified category, and writes the same grid to core and WFA. A published pre-PnL variant may declare a missing grid only through an immutable **Pre-PnL parameter declaration** follow-up; that attempt requires fresh mechanics evidence and approval before performance testing.

“Run full test suite” puts only the current variant into the durable local queue. Closing the browser does not stop work. A repeated click returns the existing job. Hash drift blocks before attempt reservation; a crash or cancellation after evidence reservation preserves partial artifacts and becomes `NEEDS MANUAL REVIEW` without replay.

After a reviewed variant receives terminal `FAIL`, Studio unlocks **Prepare next variant**. Studio reads the first failed criterion from the predecessor's immutable result bundle and uses that stage, metric, actual value, threshold, and reason to rank the remaining certified mechanics. The researcher records an evidence-based failure analysis, reviews and explicitly confirms the proposed materially different mechanic, and freezes it as the next member of the same edge campaign. `PASS` and `NEEDS MANUAL REVIEW` do not unlock another variant. A campaign stops after five variants, and prior variant configs remain immutable.

Results lead with the sequential variant stage matrix and first failed or unresolved gate. The result view reads only a complete hash-valid `ResultBundleV2`, then shows actual-versus-required criteria, required metrics, year/month/session/side tables, parameter neighbors, stitched WFA evidence, Monte Carlo evidence, and equity/drawdown charts in the browser. Missing or hash-drifted evidence becomes `NEEDS MANUAL REVIEW`; Studio never falls back to a stale index verdict. `PASS` always means “candidate strategy only.” A different reviewer must inspect the same evidence and sign `candidate_review.json` before lifecycle state can become `candidate`.

## Explicit follow-up attempts

Studio never edits or replays an original attempt. Open a campaign's **History** tab and choose **Create explicit follow-up**, then select one of five lanes:

- Replication keeps the frozen mechanics, data, and methodology unchanged while issuing fresh evidence identity.
- Data refresh requires another governed `PASS` dataset and records the data change across every currently declared variant.
- Methodology rerun keeps mechanics and data unchanged but reruns the full current mandatory stage protocol.
- Pre-PnL mechanics correction records the exact old and new scalar module value and is rejected once parent performance evidence exists.
- Authorized rescue requires an immutable parent `FAIL`, a named authorizer, campaign policy with `allowed: true`, and is limited to one rescue for the failed target variant.

Every follow-up receives a unique attempt ID, parent lineage, substantive reason, immutable manifest/config hashes for the currently declared variants, planned ledger events, and fresh validation, approval, and run paths under the storage-aware campaign tree. Publication runs full preflight before one atomic install. Repeating a queue click returns the same jobs; creating a follow-up is the only way to obtain a new scientific identity. A blocked pre-reservation job shows this action explicitly and will not replay itself.

Experts can use the same service through `alphaquest studio attempt create|list|queue-mechanics|queue-run`; the Studio controls remain the novice path and never ask the researcher to type YAML or hashes.

## Optional AI drafting

Studio is fully usable without AI. When configured, the adapter sends only pasted notes or text locally extracted from explicitly selected PDF pages. It sends no market data, results, raw files, web tools, or execution access. Requests use `store=false` and strict JSON Schema output; the response is still untrusted application input and requires deterministic validation plus explicit human confirmation.

Implementation references: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data#default-usage-policies-by-endpoint).

The local provenance record includes provider, administrator-pinned model ID, prompt version, and prompt/source/response hashes. The API key is stored in the OS keychain. Settings records and displays the administrator-provided organization retention policy beside every AI drafting form. Studio never promises zero retention unless the administrator explicitly confirms that control is enabled for the configured API organization.

## Tutorial

Open Tutorial and run the isolated 15-minute walkthrough. It creates a disposable workspace under `examples/tutorial_campaign/generated/` and sends synthetic bars through the real governed importer, strict initial-variant draft, publication preflight, transactional publisher, SQLite queue, mechanics worker, sample-bound approval service, backtest engine, randomized-entry benchmark, and `ResultBundleV2` writer. The isolated workspace has its own teaching-only active tree, ledger, evidence, approvals, and runtime database; nothing is written to real campaign evidence or the production ledger.

The initial variant uses one frozen calendar entry edge and a predeclared certified risk/exit structure. If it passes the core gate, it continues to the seeded randomized-entry gate. The teaching result ends `FAIL`: positive PnL does not beat randomized entries, which is the only state that could unlock a second mechanic in a real sequential campaign.

The tutorial deliberately does not reserve or run a production research attempt. Ten synthetic sessions cannot honestly satisfy the full walk-forward, Monte Carlo, incubation, and locked-acceptance methodology, so those stages remain `NOT_RUN`. This is an explicit teaching boundary, not a shortened path to candidate status.

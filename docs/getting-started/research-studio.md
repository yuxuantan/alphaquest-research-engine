# Research Studio

AlphaQuest Research Studio is the local, single-researcher interface for completed-bar ES and NQ research. After one administrator installs the workspace, launch it by double-clicking `AlphaQuest Studio.command`. You do not edit Python, YAML, hashes, or artifact paths.

## The seven gates

1. Declare the source, falsifiable hypothesis, causal mechanism, holding horizon, and known failure modes before PnL.
2. Review deterministic matches from active definitions, archived definitions, and `research_ledger.csv`. Close a duplicate as pre-PnL `FAIL`, or write a substantive economic distinction.
3. Select governed bars or import CSV/Parquet. Map timestamp/OHLCV/contract columns and declare timezone, timestamp meaning, and roll policy. The original file is quarantined; hashes, coverage, gaps, duplicates, ordering, invalid OHLC, transformations, and every dropped row are disclosed.
4. Confirm session, costs, sizing, entry cutoff, forced flatten, overnight prohibition, roll policy, and prop profile.
5. Select a certified recipe, build a bounded visual completed-bar rule, or generate an engineering handoff.
6. Edit and individually confirm exactly five materially distinct variant cards. Suggestions use the frozen brief and certified catalog—never observed PnL.
7. Read the plain-language protocol, run strict validation, and freeze. Publication rechecks data and duplicate fingerprints, runs preflight, atomically installs the five-variant source tree, appends planned ledger rows, and refreshes generated views.

Drafts autosave under `research/drafts/` and remain outside active discovery until publication. Home reads drafts directly, so new work never disappears while an index is stale.

## What Studio refuses

Studio V1 supports completed 1-, 5-, and 15-minute ES/NQ bars. Arbitrary expressions, Python generation, `eval`, negative lags, centered/future windows, session-final values, uncertified features, intrabar assumptions, order-flow approximation, and event replay are prohibited.

Unsupported ideas produce `research/handoffs/<campaign_id>/engineering_handoff.json` with a causal timeline, five proposed mechanics, data granularity, fill/ambiguity rules, required module contract, and tests. Their verdict is `NEEDS MANUAL REVIEW`, and they cannot be submitted until engineering certifies the implementation.

## Mechanics and performance

All five variants require mechanics approval before performance testing. The embedded inspector shows charts, conditions, exits, order-flow detail when available, automated checks, risk-based sample categories, and annotations. Self-review means only “implementation matches the frozen specification.” Studio derives every hash automatically; config or data drift makes approval stale.

“Run campaign” puts all five variants into the durable local queue in declared order. Closing the browser does not stop work. Each variant stops at its first scientific failure while later variants continue. A repeated click returns the existing job. Hash drift blocks before attempt reservation; a crash or cancellation after evidence reservation preserves partial artifacts and becomes `NEEDS MANUAL REVIEW` without replay.

Results lead with the five-variant stage matrix and first failed or unresolved gate. `PASS` always means “candidate strategy only.” A different reviewer must sign `candidate_review.json` before lifecycle state can become `candidate`.

## Explicit follow-up attempts

Studio never edits or replays an original attempt. From Campaigns → Published research → Create an explicit governed follow-up, choose one of five lanes:

- Replication keeps the frozen mechanics, data, and methodology unchanged while issuing fresh evidence identity.
- Data refresh requires another governed `PASS` dataset and records the data change across all five variants.
- Methodology rerun keeps mechanics and data unchanged but reruns the full current mandatory stage protocol.
- Pre-PnL mechanics correction records the exact old and new scalar module value and is rejected once parent performance evidence exists.
- Authorized rescue requires an immutable parent `FAIL`, a named authorizer, campaign policy with `allowed: true`, and is limited to one rescue for the failed target variant.

Every follow-up receives a unique attempt ID, parent lineage, substantive reason, immutable manifest/config hashes, five cloned configs, planned ledger events, and fresh validation, approval, and run paths under the storage-aware campaign tree. Publication runs full preflight before one atomic install. Repeating a queue click returns the same jobs; creating a follow-up is the only way to obtain a new scientific identity. A blocked pre-reservation job shows this action explicitly and will not replay itself.

Experts can use the same service through `alphaquest studio attempt create|list|queue-mechanics|queue-run`; the Studio controls remain the novice path and never ask the researcher to type YAML or hashes.

## Optional AI drafting

Studio is fully usable without AI. When configured, the adapter sends only pasted notes or text locally extracted from explicitly selected PDF pages. It sends no market data, results, raw files, web tools, or execution access. Requests use `store=false` and strict JSON Schema output; the response is still untrusted application input and requires deterministic validation plus explicit human confirmation.

Implementation references: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data#default-usage-policies-by-endpoint).

The local provenance record includes provider, administrator-pinned model ID, prompt version, and prompt/source/response hashes. The API key is stored in the OS keychain. Settings records and displays the administrator-provided organization retention policy beside every AI drafting form. Studio never promises zero retention unless the administrator explicitly confirms that control is enabled for the configured API organization.

## Tutorial

Open Tutorial and run the isolated 15-minute walkthrough. It creates a disposable workspace under `examples/tutorial_campaign/generated/` and sends synthetic bars through the real governed importer, strict five-variant draft, publication preflight, transactional publisher, SQLite queue, mechanics worker, sample-bound approval service, backtest engine, randomized-entry benchmark, and `ResultBundleV2` writer. The isolated workspace has its own teaching-only active tree, ledger, evidence, approvals, and runtime database; nothing is written to real campaign evidence or the production ledger.

The five variants share one frozen calendar entry edge and use predeclared certified risk/exit structures, producing mixed limited-core outcomes. Variants that pass the core gate continue to the seeded randomized-entry gate. The teaching result ends `FAIL`: the promising lead PnL does not beat randomized entries.

The tutorial deliberately does not reserve or run a production research attempt. Ten synthetic sessions cannot honestly satisfy the full walk-forward, Monte Carlo, incubation, and locked-acceptance methodology, so those stages remain `NOT_RUN`. This is an explicit teaching boundary, not a shortened path to candidate status.

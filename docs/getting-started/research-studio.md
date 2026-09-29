# Research Studio

AlphaQuest Research Studio is the local, single-researcher interface for completed-bar ES and NQ research. After one administrator installs the workspace, launch it by double-clicking `AlphaQuest Studio.command`. You do not edit Python, YAML, hashes, or artifact paths.

> **P2 legacy compatibility:** Studio still begins with a campaign draft. It is
> temporarily compatible with existing campaigns but is not the target P1
> discovery flow. The canonical pre-hypothesis inventory is the
> [Central Edge Backlog](../research/edge-backlog.md); replacing Studio's start
> flow and enforcing campaign linkage belong to later P3-P5 work.

For the audited research/backtesting comparison with MultiCharts, see
[MultiCharts research and backtesting parity](../reference/multicharts-research-parity.md).

## How Studio runs

The novice interface is a committed React application served by FastAPI at a workstation-only address. The browser talks to the same governed Python services used by the expert CLI; it does not reimplement campaign, data, approval, attempt, or result rules. A separate durable local worker owns long-running mechanics and performance jobs, so refreshing or closing the browser does not stop research.

Researchers do not need Node.js. The launcher uses the committed production bundle under `src/alphaquest/studio/web_assets/`, waits for both HTTP and scientific-worker health, and only then opens the local URL. The application has no hosted counterpart or CDN dependency and can operate offline with local data. The optional Codex research worker is separate from this health boundary and runs only when an operator starts it.

Operators can inspect or stop the managed pair without opening the interface:

```bash
alphaquest studio status
alphaquest studio stop
```

The old Streamlit Studio is retained only as an explicit migration fallback for expert operators. It is not the novice workflow. The separate Streamlit validation dashboard likewise remains an expert artifact-inspection tool.

The Workflow page is the cross-campaign control center. It orders failed jobs,
human review gates, active campaign actions, and unfinished drafts into one
next-required-action queue. It also reports storage, built-asset, and derived
registry health. **Rebuild derived views** may regenerate the SQLite registry,
exports, and views, but never rewrites source definitions or immutable evidence.
Cross-attempt result reuse remains disabled, and the legacy fallback remains
installed until a separate route-by-route parity and recovery audit authorizes
removal.

## Six researcher decisions, seven backend gates

Studio groups the first two independent governance gates into one visible
**Research plan** phase. The researcher therefore moves through six numbered
decisions while the backend still validates all seven contracts separately.

1. Declare the source, falsifiable hypothesis, causal mechanism, holding horizon, and known failure modes before PnL.
2. Review deterministic matches from active definitions, archived definitions, and `research_ledger.csv`. Close a duplicate as pre-PnL `FAIL`, or write a substantive economic distinction.
3. Select governed bars or import CSV/Parquet. Map timestamp/OHLCV/contract columns and declare timezone, timestamp meaning, a certified session reference, and roll policy. The original file is quarantined; bounded source inspection discovers timestamp/contract candidates before import. Hashes, coverage, gaps, cadence violations, duplicates, ordering, invalid OHLC, transformations, and every dropped row are disclosed. The Data Library can then inspect the immutable manifest, contract/roll lineage, hash-verified roll calendar, and compare two governed manifests without making either source selectable by fiat. A pre-PnL readiness forecast compares calendar coverage with the current three-window WFA plus two sequential holdouts; it does not predict signals, trades, or performance.
4. Confirm session, costs, sizing, entry cutoff, forced flatten, overnight prohibition, roll policy, and one certified prop profile. Studio freezes the profile's complete challenge, drawdown, consistency, payout, and lifecycle rules into every variant; a typed label is never treated as a rule set.
5. Select a certified recipe, build a bounded visual completed-bar rule, select a certified event-replay strategy package, or generate an engineering handoff.
6. Edit and confirm one initial variant card. For certified event strategies, each manifest-declared parameter is shown as a fixed reviewed value; entering a predeclared grid makes only that parameter tunable. Suggestions use the frozen brief and certified catalog—never observed PnL.
7. Read the plain-language protocol and choose **Review and publish governed campaign** once. Studio still performs strict validation, freeze, and transactional publication as separate backend operations. Publication rechecks data and duplicate fingerprints, runs preflight, atomically installs the initial-variant source tree, appends planned ledger rows, and refreshes generated views.

Drafts autosave under `research/drafts/` and remain outside active discovery until publication. Home reads drafts directly, so new work never disappears while an index is stale.

## What Studio refuses

Studio supports governed completed-bar ES/NQ research and explicitly certified trade-event packages. Arbitrary expressions, browser-entered Python, `eval`, negative lags, centered/future windows, session-final values, uncertified features, intrabar approximation, and unregistered event replay remain prohibited.

Unsupported ideas produce `research/handoffs/<campaign_id>/engineering_handoff.json` with a causal timeline, one initial proposed mechanic, data granularity, fill/ambiguity rules, required module contract, and tests. Their verdict is `NEEDS MANUAL REVIEW`, and they cannot be submitted until engineering certifies the implementation.

## Mechanics and performance

The current variant requires mechanics approval before every performance or optimization stage. Every strategy uses the same mechanics protocol: frozen default parameters over the latest 10 eligible sessions in its governed dataset, followed by 5 deterministic random trade reconciliations using repository seed 7. A strategy cannot enlarge, shorten, or cherry-pick this window. Causal indicator or profile warm-up may read older data, but those bars are context and do not become extra review sessions. If the window contains fewer than 5 completed trades, mechanics evidence is insufficient and remains `NEEDS MANUAL REVIEW`; the window is not expanded for that strategy. Mechanics Review includes a read-only native replay: it steps through each retained completed bar or causal trade event, overlays entry/stop/target/exit levels, and exposes event transitions plus causal feature fields. External chart comparison is still required by policy; the native replay makes the exact governed evidence inspectable without changing it. Every sample must be marked correct and every automated check must pass. Self-review means only “implementation matches the frozen specification.” Studio derives every hash automatically; config, data, implementation, or research-policy drift makes approval stale.

All later procedures are repository-owned in `config/research_settings.yaml`: the 10% deterministic shortlist and exclusion rule, 8,000-run monkey tests, 48/12/12-month unanchored WFA, stitched-WFA OOS stress, 8,000 session-block Monte Carlo paths, a 48-month train plus 12-month secondary historical OOS holdout, and final 24-month train plus 6-month acceptance holdout. Strategy configs own mechanics and their predeclared parameter grids; they do not own stage order, windows, seeds, or global policy floors. Before an idea can leave step 1, the researcher freezes a development objective contract. Those goals can tighten the repository floors and are hash-bound into the campaign, strategy specification, authoring manifest, and each variant config. Preflight fails closed when the objective hash or methodology policy drifts.

Parameter selection is not an alternative to mechanics approval. A variant may declare a predeclared parameter grid or an empty grid. An empty `parameters: {}` mapping means every stage evaluates exactly one combination: the variant's frozen default config. WFA still uses chronological train/test windows, but it has nothing to optimize and carries the same fixed config into each unseen test window. The historical holdout and acceptance apply the same rule.

The Mechanics view reports exact declared parameter combinations, minimum WFA
windows, and Monte Carlo paths before a run. Its workload class is a relative
planning aid, not a wall-clock or disk-size promise; event density, data volume,
and hardware remain dominant.

For certified event packages, `strategy.event.params` is the executable source of truth. Studio permits only parameters declared tunable by the strategy certification, requires each grid to include its reviewed default, applies the entry/stop/target tunable caps by certified category, and writes the same grid to core and WFA. A published pre-PnL variant may declare a missing grid only through an immutable **Pre-PnL parameter declaration** follow-up; that attempt requires fresh mechanics evidence and approval before performance testing.

“Run full test suite” puts only the current variant into the durable local queue. Closing the browser does not stop work. A repeated click returns the existing job. Hash drift blocks before attempt reservation; a crash or cancellation after evidence reservation preserves partial artifacts and becomes `NEEDS MANUAL REVIEW` without replay.

After a reviewed variant receives terminal `FAIL`, Studio unlocks **Prepare next variant**. Studio reads the first failed criterion from the predecessor's immutable result bundle and uses that stage, metric, actual value, threshold, and reason to rank the remaining certified mechanics. The researcher records an evidence-based failure analysis, reviews and explicitly confirms the proposed materially different mechanic, and freezes it as the next member of the same edge campaign. `PASS` and `NEEDS MANUAL REVIEW` do not unlock another variant. A campaign stops after five variants, and prior variant configs remain immutable.

Results lead with the sequential variant stage matrix and first failed or unresolved gate. The result view reads only a complete hash-valid `ResultBundleV2`, then shows actual-versus-required criteria, required metrics, year/month/session/side tables, parameter neighbors, stitched WFA evidence, Monte Carlo evidence, and equity/drawdown charts in the browser. Finalization independently recomputes acceptance metrics over the governed evaluation period and replays terminal criteria; a stale runner PASS is downgraded. The same transaction derives a searchable trade list, click-to-inspect execution levels, MAE/MFE when retained by the runner, PnL and duration distributions, rolling 20-trade metrics, losing streaks, WFA-window summaries, Monte Carlo bands when path quantiles exist, and a parameter-surface table. Complete CSVs are downloadable only through an allowlisted endpoint that revalidates the bundle, finalization, path boundary, and file hash. Selecting a trade or grid row never changes the campaign verdict. Missing or hash-drifted evidence becomes `NEEDS MANUAL REVIEW`; Studio never falls back to a stale index verdict. `PASS` always means “candidate strategy only.” A different reviewer must inspect the same evidence and sign `candidate_review.json` before chronological forward incubation can begin. Incubation eligibility still requires a separate human deployment decision.

Results also presents one authoritative verdict matrix, and Lifecycle presents one
ordered promotion checklist. These views consolidate navigation only; scientific
validity, generic objectives, account suitability, independent review, true
forward incubation, portfolio review, and human deployment authorization remain
separate hash-bound records.

Mechanics Review can optionally import a chart-platform CSV keyed by
`trade_id` and compare timestamps, prices, and direction with every governed
sample. The importer hashes the attachment and reports mismatches, but has no
approval effect and cannot write reviewer annotations. Results exports one
deterministic due-diligence ZIP containing the finalized bundle and CSVs,
frozen campaign/spec/config documents, available review records, and a SHA-256
manifest. Deployment approval must be recorded by someone other than both the
mechanics reviewer and candidate reviewer.

When a forward observation attaches a CSV with an explicit P&L column, Studio
deterministically previews its trade count and net P&L. Unique trade identities
and explicit prop/flatten flags are reconciled when present. Duplicates, invalid
P&L, or invalid flags block the preview; absent risk flags remain manual. Nothing
is appended until the researcher confirms the calculation.

## Certified generic order simulation

Studio lists execution profiles separately from strategy packages. `generic_quote_orders_v1` supports deterministic market, limit, stop, stop-limit, OCO, partial-fill, and bid/ask quote replay, with next-event eligibility and explicit displayed-liquidity requirements. The profile is shown as certified only while its implementation bytes and required test categories match its manifest. Existing campaigns do not silently acquire this behavior: a strategy must declare the execution profile, required quote/trade columns, and fresh strategy certification before publication.

MBO queue priority, hidden liquidity, exchange-specific matching priority, live routing, and broker reconciliation remain unavailable. A strategy needing them must produce an engineering handoff and `NEEDS MANUAL REVIEW`, not an approximation.

## Explicit follow-up attempts

Do not create a follow-up merely because a terminal `FAIL` has unlocked the next sequential variant. A confirmed sequential variant remains under its governed authored attempt identity; after it is frozen, open **Testing** for that exact attempt and variant and generate mechanics evidence. For example, a newly frozen `original/v04` proceeds directly to `testing?attempt=original&variant=v04`.

A follow-up has a different purpose: it creates a new immutable scientific identity for an exact replication, governed data replacement, methodology rerun, eligible pre-PnL correction or declaration, or authorized rescue. Studio never edits or automatically replays an existing attempt. Open a campaign's **History** tab and choose **Create explicit follow-up**, then select one of six lanes. The active research scope is recommended by default, while older attempts remain selectable for an intentional historical branch. Before creation, Studio shows exactly what the selected lane changes, preserves, and invalidates:

- Replication keeps the frozen mechanics, data, and methodology unchanged while issuing fresh evidence identity.
- Data refresh requires another governed `PASS` dataset and records the data change across every currently declared variant.
- Methodology rerun keeps mechanics and data unchanged but reruns the full current mandatory stage protocol.
- Pre-PnL mechanics correction records the exact old and new scalar module value and is rejected once parent performance evidence exists.
- Pre-PnL parameter declaration freezes a certified grid before the first PnL-bearing run and requires fresh mechanics approval.
- Authorized rescue requires an immutable parent `FAIL`, a named authorizer, campaign policy with `allowed: true`, and is limited to one rescue for the failed target variant.

A deprecated strategy package remains available only for the actions permitted by its repository lifecycle. Studio may inspect it and offer an exact historical replication, but new-work lanes remain disabled with the lifecycle reason shown. The options screen reads immutable metadata only; full config, data, certification, and approval hashes are revalidated when an attempt is created or mechanics/performance work is queued.

Every follow-up receives a unique attempt ID, parent lineage, substantive reason, immutable manifest/config hashes for the currently declared variants, planned ledger events, and fresh validation, approval, and run paths under the storage-aware campaign tree. Publication runs full preflight before one atomic install. Repeating a queue click returns the same jobs; creating a follow-up is the only way to obtain a new scientific identity. A blocked pre-reservation job shows this action explicitly and will not replay itself.

Experts can use the same service through `alphaquest studio attempt create|list|queue-mechanics|queue-run`; the Studio controls remain the novice path and never ask the researcher to type YAML or hashes.

## Subscription-backed Codex research factory

Studio is fully usable without AI. In the default optional assistant mode, AlphaQuest uses the local Codex CLI authenticated by an existing ChatGPT subscription. It never asks for a ChatGPT password or token and refuses API-key or unverified authentication.

The Workflow page exposes one primary execution control, **Run next AI step**, plus an exact campaign selector, cancellation, pause/resume, and proposal-review controls. AlphaQuest, not the browser or Codex, chooses the eligible task. It supplies only an explicitly bounded research-plan, source-reference, duplicate-inventory, certified-catalog, or result packet; hashes every controller-supplied artifact and task metadata; excludes locked-holdout outcomes from design tasks; applies daily and campaign-scoped pre-PnL trial budgets; and queues the work in a dedicated SQLite database. One campaign is one budgeted economic edge. The HTTP request only queues. A separately started `alphaquest factory worker` runs one task at a time with a read-only sandbox and a small supplied workspace.

Codex can propose unconfirmed source leads, a falsifiable hypothesis, non-executable mechanics intent bound to an exact currently certified strategy catalog, or a ranking over policy-eligible next actions. Native web results used for source discovery are not deterministically captured by the controller, so AI source output remains `PARTIAL`, has no verified content hash, and must be independently captured and checked by a person. AlphaQuest—not Codex—derives failure diagnosis and eligibility deterministically from hash-valid evidence. Every strict Codex output is still untrusted: AlphaQuest revalidates its schema, exact source/objective/hypothesis references, certified strategy and parameter contract, original input hashes, and persisted review-file bindings; rejects stale or tampered proposals; records run provenance and governed result-information access; and stores accepted output as `VALIDATED_NOT_APPLIED`.

Source and hypothesis proposals use typed human-review forms rather than the generic acknowledgement path. Source review requires the researcher to inspect a compatible retained full-text capture, verify all identity fields and retraction/correction status, and explicitly accept or reject every proposed claim. Studio supplies the content and claim evidence hashes automatically. Each claim requires a method choice, a human-entered checked location, a finding, a decision rationale and limitations. Changing capture clears these entries and the overall review notes. The immutable reviewed-source artifact preserves the entire original `SourceEvidenceBundleV1`—including conflicting evidence, inference notes, rejected claims, and its unchanged AI `PARTIAL` status—then adds a separate named human-verification overlay. AI output is never silently relabeled as verified.

Hypothesis review similarly requires explicit review of every `HypothesisProposalV1` field and PASS confirmation for objective alignment, accepted-source-claim alignment, falsifiability, information timing/no-lookahead, and execution-cost awareness. Its immutable reviewed-hypothesis artifact preserves the whole proposal and binds the exact reviewed-source artifact hashes. The next mechanics task consumes that complete reviewed artifact and hash, not a bibliography row or a collapsed hypothesis string.

If reviewed mechanics intent explicitly selects `ENGINEERING_HANDOFF`, Workflow provides a third typed review. It verifies every mechanics-intent field, hypothesis alignment, unsupported scope, and causal timeline. Only then may AlphaQuest queue a bounded `EngineeringHandoffProposalV1` task bound to the exact reviewed hypothesis and mechanics hashes. That task writes no code, creates no executable campaign, grants no certification, and authorizes no test.

Other proposal types may still use the one-shot, hash-bound acknowledgement disposition. A generic acknowledgement does not copy content into authoring. Typed review artifacts also do not mutate `campaign.yaml` or the mutable Studio draft; they advance only the supervised factory context.

For a validated `NEXT_EXPERIMENT` ranking after a reviewed terminal scientific `FAIL`, Workflow instead requires a person to choose one action that Codex ranked inside AlphaQuest's deterministic eligibility allow-list. AlphaQuest records that immutable `selected_action` once and binds it to the exact ranking, context packet, predecessor result, mechanics approval, objective, research budget, and information-access ledger hashes. Selection proves only which branch the person chose. `ABANDON_EDGE` and `STOP_NO_FRESH_HOLDOUT` remain incomplete until the researcher records a separate named, hash-bound terminal-decision artifact; the completion is bound to the same result and ledger and cannot change the scientific verdict. Destination assessment is not offered in this loop because its governed worker requires scientific-validity `PASS`; it remains part of the separate candidate path.

`PROPOSE_SUCCESSOR` may queue at most one read-only, non-executable mechanics proposal for the exact next sequential variant, bound to the predecessor, reviewed hypothesis, bounded failure diagnosis, approval, budget, and certified catalog. `START_NEW_RESEARCH_GENERATION` may queue at most one unconfirmed hypothesis proposal bound to the original reviewed sources and objectives plus an unused predeclared confirmation-window identity; the prior locked result and diagnosis are excluded as design inputs. These routing and proposal artifacts do not create a variant or campaign, apply proposal content, consume or reuse a holdout, grant mechanics approval or certification, launch a performance test, promote a candidate, start deployment, or change a scientific verdict.

If schema, semantic, staleness, or packet-integrity validation fails, Studio hides the raw output and shows only a sanitized rejection code. A reviewer may record one immutable **Dismiss invalid output** disposition; rejected output can never be acknowledged or applied. Dismissal clears the failed task so a new, separately budgeted request can be built from fresh authoritative inputs.

The control is disabled whenever Codex is unavailable, the login is not confirmed as ChatGPT subscription authentication, the queue is paused or active, the daily or campaign budget is exhausted, or the next workflow transition requires a human review. Every newly compiled campaign binds its objective-derived acceptance ID to the governed dataset ID, canonical and source byte hashes, exact manifest coverage, repository-owned 24-month selection calendar, and terminal 6-month acceptance calendar. Event-replay campaigns additionally bind their execution-source contract and artifact hashes. Runtime canonicalization rejects date, policy-window, dataset, roll-calendar, or event-source drift, and preflight re-hashes the canonical bar file before testing. The second objective-derived ID remains reserved for one genuinely fresh confirmation generation; it is not assigned current data. Historical v1 logical bindings remain read-only and are not backfilled. `PASS`, `FAIL`, and `NEEDS MANUAL REVIEW` remain deterministic AlphaQuest outcomes. Humans still own source verification, research confirmation, mechanics approval, custom-strategy certification, independent candidate review, forward-incubation review, and deployment authorization.

### Legacy OpenAI API drafting compatibility

The previous selected-text drafting adapter remains available only when Settings explicitly selects **Legacy OpenAI API drafting**. It sends only pasted notes or text locally extracted from selected PDF pages—never market data, results, raw files, tools, or execution access. That separate compatibility path can incur API usage charges, uses `store=false` plus strict output validation, and stores its optional key in the operating-system keychain. It is not used by the Codex factory.

## Tutorial

Open Tutorial and run the isolated 15-minute walkthrough. It creates a disposable workspace under `examples/tutorial_campaign/generated/` and sends synthetic bars through the real governed importer, strict initial-variant draft, publication preflight, transactional publisher, SQLite queue, mechanics worker, sample-bound approval service, backtest engine, randomized-entry benchmark, and `ResultBundleV2` writer. The isolated workspace has its own teaching-only active tree, ledger, evidence, approvals, and runtime database; nothing is written to real campaign evidence or the production ledger.

The initial variant uses one frozen calendar entry edge and a predeclared certified risk/exit structure. If it passes the core gate, it continues to the seeded randomized-entry gate. The teaching result ends `FAIL`: positive PnL does not beat randomized entries, which is the only state that could unlock a second mechanic in a real sequential campaign.

The tutorial deliberately does not reserve or run a production research attempt. Ten synthetic sessions cannot honestly satisfy the full walk-forward, Monte Carlo, incubation, and locked-acceptance methodology, so those stages remain `NOT_RUN`. This is an explicit teaching boundary, not a shortened path to candidate status.

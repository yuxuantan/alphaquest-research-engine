# Central Edge Backlog

The Central Edge Backlog is AlphaQuest's durable discovery memory before a
potential economic edge becomes a governed hypothesis or campaign. It conforms
to the [canonical research operating model](research-operating-model.md) and
does not add a P1 scientific object.

## Boundary

The governed sequence remains:

```text
source or market event
  -> OBSERVATION
  -> tentative economic-edge backlog entry
  -> HYPOTHESIS proposal and review
  -> admitted HYPOTHESIS
  -> EDGE_FAMILY and CAMPAIGN
  -> STRATEGY_VARIANT
  -> ATTEMPT
  -> RUN
```

A backlog entry records a possible economic transfer: market behavior, causal
mechanism, counterparties, information inputs and availability, expected
effect, horizon, context, and source-bound observations. It does not contain
entry/stop/target rules, indicators, thresholds, parameter grids, modules,
PnL, scientific verdicts, candidate status, or deployment status. Mechanical
expressions remain downstream strategy variants.

The canonical files live under `research/edge_backlog/`. SQLite, CSV, Markdown,
the bootstrap index, and future registry views are derived and rebuildable.

## Canonical records

All contracts reject unknown fields, use canonical JSON serialization, and
carry a stable SHA-256 over the complete record except its own hash field.
Timezone-aware timestamps and exact referenced-record hashes are required.

### Observation revisions

An observation is a source-bound lead, not an edge claim. Each evidence
reference declares `HASH_BOUND` or `LOCATOR_ONLY` integrity:

- `HASH_BOUND` requires a valid content or artifact SHA-256.
- `LOCATOR_ONLY` requires a durable locator, claim locator, and evidence time,
  and prohibits a content hash so it cannot masquerade as reviewed evidence.

The same `source_id` may support several claims and observations only while its
source kind, locator, and any captured content hash remain consistent.

### Edge-entry revisions

An entry may refer to any number of observations using the closed roles
`MOTIVATING`, `SUPPORTING`, and `CONTRADICTING`. A revision may add evidence,
but it cannot silently remove an earlier contradicting reference. Title wording
is excluded from the versioned economic fingerprint. Strategy and parameter
fields are not part of the closed schema.

### Human decisions

The human-only operation records `HUMAN_OWNER_RESEARCHER` by construction. The
reviewer ID is provenance, not authentication, and there is no actor-type flag.
Every review binds the exact entry revision and the complete deterministic
duplicate candidate snapshot visible to the reviewer.

- `REVIEWED_CONTINUE` is optional curation. It is not scientific approval and
  is not required before a later P4 hypothesis proposal.
- `REJECTED` is terminal.
- `DUPLICATE` is terminal and must point to an existing canonical entry present
  in the reviewed snapshot.
- `SUSPENDED` is nonterminal and records explicit resume conditions.
- `RESUMED` is a separate immutable human record. Only after it exists may
  Codex append another revision.

`UNRESOLVED` never becomes `DISTINCT_EDGE` automatically.

### Links

The link schema reserves `HYPOTHESIS_PROPOSAL`, `ADMITTED_HYPOTHESIS`,
`EDGE_FAMILY`, `CAMPAIGN`, and `REVISIT_OF`. P2 exposes only two safe store
operations:

- a deterministic `HYPOTHESIS_PROPOSAL` link, which does not require
  `REVIEWED_CONTINUE`;
- a human-governed `REVISIT_OF` link to an exact prior entry revision.

Admission, family, and campaign link operations intentionally have no P2 CLI
surface and remain reserved for P3-P5 transitions. A revisit never changes the
prior disposition, historical outcome, or research budget.

## Actors and authority

Canonical actor classes are exactly:

- `CODEX`
- `HUMAN_OWNER_RESEARCHER`
- `ALPHAQUEST_DETERMINISTIC_ENGINE`
- `EXTERNAL_SYSTEM`

Codex capture/create/revise commands always write `CODEX`. Review and resume
commands always write `HUMAN_OWNER_RESEARCHER`. AlphaQuest computes IDs,
fingerprints, hashes, candidate sets, and structural validity, but cannot
manufacture semantic acceptance. Local provenance strings are not identity
authentication.

## CLI

Prepare a JSON payload containing only user-controlled observation or entry
fields; record IDs, revision numbers, actors, timestamps, fingerprints, and
hashes are managed by AlphaQuest.

```bash
alphaquest edge-backlog capture-observation \
  --input observation.json --actor-id codex-task-id

alphaquest edge-backlog create \
  --input edge-entry.json --actor-id codex-task-id

alphaquest edge-backlog revise edge_id \
  --input edge-entry.json --actor-id codex-task-id

alphaquest edge-backlog list --json
alphaquest edge-backlog search --query "delayed hedging" --json
alphaquest edge-backlog show edge_id --json
alphaquest edge-backlog duplicate-candidates edge_id
```

The duplicate command returns a `snapshot_sha256`. A human owner uses that
exact value when recording a review:

```bash
alphaquest edge-backlog review edge_id \
  --disposition SUSPENDED \
  --duplicate-resolution UNRESOLVED \
  --candidate-snapshot-sha256 <sha256> \
  --reason-code AMBIGUOUS_DUPLICATE \
  --rationale "The related prior edge still requires owner resolution." \
  --revisit-condition "New source evidence resolves the ambiguity." \
  --reviewer-id owner

alphaquest edge-backlog resume edge_id \
  --reason-code NEW_INFORMATION \
  --rationale "The owner reviewed material new source evidence." \
  --reviewer-id owner

alphaquest edge-backlog validate
```

There is no delete, overwrite, hypothesis-admission, campaign-admission, or
deployment command.

## Deterministic duplicate recall

Backlog matching reuses the campaign matcher's deterministic token-overlap and
match-band primitives without changing the legacy campaign behavior. The richer
backlog comparison exposes each economic dimension, exact fingerprint equality,
source overlap, downstream target overlap, revisit lineage, and lexical score.
Small deterministic economic-phrase aliases improve recall. No LLM or embedding
is an authority. Candidate output remains advisory until human resolution, and
uncertainty stays unresolved.

## Historical bootstrap

```bash
alphaquest edge-backlog bootstrap-index
```

This deterministically rebuilds `catalogs/edge_backlog_history.jsonl` from
current campaign definitions, historical clean-slate definitions and ledgers,
the experiment registry, and research-reset manifests. Every row retains its
source path, source hash, generation, evidence eligibility, raw identifiers,
raw edge/hypothesis/family/fingerprint, outcome, failure reason, and extraction
completeness.

Legacy scientific verdict and lifecycle/disposition text are retained in
separate fields when both exist; the derived index does not collapse those
axes.

Historical generations remain `HISTORICAL_INELIGIBLE`. Incomplete semantics are
`NEEDS_MANUAL_REVIEW`; the builder never invents P1 fields. It creates no
canonical observation, hypothesis, family, or backlog entry and changes no
historical file or verdict.

## Temporary legacy compatibility

The current Studio campaign-first authoring path remains available temporarily
and is not made dependent on the backlog in P2. This is compatibility behavior,
not the target operating model. Literature orchestration is P3, automated
hypothesis formulation is P4, and mandatory pre-PnL campaign linkage is P5.

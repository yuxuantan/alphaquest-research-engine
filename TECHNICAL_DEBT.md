# Prioritized Technical-Debt Backlog

Snapshot: 2026-08-31, Phase P0A engineering stabilization.

This backlog is an audit, not authorization to refactor strategy mechanics,
recertify packages, rerun campaigns, rewrite evidence, or remove historical
compatibility. Priority reflects scientific-correctness risk first and future
research throughput second.

## P0: engineering-baseline blockers

No known P0 item remains after the P0A changes, subject to the final clean
checkout verification. The prior sequential CI gate, incomplete test discovery,
ignored documentation target, stale execution example path, empty queue-lock
values, and tracked runtime/temp state are addressed in this phase.

## P1: correctness and reproducibility risk

1. **Bind the standalone execution system to governed certification identity.**
   `execution_system/databento_signal_engine.py` validates campaign YAML shape
   and warns about path ownership, but it is not the same fail-closed
   certification/preflight bridge used by governed campaign runtime. A future
   dedicated change should require current implementation and manifest hashes,
   approval identity, and an explicit active-package lifecycle before a live
   campaign strategy can start. Preserve the built-in diagnostic lane.

2. **Resolve the retained hash-drift expected failure only through governed
   recertification.** `tests/test_yush_range_reversal_v2.py` contains one strict
   xfail because a spawned replay correctly rechecks a hash-drifted retained
   package. The package must remain unavailable until its source, manifest,
   required tests, certification, validation, and manual mechanics approval are
   reconciled together. Do not remove the xfail in isolation.

3. **Close the active Yush preflight backlog through governed lifecycle
   actions.** Repository-wide `make preflight` currently rejects historical
   follow-up configs that predate current policy bindings and also reports a
   stale/mismatched v04 implementation certification. Preserve those frozen
   attempts and verdicts. Each executable successor requires the appropriate
   methodology attempt or certification version review, focused tests,
   recertification, fresh validation evidence, and manual mechanics approval;
   repository stabilization must not backfill the old files.

4. **Create a machine-readable workstation-qualification inventory.** The
   hermetic suite distinguishes optional browser/PDF/plotting dependencies and
   retired source from executable research, but private DBN/SCID and large-data
   qualification remains distributed across tests and runbooks. Record required
   data identity, expected skip/block reason, owner, and exact command without
   converting missing private data into a CI skip.

5. **Make authored-campaign preflight incremental.** `make preflight` performs a
   broad repository audit and can remain CPU-bound for many minutes as the
   campaign inventory grows. Add content-addressed, fail-closed caching with
   differential parity tests; never cache across policy, code, config, dataset,
   certification, or approval hash changes.

6. **Add a repeatable lock-generation and Linux verification procedure.** P0A
   pins the complete Python 3.12.14 reference resolution and the Node/npm
   environment, but the Python constraints are still maintained manually and do
   not carry artifact hashes. Introduce a reviewed lock-generation command and
   verify it on the CI platform before dependency modernization.

## P2: maintainability and operational risk

1. **Decompose high-coupling modules behind parity tests.** Current line counts
   include approximately 13,954 lines in the standalone signal engine, 6,007 in
   the Studio API, 4,611 in factory service, 3,662 in follow-ups, 3,221 in
   campaign stages, and 2,879 in the bar backtest engine. Split by existing
   contracts and prove differential behavior before and after each extraction.

2. **Retire duplicate compatibility surfaces deliberately.** The React/FastAPI
   Studio is primary, while the Streamlit shell, legacy OpenAI API mode, legacy
   storage prefixes, report readers, and retired strategy source remain for
   migration or audit. Each removal needs usage evidence, route/artifact parity,
   a migration plan, and explicit approval; bulk deletion would damage lineage.

3. **Ratchet static analysis beyond fatal Ruff families.** The current gate
   catches parser/name failures only. Add rule families in small batches after
   cleaning the affected files, with no mass formatting of immutable evidence
   or strategy code mixed into functional changes.

4. **Add a supported-Python compatibility matrix or narrow the package claim.**
   Packaging declares Python 3.10+, while the reproducible qualification lane is
   Python 3.12.14. Either exercise supported minors independently or document a
   narrower supported range after compatibility review.

5. **Reduce the cost of tracked historical bulk without deleting evidence.**
   Large archived generations, datasets, and immutable run evidence materially
   increase clone and audit cost. Any future object-store or Git LFS migration
   must preserve hashes, manifests, offline auditability, and historical paths
   or verified redirects.

## P3: non-urgent quality improvements

1. Extend documentation validation from file existence to anchors and selected
   generated-command examples. Keep the deliberate exclusion of the very large
   historical full guide documented.
2. Add summary timing telemetry for CI jobs and the slowest test modules so
   throughput work is evidence-led.
3. Consolidate repeated compatibility terminology after the corresponding
   lifecycle is actually retired; naming cleanup alone is not a correctness
   improvement.

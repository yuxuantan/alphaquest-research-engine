# Sequential variants and mandatory mechanics review

Status: accepted, superseding the new-campaign portions of the governance-v2 five-variant protocol.

New Studio campaigns publish one initial variant. A campaign may contain at most five variants, but variant `vNN` can be authored only after `vNN-1` has a current hash-bound manual mechanics approval and a complete terminal `FAIL` result. The expansion record binds the new variant to the predecessor result path and SHA-256, failure analysis, author, and timestamp. Prior variant configs are byte-compared during installation and cannot be changed.

When the next slot unlocks, Studio reads the first failed criterion from the immutable predecessor `ResultBundleV2` and uses its stage, metric, actual value, threshold, and reason to rank the still-unused certified risk/exit structures. This is failure-informed variant selection, not retroactive relabeling: the proposal requires explicit researcher confirmation plus an 80-character analysis and is frozen as a new test before it produces any result.

Before performance testing, the researcher must compare a fixed deterministic sample against charting software using declared default parameters: 5 random entries with seed 0 (or every entry if fewer than 5 exist), plus the first, last, best, worst, forced-flatten, same-bar ambiguity, warning, and strategy-edge-case categories. Every sampled entry must be marked correct and all automated checks must pass. Review approves implementation fidelity only, never profitability.

Historical `PASS` or `FAIL` records without this proof are soft-archived. Their evidence remains on disk and is catalogued in `research_artifacts/governance/unreviewed_verdict_archive.json`, but the records are excluded from active verdict, candidate, failure, and review surfaces. Their scientific state is `NEEDS MANUAL REVIEW` until separately revalidated; the historical verdict is never silently rewritten or deleted.

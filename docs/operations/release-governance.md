# Branch, Integration, And Engine-Release Governance

## Branch model

`main` is the sole stable/default branch. It contains only reviewed, integrated
work and is the only branch from which AlphaQuest engine baselines may be
tagged. A tag identifies an engine baseline; it does not approve a strategy or
authorize deployment.

All development uses temporary branches such as `feat/<topic>`, `fix/<topic>`,
or `docs/<topic>`. Rebase or merge `main` into the temporary branch as needed,
open a pull request, and delete the branch only after the merged history is no
longer needed. Do not create another permanent development branch.

Direct pushes, force pushes, history rewrites, and branch deletion are forbidden
by repository operating policy on `main`. Integration uses a pull request and the GitHub Actions check named
`Required integration gate`, which succeeds only after every independent lint,
documentation, smoke, governed-Python, execution-system, and Studio-UI job
succeeds.

## Single-developer GitHub enforcement boundary

AlphaQuest currently has one human developer and uses a private repository on
GitHub Free. That plan does not mechanically enforce the desired private-branch
protection rules. This is an accepted procedural-governance limitation for P0,
not evidence that GitHub is enforcing the rules below and not a reason to weaken
engine qualification.

The owner must apply this operating rule:

- changes are developed on feature/fix/documentation branches;
- `main` is updated through the normal pull-request merge action only after the
  exact PR head has a green `Required integration gate`;
- no external approval is required while there is one human developer;
- direct and force pushes, history rewrites, and branch deletion remain
  procedurally forbidden on `main`;
- known-good engine releases are created only from qualified `main` commits.

If a future repository plan supports enforcement, the recommended minimal
single-owner policy is:

- require a pull request before merging, with zero mandatory approvals so the
  sole owner is not forced to self-approve;
- dismiss stale approvals when new commits are pushed;
- require conversation resolution;
- require the `Required integration gate` status check and require the branch to
  be current before merge;
- apply the rules to administrators and disallow bypass;
- require linear history;
- disallow force pushes and branch deletion.

Do not represent the branch as protected until GitHub actually enforces those
settings. A future paid-plan upgrade is optional and is not required for the
current P0 baseline.

## Methodology changes

The repository-owned methodology is `config/research_settings.yaml`, implemented
and validated by `src/alphaquest/research/policy.py`. Every qualified baseline
records both files' SHA-256 values and the declared
`methodology_policy.version`.

A semantic methodology change must:

1. update the policy source and increment `methodology_policy.version`;
2. add focused methodology regression coverage and an ADR when causality,
   stages, promotion gates, or artifact lineage change;
3. run the complete methodology, causal/execution, and hermetic validation
   surfaces;
4. create new methodology-rerun attempts for research that adopts the new
   policy.

Never rewrite historical configs, evidence, hashes, or verdicts to claim they
used a newer methodology. A formatting-only change still produces a new file
hash and must be reviewed deliberately.

## Qualifying and releasing an engine baseline

An engine baseline may be created only from a clean `main` checkout after:

```bash
make validate
make qualify
```

The matching GitHub `Required integration gate` must also be successful.
`research_artifacts/engine_qualification.json` must report:

- `engine_software_status: PASS` from a clean worktree;
- the exact clean Git commit and package/engine-contract versions;
- methodology version plus policy and implementation hashes;
- reference Python, Node, constraints, and packaging identity;
- canonical validation commands and passing test output.

This report is software qualification only. Remote release eligibility also
requires the successful integration gate on the exact main commit; it may not
be inferred from `engine_software_status`.

Run `make preflight` separately as research inventory preflight. It answers
whether authored campaigns/configurations are executable under their own
strategy hashes, mechanics approvals, data bindings, methodology identity,
lifecycle, and certification state. It remains fail-closed. A qualified engine
may coexist with stale, frozen, deprecated, awaiting-recertification, awaiting-
review, or unavailable campaigns. The release must report that result and must
not imply that any such campaign is research-ready or tradeable.

The first P0 identifier is reserved as `engine-v0.1.0-p0`. Create it only after
the qualified commit is merged to `main`. Use an annotated tag, create a GitHub
release from that tag, and attach the JSON and Markdown qualification reports.
The tag and release commit must equal the report's `git_commit`. Qualification
reports are replaceable local outputs because committing a report into the
commit it identifies would be self-referential. Attach both reports to the
GitHub release as durable release assets.

If engine qualification, remote CI, cleanliness, or identity reconciliation is
unresolved, do not create or push the tag. A research inventory preflight
failure does not invalidate engine software qualification; preserve and report
the research failure without altering its artifacts. The absence of paid
private-repository branch protection is the documented procedural limitation
above, not a P0 release blocker.

## Evidence identity

New run evidence records the engine contract and research-policy version/hash.
Resolve a run through `alphaquest artifacts find <run_uid>` and its immutable
metadata; do not infer its methodology from the current branch or a later tag.
The prioritized engineering backlog is maintained in `TECHNICAL_DEBT.md`.

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
on `main`. Integration uses a pull request and the GitHub Actions check named
`Required integration gate`, which succeeds only after every independent lint,
documentation, smoke, governed-Python, execution-system, and Studio-UI job
succeeds.

## Required GitHub protection

Protect `main` with the following minimal single-owner policy:

- require a pull request before merging, with zero mandatory approvals so the
  sole owner is not forced to self-approve;
- dismiss stale approvals when new commits are pushed;
- require conversation resolution;
- require the `Required integration gate` status check and require the branch to
  be current before merge;
- apply the rules to administrators and disallow bypass;
- require linear history;
- disallow force pushes and branch deletion.

If the repository plan cannot enforce this policy, do not represent the branch
as protected. Upgrade the private repository plan before declaring P0 branch
governance complete.

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
make smoke
# Run the methodology command in TEST_COMMANDS.md.
# Run the causal/execution command in TEST_COMMANDS.md.
make validate
make preflight
make qualify
```

The matching GitHub `Required integration gate` must also be successful.
`research_artifacts/engine_qualification.json` must report:

- `engine_software_status: PASS` from a clean worktree;
- the exact clean Git commit and package/engine-contract versions;
- methodology version plus policy and implementation hashes;
- reference Python, Node, constraints, and packaging identity;
- canonical validation commands and passing test output.

This report is software qualification only. Release eligibility additionally
requires the separate successful preflight and remote integration gate above;
neither may be inferred from `engine_software_status`.

The first P0 identifier is reserved as `engine-v0.1.0-p0`. Create it only after
the qualified commit is merged to `main`. Use an annotated tag, create a GitHub
release from that tag, and attach the JSON and Markdown qualification reports.
The tag and release commit must equal the report's `git_commit`.

If preflight, remote CI, protection, cleanliness, or identity reconciliation is
unresolved, do not create or push the tag. Record the blocker and retain the
candidate commit as unqualified.

## Evidence identity

New run evidence records the engine contract and research-policy version/hash.
Resolve a run through `alphaquest artifacts find <run_uid>` and its immutable
metadata; do not infer its methodology from the current branch or a later tag.
The prioritized engineering backlog is maintained in `TECHNICAL_DEBT.md`.

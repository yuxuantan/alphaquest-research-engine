# ES Local-Only Unused Entry Module Recheck - 2026-06-29

Verdict: FAIL

## Purpose

This continuation rechecks the current entry-module surface after the local-only inventory. The goal was to find any registered entry module that could support a compliant, non-duplicate, project-data-only ES campaign without reopening a failed family.

## Method

- Parsed `src/propstack/strategy_modules/entry/*.py` for class-level `name` values.
- Parsed active ES YAML under `campaigns/es_*` and generated ES YAML under `backtest-campaigns/es_*` for `module:` usage.
- Compared unused entry modules against local feature/cache availability and active failed ES families.
- Treated archived tests as historical context, not automatic duplicate blockers, consistent with the active-only duplicate policy.

## Result

- Entry modules with names found: 176.
- Unused entry modules after current ES YAML scan: 24.
- Eligible new project-data-only ES campaigns from unused modules: 0.

Detailed CSV: `research_artifacts/es_local_only_unused_entry_module_recheck_20260629.csv`.

## Key Findings

- NQ-side modules remain ineligible for this ES request unless explicitly converted into an ES campaign with a distinct ES-side thesis; the corresponding ES-side NQ/relative-value families have already failed.
- Quote-liquidity sweep remains data-gated because the current project does not contain the required TBBO quote/refill/spread/aggressive-imbalance fields.
- Credit-spread state remains data-gated because the usable ranked HY/IG OAS feature span starts in 2023 and cannot support the default staged WFA methodology.
- CBOE/VIX/put-call/correlation orderflow-confirmation wrappers are not new primary edges. They would be post-result confirmations on already failed CBOE state families unless explicitly approved as a rescue/reopen.
- Pure/filtered/inverse opening-range and RTH gap modules are duplicate expressions of active failed ORB/gap/overnight families.
- Remaining orderflow wrapper modules overlap signed-flow persistence, orderflow impulse/reversal, same-clock state-rank, low-toxicity, and recent-pocket families that have already failed or been explicitly duplicate-gated.

## Decision

No new campaign was launched. Under the current local-only constraint, the unused entry-module surface does not contain a compliant non-duplicate ES edge.

No `candidate_strategy_report.md` was created.

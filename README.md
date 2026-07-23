# AlphaQuest Research Engine

Institutional, fail-closed futures research and backtesting system. It separates authored hypotheses from generated evidence, enforces causal execution rules, and records every staged decision.

Start with [START_HERE.md](START_HERE.md), then choose the path that matches your work:

| Role | Start here |
| --- | --- |
| Researcher (no code) | [Research Studio](docs/getting-started/research-studio.md) |
| Researcher (expert CLI) | [First backtest](docs/getting-started/first-backtest.md) |
| Strategy author | [Campaign authoring](docs/research/campaign-authoring.md) |
| Engine developer | [Architecture](ARCHITECTURE.md) |
| Data engineer | [Data contracts](docs/data/data-contracts.md) |
| Reviewer | [Verdict semantics](docs/research/verdict-semantics.md) |
| Operator | [Runbook](docs/operations/runbook.md) |

## Core Model

```text
campaign = one economic edge
variant  = one predeclared mechanical expression
attempt  = one immutable original, validation, replication, data-refresh, methodology-rerun, pre-PnL-correction, or authorized-rescue definition
run      = zero or one immutable generated evidence record for that attempt
```

Governance-v2 attempts have a strict one-run maximum. Repeating an execution requires a new authored attempt ID and explicit parent lineage; historical runs are represented by unique `inferred_legacy` attempt records without rewriting their evidence or verdicts.

Active authored definitions live under `research/campaigns/active/`; closed definitions live under `research/campaigns/archive/`. Generated evidence lives under `research/evidence/runs/`. Use `views/workbench/` and the registry instead of browsing either archive directly.

## Quick Start

After an administrator completes [installation](docs/getting-started/installation.md), a researcher can double-click **`AlphaQuest Studio.command`**. No terminal, Python, or YAML editing is required inside the research workflow.

Studio's novice interface is a committed React application served by a local FastAPI process. It binds only to the workstation, works without Node.js or a frontend build at runtime, and uses the separate durable Python worker for long research jobs. Except for explicitly enabled optional AI drafting, the Studio workflow does not require an external web service.

Administrator setup:

```bash
make studio-setup
make smoke
```

Studio is the novice path. It guides source declaration, duplicate review, governed data intake, execution rules, five frozen variants, mechanics approval, staged execution, and result review. Unsupported intrabar or custom mechanics become a durable `NEEDS MANUAL REVIEW` engineering handoff; Studio never approximates them with bars.

Run the isolated synthetic tutorial from Studio, or use the expert command:

```bash
make tutorial
```

## Daily Commands

These are expert/operator interfaces; researchers do not need them to use Studio.

```bash
alphaquest research search --symbol ES --state closed --limit 20
alphaquest campaign show es_video_aoi_lvn_orderflow_playbook
alphaquest campaign show es_video_aoi_lvn_orderflow_playbook --explain --run <run_uid>
alphaquest campaign validate <campaign_id>
make preflight
make test
make qualify
```

## Repository Map

| Path | Purpose |
| --- | --- |
| `src/alphaquest/` | Engine and reusable library code |
| `src/alphaquest/studio/web_assets/` | Committed, runtime-ready Research Studio web bundle |
| `studio-ui/` | React/TypeScript source used only when developers rebuild the web bundle |
| `research/campaigns/active/` | Active authored research definitions |
| `research/drafts/` | Incomplete Studio drafts outside active discovery |
| `research/datasets/` | Governed Studio dataset manifests and canonical bars |
| `research/handoffs/` | Unsupported mechanics awaiting certified engineering |
| `research/campaigns/archive/` | Closed authored research definitions |
| `tests/` | Engine, methodology, strategy, and regression tests |
| `data/` | Raw, reference, external, and generated market data |
| `research/evidence/runs/` | Immutable generated staged evidence |
| `catalogs/` | Rebuildable SQLite registry and exports |
| `views/` | Generated human-facing research navigation |
| `research_artifacts/` | Durable audits and decisions |
| `apps/` | Legacy/expert interactive launch surfaces; the novice Studio runs through `alphaquest studio` |
| `execution_system/` | Separate execution bridge with its own README |
| `tools/` | Compatibility scripts; prefer the `alphaquest` CLI |

## Quality Contract

- Bar-close signals enter no earlier than the next bar.
- Ambiguous same-bar stop/target touches resolve pessimistically without ordered detail data.
- Costs, session rules, forced flattening, contract values, and roll rules are explicit.
- Time-series validation is contiguous or purged; final acceptance is locked.
- A passing result is only a candidate strategy pending independent review and incubation.
- Diagnostic or shortened stage sets resolve to `NEEDS MANUAL REVIEW` and cannot create candidate artifacts.

See the [documentation index](docs/README.md) for detailed workflows. The former monolithic guide is preserved as [full-guide.md](docs/reference/full-guide.md).

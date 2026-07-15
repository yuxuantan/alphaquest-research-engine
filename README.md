# AlphaQuest Research Engine

Institutional, fail-closed futures research and backtesting system. It separates authored hypotheses from generated evidence, enforces causal execution rules, and records every staged decision.

Start with [START_HERE.md](START_HERE.md), then choose the path that matches your work:

| Role | Start here |
| --- | --- |
| Researcher | [First backtest](docs/getting-started/first-backtest.md) |
| Strategy author | [Campaign authoring](docs/research/campaign-authoring.md) |
| Engine developer | [Architecture](ARCHITECTURE.md) |
| Data engineer | [Data contracts](docs/data/data-contracts.md) |
| Reviewer | [Verdict semantics](docs/research/verdict-semantics.md) |
| Operator | [Runbook](docs/operations/runbook.md) |

## Core Model

```text
campaign = one economic edge
variant  = one predeclared mechanical expression
attempt  = an original or explicitly authorized rescue definition
run      = immutable generated evidence for one fixed attempt
```

Authored definitions live under `campaigns/`. Generated evidence lives under `backtest-campaigns/`. Use `views/` and the registry for navigation instead of browsing the evidence store directly.

## Quick Start

```bash
make setup
make smoke
make research-workspace
alphaquest research status
```

Run the synthetic tutorial without touching real campaign evidence:

```bash
make tutorial
```

## Daily Commands

```bash
alphaquest research search --symbol ES --state closed --limit 20
alphaquest campaign show es_video_aoi_lvn_orderflow_playbook
alphaquest campaign validate <campaign_id>
make preflight
make test
make qualify
```

## Repository Map

| Path | Purpose |
| --- | --- |
| `src/alphaquest/` | Engine and reusable library code |
| `campaigns/` | Authored research definitions |
| `tests/` | Engine, methodology, strategy, and regression tests |
| `data/` | Raw, reference, external, and generated market data |
| `backtest-campaigns/` | Immutable generated staged evidence |
| `catalogs/` | Rebuildable SQLite registry and exports |
| `views/` | Generated human-facing research navigation |
| `research_artifacts/` | Durable audits and decisions |
| `apps/` | Interactive applications |
| `execution_system/` | Separate execution bridge with its own README |
| `tools/` | Compatibility scripts; prefer the `alphaquest` CLI |

## Quality Contract

- Bar-close signals enter no earlier than the next bar.
- Ambiguous same-bar stop/target touches resolve pessimistically without ordered detail data.
- Costs, session rules, forced flattening, contract values, and roll rules are explicit.
- Time-series validation is contiguous or purged; final acceptance is locked.
- A passing result is only a candidate strategy pending independent review and incubation.

See the [documentation index](docs/README.md) for detailed workflows. The former monolithic guide is preserved as [full-guide.md](docs/reference/full-guide.md).

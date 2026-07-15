# Repository Navigation Uses Generated Views And A Supported CLI

## Context

The repository contains hundreds of campaigns, thousands of runs, and large durable evidence collections. Direct filesystem browsing made routine research state difficult to understand and encouraged users to infer meaning from folder names.

## Decision

- Authored campaign and generated evidence paths remain stable.
- SQLite is the operational index; CSV and Markdown views are disposable projections.
- `alphaquest` is the supported command interface.
- `views/` is the supported filesystem navigation interface.
- Historical tools and tests keep stable paths and receive generated categorized indexes instead of bulk relocation.
- New artifacts use a centrally validated structured store.

## Consequences

The repository can grow without expanding the normal browsing surface. Generated views must identify their build timestamp and source registry. Users must rebuild the workspace after source or run changes. Historical flat paths remain until a separately audited migration can preserve every reference.

## Verification

- registry and view tests
- CLI search and scaffold tests
- documentation-link checks
- synthetic tutorial execution
- full preflight and test suite

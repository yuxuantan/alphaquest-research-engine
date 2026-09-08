# YAML And JSON Schemas

These schemas provide editor validation and stable external contracts for campaign definitions and generated evidence. Runtime preflight and `alphaquest.research.schemas` remain authoritative and may enforce stricter cross-field methodology rules.

The `edge-backlog-*.schema.json` documents define the closed, append-only P2
observation, tentative-edge, human-decision, and downstream-link contracts.
Canonical records remain JSON files under `research/edge_backlog/`; schemas and
any catalog or registry representation do not replace those files as authority.

Schema changes require regression tests and an architecture decision when they alter execution, lineage, or verdict semantics.

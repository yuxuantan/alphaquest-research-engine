# Artifact Lineage

Each run records:

- a globally unique run UID and human-readable test run ID
- exactly one attempt ID, kind, provenance, and optional parent attempt
- campaign, variant, attempt, and parent-run lineage
- authored and effective config hashes
- input-data hash
- engine and research-policy versions
- stage results and critical artifact references

`catalogs/research_registry.sqlite` indexes this lineage. `views/` and CSV exports are disposable projections. Generated evidence remains under its compatibility path until a reviewed migration updates every writer and historical reference.

Use `alphaquest artifacts find <run_uid>` to resolve an opaque run. Do not infer lineage from folder names alone.

Historical runs without explicit authored attempt identity are indexed as unique `inferred_legacy` attempts, one per run. This derived registry lineage never changes the historical run directory or recorded terminal verdict. Ambiguous historical summaries remain `NEEDS MANUAL REVIEW`.

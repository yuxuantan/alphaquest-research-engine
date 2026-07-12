# Artifact Lineage

Each run records:

- a globally unique run UID and human-readable test run ID
- campaign, variant, attempt, and parent-run lineage
- authored and effective config hashes
- input-data hash
- engine and research-policy versions
- stage results and critical artifact references

`catalogs/research_registry.sqlite` indexes this lineage. `views/` and CSV exports are disposable projections. Generated evidence remains under its compatibility path until a reviewed migration updates every writer and historical reference.

Use `propstack artifacts find <run_uid>` to resolve an opaque run. Do not infer lineage from folder names alone.

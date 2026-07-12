# Research Registry

`research_registry.sqlite` is the rebuildable operational index over authored campaign definitions and generated evidence. It is not research evidence itself and is excluded from Git.

Rebuild it with `make research-registry`. The command first refreshes definition indexes, then writes portable table exports under `catalogs/exports/` and one flat definition index per campaign under `catalogs/definitions/`.

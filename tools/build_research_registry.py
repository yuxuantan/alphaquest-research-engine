from __future__ import annotations

import argparse
from pathlib import Path

from alphaquest.research.definitions import write_definition_manifests
from alphaquest.research.registry import build_registry, export_registry_csvs, generate_views
from alphaquest.research.storage import display_path, load_storage_layout


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the institutional research registry and navigation views.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--database", default="catalogs/research_registry.sqlite")
    parser.add_argument("--campaign-root", action="append", dest="campaign_roots")
    parser.add_argument("--definition-index-root", default="catalogs/definitions")
    parser.add_argument("--run-root", action="append", dest="run_roots")
    parser.add_argument("--research-artifact-root")
    parser.add_argument("--views")
    parser.add_argument("--exports", default="catalogs/exports")
    parser.add_argument("--no-views", action="store_true")
    parser.add_argument("--no-exports", action="store_true")
    args = parser.parse_args()

    layout = load_storage_layout(args.project_root)
    campaign_roots = args.campaign_roots or [display_path(path, layout.project_root) for path in layout.campaign_roots]
    run_roots = args.run_roots or [display_path(path, layout.project_root) for path in layout.evidence_roots]
    artifact_root = args.research_artifact_root or display_path(layout.research_artifact_root, layout.project_root)
    views_root = args.views or display_path(layout.views_root, layout.project_root)

    definition_totals: dict[str, int] = {}
    for campaign_root in campaign_roots:
        result = write_definition_manifests(
            campaign_root,
            project_root=args.project_root,
            output_root=args.definition_index_root,
            apply=True,
        )
        for key, value in result.items():
            definition_totals[key] = definition_totals.get(key, 0) + value
    counts = {f"definition_{key}": value for key, value in definition_totals.items()}
    counts.update(build_registry(
        project_root=args.project_root,
        database_path=args.database,
        campaign_roots=campaign_roots,
        run_roots=run_roots,
        research_artifact_root=artifact_root,
    ))
    if not args.no_exports:
        counts.update({f"export_{key}": value for key, value in export_registry_csvs(
            project_root=args.project_root, database_path=args.database, output_root=args.exports
        ).items()})
    if not args.no_views:
        counts.update({f"view_{key}": value for key, value in generate_views(
            project_root=args.project_root, database_path=args.database, output_root=views_root
        ).items()})
    database = Path(args.project_root) / args.database
    print(f"{database}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

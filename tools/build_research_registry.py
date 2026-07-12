from __future__ import annotations

import argparse
from pathlib import Path

from propstack.research.definitions import write_definition_manifests
from propstack.research.registry import build_registry, export_registry_csvs, generate_views


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the institutional research registry and navigation views.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--database", default="catalogs/research_registry.sqlite")
    parser.add_argument("--campaign-root", default="campaigns")
    parser.add_argument("--definition-index-root", default="catalogs/definitions")
    parser.add_argument("--run-root", default="backtest-campaigns")
    parser.add_argument("--research-artifact-root", default="research_artifacts")
    parser.add_argument("--views", default="views")
    parser.add_argument("--exports", default="catalogs/exports")
    parser.add_argument("--no-views", action="store_true")
    parser.add_argument("--no-exports", action="store_true")
    args = parser.parse_args()

    counts = {
        f"definition_{key}": value
        for key, value in write_definition_manifests(
            args.campaign_root,
            project_root=args.project_root,
            output_root=args.definition_index_root,
            apply=True,
        ).items()
    }
    counts.update(build_registry(
        project_root=args.project_root,
        database_path=args.database,
        campaign_root=args.campaign_root,
        run_root=args.run_root,
        research_artifact_root=args.research_artifact_root,
    ))
    if not args.no_exports:
        counts.update({f"export_{key}": value for key, value in export_registry_csvs(
            project_root=args.project_root, database_path=args.database, output_root=args.exports
        ).items()})
    if not args.no_views:
        counts.update({f"view_{key}": value for key, value in generate_views(
            project_root=args.project_root, database_path=args.database, output_root=args.views
        ).items()})
    database = Path(args.project_root) / args.database
    print(f"{database}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

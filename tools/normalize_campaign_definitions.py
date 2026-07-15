from __future__ import annotations

import argparse

from alphaquest.research.definitions import write_definition_manifests
from alphaquest.research.storage import display_path, load_storage_layout


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create flat, generated indexes over authored variant and rescue config trees."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--campaign-root", action="append", dest="campaign_roots")
    parser.add_argument("--output-root", default="catalogs/definitions")
    parser.add_argument("--apply", action="store_true", help="Write manifests; default is dry-run.")
    args = parser.parse_args()
    layout = load_storage_layout(args.project_root)
    campaign_roots = args.campaign_roots or [
        display_path(path, layout.project_root) for path in layout.campaign_roots
    ]
    counts: dict[str, int] = {}
    for campaign_root in campaign_roots:
        result = write_definition_manifests(
            campaign_root,
            project_root=args.project_root,
            output_root=args.output_root,
            apply=args.apply,
        )
        for key, value in result.items():
            counts[key] = counts.get(key, 0) + value
    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(f"{mode}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

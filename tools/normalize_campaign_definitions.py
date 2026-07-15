from __future__ import annotations

import argparse

from alphaquest.research.definitions import write_definition_manifests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create flat, generated indexes over authored variant and rescue config trees."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--campaign-root", default="campaigns")
    parser.add_argument("--output-root", default="catalogs/definitions")
    parser.add_argument("--apply", action="store_true", help="Write manifests; default is dry-run.")
    args = parser.parse_args()
    counts = write_definition_manifests(
        args.campaign_root,
        project_root=args.project_root,
        output_root=args.output_root,
        apply=args.apply,
    )
    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(f"{mode}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

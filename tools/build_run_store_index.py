from __future__ import annotations

import argparse

from alphaquest.research.run_store import build_run_store_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the date-partitioned opaque run-store compatibility index.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--database", default="catalogs/research_registry.sqlite")
    parser.add_argument("--output-root", default="run-store/generated")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    counts = build_run_store_index(
        args.database, project_root=args.project_root, output_root=args.output_root, apply=args.apply
    )
    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(f"{mode}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

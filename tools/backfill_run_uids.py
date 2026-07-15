from __future__ import annotations

import argparse

from alphaquest.research.run_store import backfill_run_uids
from alphaquest.research.storage import display_path, load_storage_layout


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill globally unique IDs into legacy generated run roots.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-root", action="append", dest="run_roots")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    layout = load_storage_layout(args.project_root)
    run_roots = args.run_roots or [display_path(path, layout.project_root) for path in layout.evidence_roots]
    counts: dict[str, int] = {}
    for run_root in run_roots:
        result = backfill_run_uids(run_root, project_root=args.project_root, apply=args.apply)
        for key, value in result.items():
            counts[key] = counts.get(key, 0) + value
    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(f"{mode}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 1 if counts["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

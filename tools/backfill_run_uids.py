from __future__ import annotations

import argparse

from alphaquest.research.run_store import backfill_run_uids


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill globally unique IDs into legacy generated run roots.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-root", default="backtest-campaigns")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    counts = backfill_run_uids(args.run_root, project_root=args.project_root, apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(f"{mode}: " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 1 if counts["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

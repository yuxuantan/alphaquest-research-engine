from __future__ import annotations

import argparse

from alphaquest.research.catalog import catalog_rows, write_run_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CSV catalog of generated campaign run summaries.")
    parser.add_argument("--root", default="backtest-campaigns", help="Generated campaign evidence root.")
    parser.add_argument("--out", default="research_artifacts/run_catalog.csv", help="Output CSV path.")
    args = parser.parse_args()

    out = write_run_catalog(args.root, args.out)
    print(f"{out} rows={len(catalog_rows(args.root))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

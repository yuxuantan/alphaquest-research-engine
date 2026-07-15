from __future__ import annotations

import argparse

from alphaquest.research.catalog import catalog_rows, write_run_catalog
from alphaquest.research.storage import display_path, load_storage_layout


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CSV catalog of generated campaign run summaries.")
    parser.add_argument("--root", help="Generated campaign evidence root.")
    parser.add_argument("--out", default="research_artifacts/run_catalog.csv", help="Output CSV path.")
    args = parser.parse_args()

    layout = load_storage_layout()
    run_root = args.root or display_path(layout.evidence_roots[0], layout.project_root)
    out = write_run_catalog(run_root, args.out)
    print(f"{out} rows={len(catalog_rows(run_root))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

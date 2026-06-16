from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re
import urllib.request


ALFRED_RELEASES = {
    "employment_situation": {
        "rid": 50,
        "release_name": "Employment Situation",
        "source_url": "https://alfred.stlouisfed.org/release/downloaddates?rid=50",
    },
    "cpi": {
        "rid": 10,
        "release_name": "Consumer Price Index",
        "source_url": "https://alfred.stlouisfed.org/release/downloaddates?rid=10",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CPI and Employment Situation release-date calendar.")
    parser.add_argument("--start-date", default="2011-01-03")
    parser.add_argument("--end-date", default="2026-06-09")
    parser.add_argument("--output", default="data/external/bls_macro_release_dates_20110103_20260609.csv")
    args = parser.parse_args()

    rows = build_calendar(date.fromisoformat(args.start_date), date.fromisoformat(args.end_date))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "release_date",
                "release_time",
                "release_type",
                "release_name",
                "scheduled",
                "source",
                "source_url",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} BLS release rows to {output}")
    return 0


def build_calendar(start: date, end: date) -> list[dict[str, str]]:
    rows = []
    for release_type, meta in ALFRED_RELEASES.items():
        text = _fetch_release_dates(int(meta["rid"]))
        for release_date in _parse_release_dates(text):
            if not start <= release_date <= end:
                continue
            rows.append(
                {
                    "release_date": release_date.isoformat(),
                    "release_time": "08:30:00",
                    "release_type": release_type,
                    "release_name": str(meta["release_name"]),
                    "scheduled": "true",
                    "source": "alfred_st_louis_fed_bls_release_dates",
                    "source_url": str(meta["source_url"]),
                    "notes": "release date known before RTH; release value/surprise not used by strategy",
                }
            )
    rows.sort(key=lambda row: (row["release_date"], row["release_type"]))
    return rows


def _fetch_release_dates(rid: int) -> str:
    url = f"https://alfred.stlouisfed.org/release/downloaddates?ff=txt&rid={rid}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def _parse_release_dates(text: str) -> list[date]:
    out = []
    for line in text.splitlines():
        value = line.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            out.append(date.fromisoformat(value))
    return out


if __name__ == "__main__":
    raise SystemExit(main())

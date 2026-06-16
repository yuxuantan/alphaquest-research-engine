from __future__ import annotations

import argparse
import csv
from datetime import date
from html.parser import HTMLParser
import re
from pathlib import Path
import urllib.request


FED_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FED_HISTORICAL_URL = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = " ".join(data.split())
        if stripped:
            self.text.append(stripped)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scheduled FOMC decision-date calendar from Fed pages.")
    parser.add_argument("--start-year", type=int, default=2011)
    parser.add_argument("--end-date", default="2026-06-09")
    parser.add_argument(
        "--out",
        default="data/external/fomc_scheduled_decision_dates_20110101_20260609.csv",
    )
    args = parser.parse_args()

    end_date = date.fromisoformat(args.end_date)
    rows = build_calendar(args.start_year, end_date)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "event_date",
                "event_time",
                "event_type",
                "scheduled",
                "source_year",
                "source_url",
                "source_label",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} scheduled FOMC decision dates to {out}")
    return 0


def build_calendar(start_year: int, end_date: date) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current_year_rows = _current_calendar_rows(end_date.year)
    for year in range(start_year, end_date.year + 1):
        if year >= 2021:
            rows.extend(row for row in current_year_rows if int(row["source_year"]) == year)
        else:
            rows.extend(_historical_year_rows(year))
    deduped = {}
    for row in rows:
        event_date = date.fromisoformat(str(row["event_date"]))
        if event_date > end_date:
            continue
        deduped[str(row["event_date"])] = row
    return [deduped[key] for key in sorted(deduped)]


def _current_calendar_rows(max_year: int) -> list[dict[str, object]]:
    html = _fetch(FED_CALENDAR_URL)
    rows = []
    panel_pattern = re.compile(
        r"<h4>\s*<a[^>]*>\s*(\d{4}) FOMC Meetings\s*</a>\s*</h4>(.*?)(?=<h4>|</main>|Last Update)",
        re.IGNORECASE | re.DOTALL,
    )
    for year_text, panel_html in panel_pattern.findall(html):
        year = int(year_text)
        if year > max_year:
            continue
        # The Fed's current page uses one row per meeting with month/date classes.
        for row_html in re.split(r'<div[^>]*class="[^"]*row fomc-meeting[^"]*"[^>]*>', panel_html)[1:]:
            text = _html_text(row_html)
            if "notation vote" in text.lower() or "cancel" in text.lower():
                continue
            month_match = re.search(r'<strong>\s*([A-Za-z/]+)\s*</strong>', row_html, re.IGNORECASE)
            date_match = re.search(
                r'class="[^"]*fomc-meeting__date[^"]*"[^>]*>\s*([^<]+?)\s*</div>',
                row_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not month_match or not date_match:
                continue
            month_text = month_match.group(1).strip()
            date_text = date_match.group(1).strip()
            try:
                decision_date = _decision_date(year, month_text, date_text)
            except ValueError:
                continue
            rows.append(_row(decision_date, year, FED_CALENDAR_URL, f"{month_text} {date_text}"))
    if rows:
        return rows

    # Fallback for parser changes: use visible text from the page.
    return _text_calendar_rows(html, FED_CALENDAR_URL)


def _historical_year_rows(year: int) -> list[dict[str, object]]:
    url = FED_HISTORICAL_URL.format(year=year)
    html = _fetch(url)
    text = _html_text(html)
    rows = []
    pattern = re.compile(rf"^(.+?)\s+Meeting\s+-\s+{year}$", re.IGNORECASE)
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        label = " ".join(match.group(1).split())
        lower = label.lower()
        if "unscheduled" in lower or "cancel" in lower or "conference call" in lower:
            continue
        try:
            month_text, date_text = label.split(maxsplit=1)
            decision_date = _decision_date(year, month_text, date_text)
        except ValueError:
            continue
        rows.append(_row(decision_date, year, url, label))
    return rows


def _text_calendar_rows(html: str, source_url: str) -> list[dict[str, object]]:
    text = _html_text(html)
    rows = []
    current_year = None
    current_month = None
    for token in text.splitlines():
        year_match = re.match(r"^(\d{4}) FOMC Meetings$", token)
        if year_match:
            current_year = int(year_match.group(1))
            current_month = None
            continue
        if token.lower() in MONTHS or "/" in token and all(part.lower() in MONTHS for part in token.split("/")):
            current_month = token
            continue
        if current_year and current_month and re.match(r"^\d", token) and "released" not in token.lower():
            if "notation" in token.lower() or "cancel" in token.lower():
                continue
            try:
                decision_date = _decision_date(current_year, current_month, token)
            except ValueError:
                continue
            rows.append(_row(decision_date, current_year, source_url, f"{current_month} {token}"))
            current_month = None
    return rows


def _decision_date(year: int, month_text: str, date_text: str) -> date:
    date_text = date_text.replace("*", "").replace(",", "").strip()
    date_text = re.sub(r"\([^)]*\)", "", date_text).strip()
    month_parts = month_text.split("/")
    start_month = month_parts[0]
    end_month = month_parts[-1]
    if "-" in date_text:
        first, second = [part.strip() for part in date_text.split("-", 1)]
        second_match = re.match(r"([A-Za-z]+)?\s*(\d{1,2})$", second)
        if not second_match:
            raise ValueError(f"Cannot parse FOMC date: {month_text} {date_text}")
        explicit_month, day_text = second_match.groups()
        if explicit_month:
            end_month = explicit_month
        elif int(day_text) < int(re.search(r"\d{1,2}", first).group(0)) and len(month_parts) == 2:
            end_month = month_parts[1]
        month = _month_number(end_month)
        day = int(day_text)
    else:
        match = re.match(r"([A-Za-z]+)?\s*(\d{1,2})$", date_text)
        if not match:
            raise ValueError(f"Cannot parse FOMC date: {month_text} {date_text}")
        explicit_month, day_text = match.groups()
        month = _month_number(explicit_month or start_month)
        day = int(day_text)
    return date(year, month, day)


def _month_number(value: str) -> int:
    key = value.strip().lower()
    if key not in MONTHS:
        raise ValueError(f"Unknown month: {value}")
    return MONTHS[key]


def _row(event_date: date, year: int, source_url: str, label: str) -> dict[str, object]:
    return {
        "event_date": event_date.isoformat(),
        "event_time": "14:00:00",
        "event_type": "fomc_scheduled_decision",
        "scheduled": "true",
        "source_year": year,
        "source_url": source_url,
        "source_label": label,
        "notes": "Scheduled FOMC meeting decision date; unscheduled, cancelled, notation votes, and conference calls excluded.",
    }


def _html_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    return "\n".join(parser.text)


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


if __name__ == "__main__":
    raise SystemExit(main())

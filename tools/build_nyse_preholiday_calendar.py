from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path


HOLIDAY_NAMES = {
    "new_years_day": "New Year's Day",
    "mlk_day": "Martin Luther King Jr. Day",
    "washingtons_birthday": "Washington's Birthday",
    "good_friday": "Good Friday",
    "memorial_day": "Memorial Day",
    "juneteenth": "Juneteenth National Independence Day",
    "independence_day": "Independence Day",
    "labor_day": "Labor Day",
    "thanksgiving": "Thanksgiving Day",
    "christmas": "Christmas Day",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pre-holiday regular-session calendar for ES research.")
    parser.add_argument("--start-date", default="2011-01-03")
    parser.add_argument("--end-date", default="2026-06-09")
    parser.add_argument("--output", default="data/external/nyse_preholiday_regular_sessions_20110103_20260609.csv")
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    rows = preholiday_rows(start, end)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["signal_date", "holiday_date", "holiday_name", "regular_session", "source", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output}")


def preholiday_rows(start: date, end: date) -> list[dict]:
    holidays = scheduled_nyse_holidays(start.year, end.year)
    holiday_dates = {row["holiday_date"] for row in holidays}
    early_closes = nyse_early_closes(start.year, end.year, holiday_dates)
    rows = []
    for holiday in holidays:
        holiday_date = holiday["holiday_date"]
        signal_date = previous_regular_session(holiday_date, holiday_dates, early_closes)
        if start <= signal_date <= end:
            rows.append(
                {
                    "signal_date": signal_date.isoformat(),
                    "holiday_date": holiday_date.isoformat(),
                    "holiday_name": holiday["holiday_name"],
                    "regular_session": "true",
                    "source": "deterministic_nyse_holiday_rules",
                    "notes": "last regular session before full NYSE holiday; early-close sessions excluded to match local RTH cache",
                }
            )
    rows.sort(key=lambda row: (row["signal_date"], row["holiday_date"]))
    return rows


def scheduled_nyse_holidays(start_year: int, end_year: int) -> list[dict]:
    rows = []
    for year in range(start_year, end_year + 1):
        entries = [
            ("new_years_day", observed(date(year, 1, 1))),
            ("mlk_day", nth_weekday(year, 1, 0, 3)),
            ("washingtons_birthday", nth_weekday(year, 2, 0, 3)),
            ("good_friday", good_friday(year)),
            ("memorial_day", last_weekday(year, 5, 0)),
            ("independence_day", observed(date(year, 7, 4))),
            ("labor_day", nth_weekday(year, 9, 0, 1)),
            ("thanksgiving", nth_weekday(year, 11, 3, 4)),
            ("christmas", observed(date(year, 12, 25))),
        ]
        if year >= 2022:
            entries.append(("juneteenth", observed(date(year, 6, 19))))
        for key, holiday_date in entries:
            if holiday_date.weekday() < 5:
                rows.append({"holiday_date": holiday_date, "holiday_name": HOLIDAY_NAMES[key]})
    return rows


def nyse_early_closes(start_year: int, end_year: int, holidays: set[date]) -> set[date]:
    closes: set[date] = set()
    for year in range(start_year, end_year + 1):
        candidates = [
            nth_weekday(year, 11, 3, 4) + timedelta(days=1),
            date(year, 12, 24),
            date(year, 7, 3),
        ]
        for value in candidates:
            if value.weekday() < 5 and value not in holidays:
                closes.add(value)
    return closes


def previous_regular_session(value: date, holidays: set[date], early_closes: set[date]) -> date:
    current = value - timedelta(days=1)
    while current.weekday() >= 5 or current in holidays or current in early_closes:
        current -= timedelta(days=1)
    return current


def observed(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def good_friday(year: int) -> date:
    return easter_sunday(year) - timedelta(days=2)


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic monthly VIX derivatives expiration signal calendar.")
    parser.add_argument("--start-date", default="2011-01-03")
    parser.add_argument("--end-date", default="2026-06-09")
    parser.add_argument("--output", default="data/external/vix_expiration_sessions_20110103_20260609.csv")
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    rows = vix_expiration_rows(start, end)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "signal_date",
                "vix_expiration_date",
                "spx_reference_expiration_date",
                "calendar_month",
                "signal_type",
                "regular_session",
                "source",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output}")


def vix_expiration_rows(start: date, end: date) -> list[dict]:
    holidays = nyse_holidays(start.year, end.year + 1)
    early_closes = nyse_early_closes(start.year, end.year + 1, holidays)
    rows: list[dict] = []
    for year in range(start.year, end.year + 1):
        for month in range(1, 13):
            next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
            spx_expiration = standard_spx_expiration_session(next_year, next_month, holidays, early_closes)
            raw_vix_expiration = spx_expiration - timedelta(days=30)
            vix_expiration = regular_session_on_or_before(raw_vix_expiration, holidays, early_closes)
            signal_dates = {
                "previous_regular_session": previous_regular_session(vix_expiration, holidays, early_closes),
                "vix_expiration_session": vix_expiration,
                "next_regular_session": next_regular_session(vix_expiration, holidays, early_closes),
            }
            for signal_type, signal_date in signal_dates.items():
                if start <= signal_date <= end:
                    rows.append(
                        {
                            "signal_date": signal_date.isoformat(),
                            "vix_expiration_date": vix_expiration.isoformat(),
                            "spx_reference_expiration_date": spx_expiration.isoformat(),
                            "calendar_month": f"{year}-{month:02d}",
                            "signal_type": signal_type,
                            "regular_session": "true",
                            "source": "deterministic_vix_standard_expiration_rule",
                            "notes": "monthly VIX expiration is 30 calendar days before the following-month SPX standard expiration session; dates shifted to prior regular session if needed; early closes excluded",
                        }
                    )
    rows.sort(key=lambda item: (item["signal_date"], item["signal_type"]))
    return rows


def standard_spx_expiration_session(year: int, month: int, holidays: set[date], early_closes: set[date]) -> date:
    third_friday = nth_weekday(year, month, 4, 3)
    return regular_session_on_or_before(third_friday, holidays, early_closes)


def regular_session_on_or_before(value: date, holidays: set[date], early_closes: set[date]) -> date:
    current = value
    while current.weekday() >= 5 or current in holidays or current in early_closes:
        current -= timedelta(days=1)
    return current


def previous_regular_session(value: date, holidays: set[date], early_closes: set[date]) -> date:
    current = value - timedelta(days=1)
    while current.weekday() >= 5 or current in holidays or current in early_closes:
        current -= timedelta(days=1)
    return current


def next_regular_session(value: date, holidays: set[date], early_closes: set[date]) -> date:
    current = value + timedelta(days=1)
    while current.weekday() >= 5 or current in holidays or current in early_closes:
        current += timedelta(days=1)
    return current


def nyse_holidays(start_year: int, end_year: int) -> set[date]:
    holidays: set[date] = set()
    for year in range(start_year, end_year + 1):
        holidays.add(observed(date(year, 1, 1)))
        holidays.add(nth_weekday(year, 1, 0, 3))
        holidays.add(nth_weekday(year, 2, 0, 3))
        holidays.add(good_friday(year))
        holidays.add(last_weekday(year, 5, 0))
        if year >= 2022:
            holidays.add(observed(date(year, 6, 19)))
        holidays.add(observed(date(year, 7, 4)))
        holidays.add(nth_weekday(year, 9, 0, 1))
        holidays.add(nth_weekday(year, 11, 3, 4))
        holidays.add(observed(date(year, 12, 25)))
    holidays.update({date(2012, 10, 29), date(2012, 10, 30), date(2018, 12, 5), date(2025, 1, 9)})
    return {value for value in holidays if value.weekday() < 5}


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
    le = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * le) // 451
    month = (h + le - 7 * m + 114) // 31
    day = ((h + le - 7 * m + 114) % 31) + 1
    return date(year, month, day)


if __name__ == "__main__":
    main()

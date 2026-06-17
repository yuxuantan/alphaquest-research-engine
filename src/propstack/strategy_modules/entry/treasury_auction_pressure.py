from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TreasuryAuctionPressureEntry:
    name = "treasury_auction_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "treasury_auction_pressure")).lower()
        self.auction_scope = str(params.get("auction_scope", "all_coupon")).lower()
        self.signal_time = parse_time(params.get("signal_time", "13:05:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.direction = _direction(params.get("direction", "short"))
        self.event_calendar_csv = Path(str(params.get("event_calendar_csv", "")))
        self.calendar_by_date = self._load_calendar(self.event_calendar_csv)
        self.state_by_day: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_day.setdefault(session_date, {"signaled": False})
        if state["signaled"]:
            return None

        event_row = self.calendar_by_date.get(session_date)
        if event_row is None or not self._scope_matches(event_row):
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.signal_time.hour,
            minute=self.signal_time.minute,
            second=self.signal_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "lou_yan_zhang_2013_treasury_auction_pressure",
            "setup_mode": self.setup_mode,
            "treasury_auction_signal_timestamp": signal_timestamp,
            "treasury_auction_session_date": session_date.isoformat(),
            "treasury_auction_scope": self.auction_scope,
            "treasury_auction_direction": self.direction,
            "treasury_coupon_count": event_row["coupon_count"],
            "treasury_note_count": event_row["note_count"],
            "treasury_bond_count": event_row["bond_count"],
            "treasury_auction_terms": event_row["terms"],
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=self.direction,
            level_type=f"treasury_auction_{self.auction_scope}_{self.direction}",
            swept_level=float(bar["open"]),
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "auction_scope": self.auction_scope,
                "direction": self.direction,
                "coupon_count": event_row["coupon_count"],
                "terms": event_row["terms"],
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _scope_matches(self, row: dict) -> bool:
        if self.auction_scope == "all_coupon":
            return row["coupon_count"] > 0
        if self.auction_scope == "note_only":
            return row["note_count"] > 0
        if self.auction_scope == "bond_only":
            return row["bond_count"] > 0
        raise ValueError("auction_scope must be all_coupon, note_only, or bond_only.")

    def _load_calendar(self, path: Path) -> dict[date, dict]:
        if not path:
            raise ValueError("event_calendar_csv is required.")
        if not path.exists():
            raise FileNotFoundError(f"Treasury auction calendar does not exist: {path}")
        df = pd.read_csv(path)
        required = {"signal_date", "coupon_count", "note_count", "bond_count", "terms"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Treasury auction calendar missing column(s): {sorted(missing)}")
        calendar: dict[date, dict] = {}
        for raw in df.to_dict("records"):
            signal_date = pd.Timestamp(raw["signal_date"]).date()
            if signal_date in calendar:
                raise ValueError(f"Duplicate Treasury auction signal date: {signal_date}")
            calendar[signal_date] = {
                "signal_date": signal_date.isoformat(),
                "coupon_count": int(raw["coupon_count"]),
                "note_count": int(raw["note_count"]),
                "bond_count": int(raw["bond_count"]),
                "terms": str(raw.get("terms", "")),
            }
        return calendar

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")


def _direction(value) -> str:
    out = str(value).lower()
    if out not in {"long", "short"}:
        raise ValueError("direction must be long or short.")
    return out


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()

from __future__ import annotations

from pathlib import Path
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class CftcTffHedgingPressureEntry:
    name = "cftc_tff_hedging_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.feature_file = Path(params.get("feature_file", "data/external/cftc_tff_hedging_pressure_features.csv"))
        self.feature_name = str(params.get("feature_name", "SPX_open_interest_chg13"))
        self.operator = str(params.get("operator", ">=")).strip()
        self.threshold = float(params.get("threshold", 25000.0))
        self.direction = str(params.get("direction", "long")).lower()
        self.entry_time = parse_time(params.get("entry_time", "11:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self.feature_by_date = _load_feature_by_date(self.feature_file, self.feature_name)
        if self.direction not in {"long", "short"}:
            raise ValueError("cftc_tff_hedging_pressure direction must be long or short.")
        if self.operator not in {">=", "<=", ">", "<"}:
            raise ValueError("cftc_tff_hedging_pressure operator must be one of >=, <=, >, <.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = pd.Timestamp(bar["session_date"]).normalize()
        state = self._state(session_date)
        if state["signaled"]:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() != self.entry_time:
            return None

        feature_value = self.feature_by_date.get(session_date)
        if feature_value is None or not math.isfinite(feature_value):
            return None
        if not _compare(feature_value, self.operator, self.threshold):
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "de_roon_nijman_veld_2000_hedging_pressure",
            "external_dataset": "cftc_tff_financial_futures_combined",
            "external_feature_file": str(self.feature_file),
            "feature_name": self.feature_name,
            "feature_operator": self.operator,
            "feature_threshold": self.threshold,
            "feature_value": feature_value,
            "feature_trade_date": session_date.date().isoformat(),
            "feature_availability_rule": "Tuesday CFTC TFF positions traded no earlier than following Monday RTH",
            "signal_timestamp": bar_close,
        }
        return Signal(
            direction=self.direction,
            level_type=f"cftc_tff_hedging_pressure_{self.feature_name}",
            swept_level=float(bar["close"]),
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "feature_name": self.feature_name,
                "feature_value": feature_value,
            },
            report_fields=report_fields,
        )


def _load_feature_by_date(path: Path, feature_name: str) -> dict[pd.Timestamp, float]:
    if not path.exists():
        raise FileNotFoundError(f"CFTC TFF feature file not found: {path}")
    frame = pd.read_csv(path, usecols=["trade_date", feature_name])
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame[feature_name] = pd.to_numeric(frame[feature_name], errors="coerce")
    frame = frame.dropna(subset=["trade_date"]).drop_duplicates("trade_date", keep="last")
    values = {}
    for row in frame[["trade_date", feature_name]].itertuples(index=False, name=None):
        trade_date, feature_value = row
        if pd.notna(feature_value):
            values[pd.Timestamp(trade_date)] = float(feature_value)
    return values


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    raise ValueError(f"Unsupported operator: {operator}")

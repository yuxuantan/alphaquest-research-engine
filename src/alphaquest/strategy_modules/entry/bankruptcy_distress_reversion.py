from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class BankruptcyDistressReversionEntry:
    name = "bankruptcy_distress_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.feature_file = Path(params.get("feature_file", "data/external/uscourts_bankruptcy_f2_quarterly_features.csv"))
        self.feature_name = str(params.get("feature_name", "total_ch11_yoy_pct"))
        self.operator = str(params.get("operator", ">=")).strip()
        self.threshold = float(params.get("threshold", 14.780168))
        self.direction = str(params.get("direction", "long")).lower()
        self.entry_time = parse_time(params.get("entry_time", "11:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.prior_return_filter = _normalize_prior_filter(params.get("prior_return_filter", "down"))
        self.stale_after_days = int(params.get("stale_after_days", 180))
        self.stop_pct = float(params.get("stop_pct", 0.03))
        self.target_r_multiple = float(params.get("target_r_multiple", 10.0))
        self.flatten_time = parse_time(params.get("flatten_time", "15:30:00"))
        self.feature_history = _load_feature_history(self.feature_file, self.feature_name)
        self.feature_dates = [item["effective_date"] for item in self.feature_history]
        self.state_by_day: dict = {}
        self.session_closes: dict[pd.Timestamp, float] = {}
        if self.direction not in {"long", "short"}:
            raise ValueError("bankruptcy_distress_reversion direction must be long or short.")
        if self.operator not in {">=", "<=", ">", "<"}:
            raise ValueError("bankruptcy_distress_reversion operator must be one of >=, <=, >, <.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stale_after_days <= 0:
            raise ValueError("stale_after_days must be greater than 0.")

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = pd.Timestamp(bar["session_date"]).normalize()
        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(session_date)

        signal = None
        if (
            not state["signaled"]
            and trades_today < self.max_trades_per_day
            and bar_close.time() == self.entry_time
        ):
            signal = self._signal(bar, session_date, bar_close)
            if signal is not None:
                state["signaled"] = True

        self.session_closes[session_date] = float(bar["close"])
        return signal

    def _signal(self, bar: pd.Series, session_date: pd.Timestamp, signal_timestamp: pd.Timestamp) -> Signal | None:
        feature = self._feature_asof(session_date)
        if feature is None:
            return None
        feature_value = feature["value"]
        if feature_value is None or not math.isfinite(feature_value):
            return None
        if not _compare(feature_value, self.operator, self.threshold):
            return None

        prior_return_pct = self._prior_session_return_pct(session_date)
        if prior_return_pct is None or not _prior_filter_matches(prior_return_pct, self.prior_return_filter):
            return None

        report_fields = {
            "academic_source_key": "bankruptcy_distress_risk_reversal",
            "external_dataset": "uscourts_bankruptcy_f2_quarterly",
            "external_feature_file": str(self.feature_file),
            "feature_name": self.feature_name,
            "feature_operator": self.operator,
            "feature_threshold": self.threshold,
            "feature_value": feature_value,
            "feature_period_end": feature["period_end"].date().isoformat(),
            "feature_effective_date": feature["effective_date"].date().isoformat(),
            "feature_availability_rule": "Quarter end plus 45 calendar days, moved to next weekday when needed",
            "prior_return_filter": self.prior_return_filter,
            "prior_session_return_pct": prior_return_pct,
            "signal_timestamp": signal_timestamp,
        }
        return Signal(
            direction=self.direction,
            level_type=f"bankruptcy_distress_reversion_{self.feature_name}",
            swept_level=float(bar["close"]),
            sweep_timestamp=signal_timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "feature_name": self.feature_name,
                "feature_value": feature_value,
                "prior_session_return_pct": prior_return_pct,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _feature_asof(self, session_date: pd.Timestamp) -> dict | None:
        idx = bisect_right(self.feature_dates, session_date) - 1
        if idx < 0:
            return None
        feature = self.feature_history[idx]
        if (session_date - feature["effective_date"]).days > self.stale_after_days:
            return None
        return feature

    def _prior_session_return_pct(self, session_date: pd.Timestamp) -> float | None:
        prior_dates = sorted(date for date in self.session_closes if date < session_date)
        if len(prior_dates) < 2:
            return None
        prev_prev_close = self.session_closes[prior_dates[-2]]
        prev_close = self.session_closes[prior_dates[-1]]
        if prev_prev_close <= 0:
            return None
        return (prev_close / prev_prev_close - 1.0) * 100.0


def _load_feature_history(path: Path, feature_name: str) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Bankruptcy F-2 feature file not found: {path}")
    frame = pd.read_csv(path, usecols=["period_end", "effective_date", feature_name])
    frame["period_end"] = pd.to_datetime(frame["period_end"], errors="coerce").dt.normalize()
    frame["effective_date"] = pd.to_datetime(frame["effective_date"], errors="coerce").dt.normalize()
    frame[feature_name] = pd.to_numeric(frame[feature_name], errors="coerce")
    frame = frame.dropna(subset=["period_end", "effective_date"]).sort_values("effective_date")
    rows = []
    for row in frame[["period_end", "effective_date", feature_name]].itertuples(index=False, name=None):
        period_end, effective_date, feature_value = row
        rows.append(
            {
                "period_end": pd.Timestamp(period_end),
                "effective_date": pd.Timestamp(effective_date),
                "value": float(feature_value) if pd.notna(feature_value) else math.nan,
            }
        )
    return rows


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


def _normalize_prior_filter(value) -> str:
    normalized = str(value).strip().lower()
    aliases = {"prior_down": "down", "prior_up": "up", "none": "any"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"down", "up", "any"}:
        raise ValueError("prior_return_filter must be one of down, up, any.")
    return normalized


def _prior_filter_matches(prior_return_pct: float, prior_filter: str) -> bool:
    if prior_filter == "down":
        return prior_return_pct < 0
    if prior_filter == "up":
        return prior_return_pct > 0
    return True

from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class PdhPdlVapAbsorptionSweepEntry:
    name = "pdh_pdl_vap_absorption_sweep"

    def __init__(self, params: dict):
        self.params = params
        self.start_time = parse_time(params.get("start_time", "09:30:00"))
        self.end_time = parse_time(params.get("end_time", "11:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 3))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.feature_prefix = str(params.get("feature_prefix", "intrabar"))
        self.min_pivots = int(params.get("min_pivots", 3))
        self.min_range_pct = float(params.get("min_range_pct", 0.002))
        self.max_vap_distance_pct = float(params.get("max_vap_distance_pct", 0.0005))
        self.min_absorption_delta = float(params.get("min_absorption_delta", 300.0))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            self.current_session_bars.append(bar.copy())
            return None

        pivots = self._formed_pivot_count()
        candidates = []
        if pivots >= self.min_pivots:
            if self.allow_short:
                short_signal = self._candidate_signal(bar, "short", pivots)
                if short_signal is not None:
                    candidates.append(short_signal)
            if self.allow_long:
                long_signal = self._candidate_signal(bar, "long", pivots)
                if long_signal is not None:
                    candidates.append(long_signal)

        self.current_session_bars.append(bar.copy())
        if not candidates:
            return None
        return min(candidates, key=lambda signal: pd.Timestamp(signal.reclaim_timestamp))

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.current_session = session_date
        self.current_session_bars = []

    def _candidate_signal(self, bar: pd.Series, direction: str, pivots: int) -> Signal | None:
        side = "long" if direction == "long" else "short"
        release_price = _finite_float(bar.get(self._col(side, "release_price")))
        release_offset = _finite_float(bar.get(self._col(side, "release_offset_seconds")))
        absorption_delta = _finite_float(bar.get(self._col(side, "delta")))
        session_open = _finite_float(bar.get(self._col(side, "session_open")))
        session_high = _finite_float(bar.get(self._col(side, "session_high")))
        session_low = _finite_float(bar.get(self._col(side, "session_low")))
        range_pct = _finite_float(bar.get(self._col(side, "session_range_pct")))
        vah = _finite_float(bar.get(self._col(side, "vap_vah")))
        val = _finite_float(bar.get(self._col(side, "vap_val")))
        poc = _finite_float(bar.get(self._col(side, "vap_poc")))
        no_lvn_between_va = _truthy_number(bar.get(self._col(side, "vap_no_lvn_between_value_area")))
        if (
            release_price is None
            or release_offset is None
            or absorption_delta is None
            or session_open is None
            or session_high is None
            or session_low is None
            or range_pct is None
            or vah is None
            or val is None
            or poc is None
            or not no_lvn_between_va
        ):
            return None
        if range_pct < self.min_range_pct:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(seconds=float(release_offset))
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        max_distance = session_open * self.max_vap_distance_pct
        sweep = self._sweep_status(bar, release_price, session_high, session_low)
        if sweep is None:
            return None
        if direction == "short":
            if absorption_delta < self.min_absorption_delta:
                return None
            profile_level = vah
            if abs(release_price - profile_level) > max_distance:
                return None
            sweep_high = session_high
            sweep_low = session_low
            delta_zone_low = _finite_float(bar.get(self._col(side, "delta_zone_low")))
            delta_zone_high = _finite_float(bar.get(self._col(side, "delta_zone_high")))
        else:
            if absorption_delta > -self.min_absorption_delta:
                return None
            profile_level = val
            if abs(release_price - profile_level) > max_distance:
                return None
            sweep_high = session_high
            sweep_low = session_low
            delta_zone_low = _finite_float(bar.get(self._col(side, "delta_zone_low")))
            delta_zone_high = _finite_float(bar.get(self._col(side, "delta_zone_high")))

        fields = {
            "setup_mode": "pdh_pdl_vap_absorption_sweep",
            "entry_mode": "intrabar",
            "entry_reference_price": release_price,
            "intrabar_entry_price": release_price,
            "intrabar_entry_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_timestamp": signal_timestamp,
            "reclaim_timestamp": signal_timestamp,
            "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "pivots_formed_before_entry": pivots,
            "min_pivots_required": self.min_pivots,
            "min_range_pct": self.min_range_pct,
            "session_range_pct_at_release": range_pct,
            "session_open_at_release": session_open,
            "session_high_at_release": session_high,
            "session_low_at_release": session_low,
            "prev_rth_high": sweep["prev_rth_high"],
            "prev_rth_low": sweep["prev_rth_low"],
            "swept_level": sweep["swept_level"],
            "sweep_high": sweep_high,
            "sweep_low": sweep_low,
            "sweep_reference": sweep["sweep_reference"],
            "swept_pdh": float(sweep["swept_pdh"]),
            "swept_pdl": float(sweep["swept_pdl"]),
            "profile_level_type": "developing_vap_vah" if direction == "short" else "developing_vap_val",
            "profile_level_price": profile_level,
            "profile_distance_points": abs(release_price - profile_level),
            "max_profile_distance_points": max_distance,
            "developing_vap_poc_at_release": poc,
            "developing_vap_vah_at_release": vah,
            "developing_vap_val_at_release": val,
            "developing_vap_no_lvn_between_value_area": float(no_lvn_between_va),
            "absorption_delta_4_ticks": absorption_delta,
            "absorption_delta_zone_low": delta_zone_low,
            "absorption_delta_zone_high": delta_zone_high,
            "min_absorption_delta": self.min_absorption_delta,
            "intrabar_release_offset_seconds": release_offset,
            "intrabar_source": "raw_sierra_scid_records",
        }
        return Signal(
            direction=direction,
            level_type=f"{sweep['sweep_reference']}_{fields['profile_level_type']}_absorption_sweep",
            swept_level=sweep["swept_level"],
            sweep_timestamp=timestamp,
            sweep_high=sweep_high,
            sweep_low=sweep_low,
            reclaim_timestamp=signal_timestamp,
            breakout_level=sweep["swept_level"],
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _formed_pivot_count(self) -> int:
        bars = self.current_session_bars
        if len(bars) < 3:
            return 0
        count = 0
        for idx in range(1, len(bars) - 1):
            prev_bar = bars[idx - 1]
            center = bars[idx]
            next_bar = bars[idx + 1]
            prev_high = _finite_float(prev_bar.get("high"))
            high = _finite_float(center.get("high"))
            next_high = _finite_float(next_bar.get("high"))
            prev_low = _finite_float(prev_bar.get("low"))
            low = _finite_float(center.get("low"))
            next_low = _finite_float(next_bar.get("low"))
            if None not in {prev_high, high, next_high} and high > prev_high and high > next_high:
                count += 1
            if None not in {prev_low, low, next_low} and low < prev_low and low < next_low:
                count += 1
        return count

    def _sweep_status(
        self,
        bar: pd.Series,
        release_price: float,
        session_high: float,
        session_low: float,
    ) -> dict | None:
        prev_high = _finite_float(bar.get("prev_rth_high"))
        prev_low = _finite_float(bar.get("prev_rth_low"))
        swept_pdh = prev_high is not None and session_high > prev_high and release_price < prev_high
        swept_pdl = prev_low is not None and session_low < prev_low and release_price > prev_low
        if not swept_pdh and not swept_pdl:
            return None
        if swept_pdh and swept_pdl:
            reference = "previous_rth_high_and_low"
            swept_level = prev_high if abs(release_price - prev_high) <= abs(release_price - prev_low) else prev_low
        elif swept_pdh:
            reference = "previous_rth_high"
            swept_level = prev_high
        else:
            reference = "previous_rth_low"
            swept_level = prev_low
        return {
            "prev_rth_high": prev_high,
            "prev_rth_low": prev_low,
            "swept_pdh": swept_pdh,
            "swept_pdl": swept_pdl,
            "sweep_reference": reference,
            "swept_level": swept_level,
        }

    def _col(self, side: str, name: str) -> str:
        return f"{self.feature_prefix}_{side}_{name}"

    def _validate(self) -> None:
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be positive.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be positive.")
        if self.min_pivots < 0:
            raise ValueError("entry.params.min_pivots must be non-negative.")
        if self.min_range_pct < 0:
            raise ValueError("entry.params.min_range_pct must be non-negative.")
        if self.max_vap_distance_pct < 0:
            raise ValueError("entry.params.max_vap_distance_pct must be non-negative.")
        if self.min_absorption_delta <= 0:
            raise ValueError("entry.params.min_absorption_delta must be positive.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _truthy_number(value) -> bool:
    numeric = _finite_float(value)
    return numeric is not None and numeric > 0

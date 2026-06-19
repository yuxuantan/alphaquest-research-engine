from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OpeningDriveMesCrowdingReversalEntry:
    name = "opening_drive_mes_crowding_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", self.name))
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.opening_drive_minutes = int(params.get("opening_drive_minutes", 15))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.signal_start_time = parse_time(params.get("signal_start_time", "09:45:00"))
        self.last_entry_time = parse_time(params.get("last_entry_time", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.participation_window = int(params.get("participation_window", 15))
        self.rank_window = int(params.get("rank_window", 252))
        self.share_mode = str(params.get("share_mode", "notional")).lower()
        self.direction = str(params.get("direction", "both")).lower()
        self.share_rank_min = float(params.get("share_rank_min", 0.55))
        self.min_opening_drive_ticks = float(params.get("min_opening_drive_ticks", 4.0))
        self.min_extension_ticks = float(params.get("min_extension_ticks", 1.0))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0.0))
        self.max_opening_drive_pct_of_open = float(params.get("max_opening_drive_pct_of_open", 0.04))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)
        rth_start_ts = timestamp.replace(
            hour=self.rth_start.hour,
            minute=self.rth_start.minute,
            second=self.rth_start.second,
            microsecond=0,
        )
        drive_end = rth_start_ts + pd.Timedelta(minutes=self.opening_drive_minutes)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        if timestamp.time() >= self.rth_start and bar_close <= drive_end:
            state["drive_bars"].append(bar.copy())
            if bar_close >= drive_end:
                self._finalize_drive(state, drive_end)
            return None

        if not state.get("drive_finalized") and bar_close > drive_end:
            self._finalize_drive(state, drive_end)

        if trades_today >= self.max_trades_per_day or state["signaled"]:
            return None
        if not state.get("drive_finalized"):
            return None
        if bar_close.time() < self.signal_start_time or bar_close.time() > self.last_entry_time:
            return None

        drive = state.get("drive")
        if drive is None or abs(drive["drive_return_ticks"]) < self.min_opening_drive_ticks:
            return None
        if drive["width_pct_of_open"] > self.max_opening_drive_pct_of_open:
            return None

        metrics = self._participation_metrics(bar)
        if metrics is None or metrics["share_rank"] < self.share_rank_min:
            return None

        signal = self._extension_failure_signal(bar, timestamp, bar_close, drive, metrics)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _state(self, session_date) -> dict:
        state = self.state_by_day.get(session_date)
        if state is None:
            state = {"drive_bars": [], "drive_finalized": False, "drive": None, "signaled": False}
            self.state_by_day[session_date] = state
        return state

    def _finalize_drive(self, state: dict, drive_end: pd.Timestamp) -> None:
        if state.get("drive_finalized"):
            return
        bars = state.get("drive_bars") or []
        if not bars:
            return
        open_price = _finite_float(bars[0].get("open"))
        close_price = _finite_float(bars[-1].get("close"))
        highs = [_finite_float(bar.get("high")) for bar in bars]
        lows = [_finite_float(bar.get("low")) for bar in bars]
        if open_price is None or close_price is None or any(v is None for v in highs + lows):
            return
        high = max(float(v) for v in highs if v is not None)
        low = min(float(v) for v in lows if v is not None)
        if open_price <= 0 or high < low:
            return
        state["drive"] = {
            "opening_drive_start": pd.Timestamp(bars[0]["timestamp"]),
            "opening_drive_end": drive_end,
            "opening_drive_open": open_price,
            "opening_drive_close": close_price,
            "opening_drive_high": high,
            "opening_drive_low": low,
            "opening_drive_width": high - low,
            "width_pct_of_open": (high - low) / open_price,
            "drive_return_ticks": (close_price - open_price) / self.tick_size,
        }
        state["drive_finalized"] = True

    def _participation_metrics(self, bar: pd.Series) -> dict[str, float] | None:
        suffix = str(self.participation_window)
        if self.share_mode == "trade":
            share_col = f"mes_trade_share_{suffix}"
            rank_col = f"mes_trade_share_{suffix}_rank{self.rank_window}"
        else:
            share_col = f"mes_participation_share_{suffix}"
            rank_col = f"mes_participation_share_{suffix}_rank{self.rank_window}"
        share_value = _finite_float(bar.get(share_col))
        share_rank = _finite_float(bar.get(rank_col))
        if share_value is None or share_rank is None:
            return None
        return {"share_value": share_value, "share_rank": share_rank}

    def _extension_failure_signal(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
        drive: dict,
        metrics: dict[str, float],
    ) -> Signal | None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if high is None or low is None or close is None:
            return None

        extension = self.min_extension_ticks * self.tick_size
        reclaim = self.reclaim_buffer_ticks * self.tick_size
        drive_direction = "up" if drive["drive_return_ticks"] > 0 else "down"

        direction = None
        breakout_level = None
        if (
            drive_direction == "up"
            and self.direction in {"short", "both"}
            and high >= drive["opening_drive_high"] + extension
            and close <= drive["opening_drive_high"] - reclaim
        ):
            direction = "short"
            breakout_level = drive["opening_drive_high"]
        elif (
            drive_direction == "down"
            and self.direction in {"long", "both"}
            and low <= drive["opening_drive_low"] - extension
            and close >= drive["opening_drive_low"] + reclaim
        ):
            direction = "long"
            breakout_level = drive["opening_drive_low"]

        if direction is None or breakout_level is None:
            return None

        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_opening_drive_extension_failure_with_mes_crowding",
            "share_mode": self.share_mode,
            "participation_window": self.participation_window,
            "rank_window": self.rank_window,
            "share_rank": metrics["share_rank"],
            "share_value": metrics["share_value"],
            "share_rank_min": self.share_rank_min,
            "opening_drive_minutes": self.opening_drive_minutes,
            "opening_drive_direction": drive_direction,
            "opening_drive_return_ticks": drive["drive_return_ticks"],
            "opening_drive_width": drive["opening_drive_width"],
            "opening_drive_width_pct_of_open": drive["width_pct_of_open"],
            "opening_drive_high": drive["opening_drive_high"],
            "opening_drive_low": drive["opening_drive_low"],
            "min_opening_drive_ticks": self.min_opening_drive_ticks,
            "min_extension_ticks": self.min_extension_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "breakout_level": breakout_level,
            "extension_bar_timestamp": timestamp,
            "signal_close_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "sweep_high": high,
            "sweep_low": low,
        }
        return Signal(
            direction=direction,
            level_type=f"opening_drive_mes_crowding_{self.setup_mode}",
            swept_level=float(breakout_level),
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            opening_range_high=drive["opening_drive_high"],
            opening_range_low=drive["opening_drive_low"],
            opening_range_open=drive["opening_drive_open"],
            opening_range_width=drive["opening_drive_width"],
            breakout_level=float(breakout_level),
            metadata={
                "setup_mode": self.setup_mode,
                "share_mode": self.share_mode,
                "participation_window": self.participation_window,
                "share_rank_min": self.share_rank_min,
                "min_opening_drive_ticks": self.min_opening_drive_ticks,
                "min_extension_ticks": self.min_extension_ticks,
                "opening_drive_return_ticks": drive["drive_return_ticks"],
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.opening_drive_minutes <= 0:
            raise ValueError("entry.params.opening_drive_minutes must be greater than 0.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.participation_window <= 0:
            raise ValueError("entry.params.participation_window must be greater than 0.")
        if self.rank_window <= 0:
            raise ValueError("entry.params.rank_window must be greater than 0.")
        if self.share_mode not in {"notional", "trade"}:
            raise ValueError("entry.params.share_mode must be notional or trade.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("entry.params.direction must be long, short, or both.")
        if not 0 <= self.share_rank_min <= 1:
            raise ValueError("entry.params.share_rank_min must be between 0 and 1.")
        if self.min_opening_drive_ticks < 0:
            raise ValueError("entry.params.min_opening_drive_ticks must be non-negative.")
        if self.min_extension_ticks < 0:
            raise ValueError("entry.params.min_extension_ticks must be non-negative.")
        if self.reclaim_buffer_ticks < 0:
            raise ValueError("entry.params.reclaim_buffer_ticks must be non-negative.")
        if self.max_opening_drive_pct_of_open <= 0:
            raise ValueError("entry.params.max_opening_drive_pct_of_open must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("entry.params.max_trades_per_day must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None

from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class MesParticipationCrowdingEntry:
    name = "mes_participation_crowding"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "mes_participation_crowding"))
        self.signal_mode = str(params.get("signal_mode", "fixed_time")).lower()
        self.entry_time = parse_time(params.get("entry_time", "10:30:00"))
        self.start_time = parse_time(params.get("start_time", params.get("entry_start_time", self.entry_time)))
        self.end_time = parse_time(params.get("end_time", params.get("last_entry_time", self.entry_time)))
        self.flatten_time = parse_time(params.get("flatten_time", "12:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_minutes = int(params.get("lookback_minutes", 30))
        self.rank_window = int(params.get("rank_window", 252))
        self.share_mode = str(params.get("share_mode", "notional")).lower()
        self.direction = str(params.get("direction", "both")).lower()
        self.share_rank_min = float(params.get("share_rank_min", 0.65))
        self.min_abs_return_ticks = float(params.get("min_abs_return_ticks", 4.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        self._validate()

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if self.signal_mode == "fixed_time":
            signal_timestamp = timestamp.replace(
                hour=self.entry_time.hour,
                minute=self.entry_time.minute,
                second=self.entry_time.second,
                microsecond=0,
            )
            if bar_close != signal_timestamp:
                return None
        elif self.signal_mode in {"first_signal_in_window", "first_in_window"}:
            if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
                return None
            signal_timestamp = bar_close
        else:
            raise ValueError("signal_mode must be fixed_time or first_signal_in_window.")

        metrics = self._metrics(bar)
        if metrics is None:
            return None
        if metrics["share_rank"] < self.share_rank_min:
            return None
        if abs(metrics["es_return_ticks"]) < self.min_abs_return_ticks:
            return None

        direction = self._direction(metrics["es_return_ticks"])
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_mes_participation_crowding",
            "signal_mode": self.signal_mode,
            "signal_window_start": self.start_time.strftime("%H:%M:%S"),
            "signal_window_end": self.end_time.strftime("%H:%M:%S"),
            "share_mode": self.share_mode,
            "lookback_minutes": self.lookback_minutes,
            "rank_window": self.rank_window,
            "configured_direction": self.direction,
            "share_rank": metrics["share_rank"],
            "share_value": metrics["share_value"],
            "es_return_ticks": metrics["es_return_ticks"],
            "share_rank_min": self.share_rank_min,
            "min_abs_return_ticks": self.min_abs_return_ticks,
            "crowding_signal_timestamp": signal_timestamp,
            "crowding_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }

        return Signal(
            direction=direction,
            level_type=f"mes_participation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "signal_mode": self.signal_mode,
                "signal_window_start": self.start_time.strftime("%H:%M:%S"),
                "signal_window_end": self.end_time.strftime("%H:%M:%S"),
                "share_mode": self.share_mode,
                "lookback_minutes": self.lookback_minutes,
                "rank_window": self.rank_window,
                "share_rank_min": self.share_rank_min,
                "min_abs_return_ticks": self.min_abs_return_ticks,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_minutes <= 0:
            raise ValueError("lookback_minutes must be greater than 0.")
        if self.signal_mode not in {"fixed_time", "first_signal_in_window", "first_in_window"}:
            raise ValueError("signal_mode must be fixed_time or first_signal_in_window.")
        if self.start_time > self.end_time:
            raise ValueError("start_time must be at or before end_time.")
        if self.rank_window <= 0:
            raise ValueError("rank_window must be greater than 0.")
        if self.share_mode not in {"notional", "trade"}:
            raise ValueError("share_mode must be notional or trade.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("direction must be long, short, or both.")
        if not 0 <= self.share_rank_min <= 1:
            raise ValueError("share_rank_min must be between 0 and 1.")
        if self.min_abs_return_ticks < 0:
            raise ValueError("min_abs_return_ticks must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")

    def _metrics(self, bar: pd.Series) -> dict[str, float] | None:
        suffix = str(self.lookback_minutes)
        if self.share_mode == "trade":
            share_col = f"mes_trade_share_{suffix}"
            rank_col = f"mes_trade_share_{suffix}_rank{self.rank_window}"
        else:
            share_col = f"mes_participation_share_{suffix}"
            rank_col = f"mes_participation_share_{suffix}_rank{self.rank_window}"
        return_col = f"es_return_ticks_{suffix}"
        share_rank = _finite_float(bar.get(rank_col))
        share_value = _finite_float(bar.get(share_col))
        es_return_ticks = _finite_float(bar.get(return_col))
        if None in {share_rank, share_value, es_return_ticks}:
            return None
        return {
            "share_rank": share_rank,
            "share_value": share_value,
            "es_return_ticks": es_return_ticks,
        }

    def _direction(self, es_return_ticks: float) -> str | None:
        if es_return_ticks <= -self.min_abs_return_ticks and self.direction in {"long", "both"}:
            return "long"
        if es_return_ticks >= self.min_abs_return_ticks and self.direction in {"short", "both"}:
            return "short"
        return None


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None

from __future__ import annotations

from collections import deque
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.target_rr import MIN_TARGET_R_MULTIPLE
from propstack.utils.time import parse_time


class IntradayInvarianceDislocationReversionEntry:
    name = "intraday_invariance_dislocation_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", self.name))
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.window_minutes = int(params.get("window_minutes", 30))
        self.same_clock_rank_window = int(params.get("same_clock_rank_window", 252))
        self.min_same_clock_observations = int(params.get("min_same_clock_observations", 60))
        self.invariance_rank_threshold = float(params.get("invariance_rank_threshold", 0.90))
        self.min_return_ticks = float(params.get("min_return_ticks", 6.0))
        self.max_aligned_flow_imbalance = float(params.get("max_aligned_flow_imbalance", 0.05))
        self.direction = str(params.get("direction", "both")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 2))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.current_session = None
        self.session_bars: list[dict] = []
        self.same_clock_scores: dict[str, deque[float]] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        self._roll_session(bar)
        self._append_bar(bar, bar_close)

        metrics = self._metrics()
        if metrics is None:
            return None

        clock_key = bar_close.strftime("%H:%M:%S")
        rank = self._same_clock_rank(clock_key, metrics["invariance_score"])
        self._append_same_clock_score(clock_key, metrics["invariance_score"])
        metrics["invariance_rank"] = rank

        if trades_today >= self.max_trades_per_day:
            return None
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None
        if rank is None or rank < self.invariance_rank_threshold:
            return None
        if abs(metrics["return_ticks"]) < self.min_return_ticks:
            return None

        direction = self._direction(metrics)
        if direction is None:
            return None
        return self._signal(bar, bar_close, direction, metrics)

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date != self.current_session:
            self.current_session = session_date
            self.session_bars = []

    def _append_bar(self, bar: pd.Series, bar_close: pd.Timestamp) -> None:
        item = {
            "timestamp": bar_close,
            "open": _finite_float(bar.get("open")),
            "high": _finite_float(bar.get("high")),
            "low": _finite_float(bar.get("low")),
            "close": _finite_float(bar.get("close")),
            "volume": _finite_float(bar.get("volume")),
            "signed_volume": _finite_float(bar.get("signed_volume")),
            "trades": _finite_float(bar.get("trades")),
        }
        required = {item["open"], item["high"], item["low"], item["close"], item["volume"], item["signed_volume"], item["trades"]}
        if None in required:
            return
        self.session_bars.append(item)
        self.session_bars = self.session_bars[-(self.window_minutes + 1) :]

    def _metrics(self) -> dict[str, float] | None:
        if len(self.session_bars) < self.window_minutes + 1:
            return None
        window = self.session_bars[-self.window_minutes :]
        start_close = self.session_bars[-(self.window_minutes + 1)]["close"]
        current = self.session_bars[-1]
        return_ticks = (current["close"] - start_close) / self.tick_size
        volume = sum(item["volume"] for item in window)
        signed_volume = sum(item["signed_volume"] for item in window)
        trades = sum(item["trades"] for item in window)
        if volume <= 0 or trades <= 0:
            return None
        avg_trade_size = volume / trades
        flow_imbalance = signed_volume / volume

        raw_score = ((abs(return_ticks) ** 2) / trades) * (avg_trade_size**2)
        if not all(math.isfinite(value) for value in [return_ticks, avg_trade_size, flow_imbalance, raw_score]):
            return None
        return {
            "return_ticks": return_ticks,
            "volume": volume,
            "signed_volume": signed_volume,
            "trades": trades,
            "avg_trade_size": avg_trade_size,
            "flow_imbalance": flow_imbalance,
            "invariance_score": math.log1p(raw_score),
            "current_close": current["close"],
        }

    def _same_clock_rank(self, clock_key: str, score: float) -> float | None:
        history = self.same_clock_scores.get(clock_key)
        if history is None or len(history) < self.min_same_clock_observations:
            return None
        values = [value for value in history if math.isfinite(value)]
        if len(values) < self.min_same_clock_observations:
            return None
        below_or_equal = sum(1 for value in values if value <= score)
        return below_or_equal / len(values)

    def _append_same_clock_score(self, clock_key: str, score: float) -> None:
        history = self.same_clock_scores.get(clock_key)
        if history is None:
            history = deque(maxlen=self.same_clock_rank_window)
            self.same_clock_scores[clock_key] = history
        if math.isfinite(score):
            history.append(score)

    def _direction(self, metrics: dict[str, float]) -> str | None:
        return_ticks = metrics["return_ticks"]
        flow_imbalance = metrics["flow_imbalance"]
        if return_ticks >= self.min_return_ticks and flow_imbalance <= self.max_aligned_flow_imbalance:
            return "short" if self.direction in {"short", "both"} else None
        if return_ticks <= -self.min_return_ticks and flow_imbalance >= -self.max_aligned_flow_imbalance:
            return "long" if self.direction in {"long", "both"} else None
        return None

    def _signal(
        self,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        direction: str,
        metrics: dict[str, float],
    ) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        current_close = float(bar["close"])
        flatten_label = self.flatten_time.strftime("%H:%M:%S")
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_intraday_trading_invariance_dislocation",
            "window_minutes": self.window_minutes,
            "same_clock_rank_window": self.same_clock_rank_window,
            "min_same_clock_observations": self.min_same_clock_observations,
            "invariance_score": metrics["invariance_score"],
            "invariance_rank": metrics["invariance_rank"],
            "invariance_rank_threshold": self.invariance_rank_threshold,
            "return_ticks": metrics["return_ticks"],
            "min_return_ticks": self.min_return_ticks,
            "volume": metrics["volume"],
            "signed_volume": metrics["signed_volume"],
            "trades": metrics["trades"],
            "avg_trade_size": metrics["avg_trade_size"],
            "flow_imbalance": metrics["flow_imbalance"],
            "max_aligned_flow_imbalance": self.max_aligned_flow_imbalance,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": flatten_label,
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"invariance_dislocation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "window_minutes": self.window_minutes,
                "invariance_rank": metrics["invariance_rank"],
                "invariance_score": metrics["invariance_score"],
                "return_ticks": metrics["return_ticks"],
                "flow_imbalance": metrics["flow_imbalance"],
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.end_time < self.start_time:
            raise ValueError("entry.params.end_time must be at or after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.window_minutes <= 1:
            raise ValueError("entry.params.window_minutes must be greater than 1.")
        if self.same_clock_rank_window <= 0 or self.min_same_clock_observations <= 0:
            raise ValueError("same-clock rank window and minimum observations must be positive.")
        if self.min_same_clock_observations > self.same_clock_rank_window:
            raise ValueError("min_same_clock_observations cannot exceed same_clock_rank_window.")
        if not 0 <= self.invariance_rank_threshold <= 1:
            raise ValueError("entry.params.invariance_rank_threshold must be in [0, 1].")
        if self.min_return_ticks < 0:
            raise ValueError("entry.params.min_return_ticks must be non-negative.")
        if self.max_aligned_flow_imbalance < 0:
            raise ValueError("entry.params.max_aligned_flow_imbalance must be non-negative.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("entry.params.direction must be long, short, or both.")
        if self.max_trades_per_day <= 0:
            raise ValueError("entry.params.max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0:
            raise ValueError("entry.params.stop_pct must be greater than 0.")
        if self.target_r_multiple < MIN_TARGET_R_MULTIPLE:
            raise ValueError(f"entry.params.target_r_multiple must be >= {MIN_TARGET_R_MULTIPLE:.1f}.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None

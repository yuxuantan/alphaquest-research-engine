from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class DailyTimeSeriesMomentumEntry:
    name = "daily_time_series_momentum"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "close_to_close_trend")).lower()
        self.rth_end = parse_time(params.get("rth_end", "16:00:00"))
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_sessions = int(params.get("lookback_sessions", 20))
        self.confirmation_sessions = int(params.get("confirmation_sessions", 1))
        self.min_abs_trend_return_pct = float(params.get("min_abs_trend_return_pct", 0.0))
        self.min_trend_zscore = float(params.get("min_trend_zscore", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.history: list[dict] = []
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "recorded_close": False,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar["session_date"])

        signal = None
        if not state["signaled"] and trades_today < self.max_trades_per_day and bar_close.time() == self.signal_time:
            signal = self._signal(bar, bar_close)
            if signal is not None:
                state["signaled"] = True

        if not state["recorded_close"] and bar_close.time() >= self.rth_end:
            self.history.append(
                {
                    "session_date": bar["session_date"],
                    "timestamp": bar_close,
                    "close": float(bar["close"]),
                }
            )
            state["recorded_close"] = True
        return signal

    def _signal(self, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal | None:
        if self.lookback_sessions <= 1 or len(self.history) < self.lookback_sessions:
            return None

        recent = self.history[-1]
        anchor = self.history[-self.lookback_sessions]
        recent_close = float(recent["close"])
        anchor_close = float(anchor["close"])
        if anchor_close <= 0:
            return None

        trend_return_pct = recent_close / anchor_close - 1.0
        if abs(trend_return_pct) < self.min_abs_trend_return_pct:
            return None

        direction = "long" if trend_return_pct > 0 else "short" if trend_return_pct < 0 else None
        if direction is None:
            return None
        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None

        trend_zscore = None
        if self.setup_mode == "volatility_normalized_trend":
            trend_zscore = self._trend_zscore()
            if trend_zscore is None or abs(trend_zscore) < self.min_trend_zscore:
                return None
            if (trend_zscore > 0 and direction != "long") or (trend_zscore < 0 and direction != "short"):
                return None

        confirmation_return_pct = None
        if self.setup_mode == "short_term_alignment":
            if len(self.history) < self.confirmation_sessions + 1:
                return None
            confirm_anchor = self.history[-(self.confirmation_sessions + 1)]
            confirm_anchor_close = float(confirm_anchor["close"])
            if confirm_anchor_close <= 0:
                return None
            confirmation_return_pct = recent_close / confirm_anchor_close - 1.0
            if (confirmation_return_pct > 0 and direction != "long") or (
                confirmation_return_pct < 0 and direction != "short"
            ):
                return None
            if confirmation_return_pct == 0:
                return None

        report_fields = {
            "academic_source_key": "moskowitz_ooi_pedersen_2012_time_series_momentum",
            "setup_mode": self.setup_mode,
            "signal_timestamp": signal_timestamp,
            "trend_anchor_session_date": anchor["session_date"],
            "trend_anchor_close": anchor_close,
            "trend_recent_session_date": recent["session_date"],
            "trend_recent_close": recent_close,
            "trend_return_pct": trend_return_pct,
            "trend_zscore": trend_zscore,
            "confirmation_return_pct": confirmation_return_pct,
            "lookback_sessions": self.lookback_sessions,
            "confirmation_sessions": self.confirmation_sessions,
            "min_abs_trend_return_pct": self.min_abs_trend_return_pct,
            "min_trend_zscore": self.min_trend_zscore,
        }
        return Signal(
            direction=direction,
            level_type=f"daily_time_series_momentum_{self.setup_mode}",
            swept_level=anchor_close,
            sweep_timestamp=anchor["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "trend_return_pct": trend_return_pct,
                "trend_zscore": trend_zscore,
                "setup_mode": self.setup_mode,
            },
            report_fields=report_fields,
        )

    def _trend_zscore(self) -> float | None:
        if len(self.history) < self.lookback_sessions:
            return None
        closes = [float(item["close"]) for item in self.history[-self.lookback_sessions :]]
        returns = []
        for prior, current in zip(closes, closes[1:]):
            if prior <= 0:
                return None
            returns.append(current / prior - 1.0)
        if not returns:
            return None
        volatility = pd.Series(returns).std(ddof=0)
        if volatility is None or pd.isna(volatility) or not math.isfinite(float(volatility)) or volatility <= 0:
            return None
        return sum(returns) / (float(volatility) * math.sqrt(len(returns)))

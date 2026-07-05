from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TurnaroundTuesdayReversalEntry:
    name = "turnaround_tuesday_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "prior_loss_reversal")).lower()
        self.direction_mode = str(params.get("direction_mode", "loss_long")).lower()
        self.signal_time = parse_time(params.get("signal_time", "10:00:00"))
        self.rth_end = parse_time(params.get("rth_end", "16:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.lookback_sessions = int(params.get("lookback_sessions", 1))
        self.min_abs_reversal_return_pct = float(params.get("min_abs_reversal_return_pct", 0.005))
        self.min_reversal_zscore = float(params.get("min_reversal_zscore", 0.0))
        self.signal_weekday = int(params.get("signal_weekday", 1))
        self.require_recent_weekday = params.get("require_recent_weekday", 0)
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.history: list[dict] = []
        self.state_by_day: dict = {}
        self._validate()

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False, "recorded_close": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        session_date = bar["session_date"]
        state = self._state(session_date)

        signal = None
        if (
            not state["signaled"]
            and trades_today < self.max_trades_per_day
            and bar_close.time() == self.signal_time
        ):
            signal = self._signal(bar, bar_close)
            if signal is not None:
                state["signaled"] = True

        if not state["recorded_close"] and bar_close.time() >= self.rth_end:
            self.history.append(
                {
                    "session_date": session_date,
                    "timestamp": bar_close,
                    "weekday": int(timestamp.weekday()),
                    "close": float(bar["close"]),
                }
            )
            state["recorded_close"] = True
        return signal

    def _signal(self, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal | None:
        signal_weekday = int(pd.Timestamp(bar["timestamp"]).weekday())
        if signal_weekday != self.signal_weekday:
            return None
        if self.lookback_sessions < 1 or len(self.history) < self.lookback_sessions + 1:
            return None

        recent = self.history[-1]
        if self.require_recent_weekday is not None and int(recent["weekday"]) != int(self.require_recent_weekday):
            return None

        anchor = self.history[-(self.lookback_sessions + 1)]
        recent_close = float(recent["close"])
        anchor_close = float(anchor["close"])
        if anchor_close <= 0:
            return None

        reversal_return_pct = recent_close / anchor_close - 1.0
        if abs(reversal_return_pct) < self.min_abs_reversal_return_pct:
            return None

        direction = self._direction_from_return(reversal_return_pct)
        if direction is None:
            return None

        reversal_zscore = None
        if self.setup_mode == "volatility_normalized_reversal":
            reversal_zscore = self._reversal_zscore()
            if reversal_zscore is None or abs(reversal_zscore) < self.min_reversal_zscore:
                return None
            if (reversal_zscore > 0 and direction != "short") or (
                reversal_zscore < 0 and direction != "long"
            ):
                return None

        report_fields = {
            "academic_source_key": "turnaround_tuesday_weekday_short_term_reversal",
            "setup_mode": self.setup_mode,
            "direction_mode": self.direction_mode,
            "signal_timestamp": signal_timestamp,
            "signal_weekday": signal_weekday,
            "required_signal_weekday": self.signal_weekday,
            "required_recent_weekday": self.require_recent_weekday,
            "reversal_anchor_session_date": anchor["session_date"],
            "reversal_anchor_close": anchor_close,
            "reversal_recent_session_date": recent["session_date"],
            "reversal_recent_weekday": recent["weekday"],
            "reversal_recent_close": recent_close,
            "reversal_return_pct": reversal_return_pct,
            "reversal_zscore": reversal_zscore,
            "lookback_sessions": self.lookback_sessions,
            "min_abs_reversal_return_pct": self.min_abs_reversal_return_pct,
            "min_reversal_zscore": self.min_reversal_zscore,
            "availability_rule": "uses only completed prior RTH closes before the Tuesday signal session",
        }
        return Signal(
            direction=direction,
            level_type=f"turnaround_tuesday_{self.setup_mode}_{direction}",
            swept_level=recent_close,
            sweep_timestamp=recent["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "reversal_return_pct": reversal_return_pct,
                "reversal_zscore": reversal_zscore,
                "setup_mode": self.setup_mode,
                "direction_mode": self.direction_mode,
            },
            report_fields=report_fields,
        )

    def _direction_from_return(self, reversal_return_pct: float) -> str | None:
        if reversal_return_pct > 0:
            contrarian = "short"
        elif reversal_return_pct < 0:
            contrarian = "long"
        else:
            return None

        if self.direction_mode == "two_sided":
            return contrarian
        if self.direction_mode == "loss_long":
            return "long" if contrarian == "long" else None
        if self.direction_mode == "gain_short":
            return "short" if contrarian == "short" else None
        raise ValueError("direction_mode must be one of two_sided, loss_long, gain_short.")

    def _reversal_zscore(self) -> float | None:
        if len(self.history) < self.lookback_sessions + 1:
            return None
        closes = [float(item["close"]) for item in self.history[-(self.lookback_sessions + 1) :]]
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

    def _validate(self) -> None:
        if self.setup_mode not in {"prior_loss_reversal", "volatility_normalized_reversal"}:
            raise ValueError("setup_mode must be prior_loss_reversal or volatility_normalized_reversal.")
        if self.direction_mode not in {"two_sided", "loss_long", "gain_short"}:
            raise ValueError("direction_mode must be one of two_sided, loss_long, gain_short.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_sessions < 1:
            raise ValueError("lookback_sessions must be at least 1.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if not 0 <= self.signal_weekday <= 4:
            raise ValueError("signal_weekday must be Monday=0 through Friday=4.")
        if self.require_recent_weekday is not None:
            self.require_recent_weekday = int(self.require_recent_weekday)
            if not 0 <= self.require_recent_weekday <= 4:
                raise ValueError("require_recent_weekday must be Monday=0 through Friday=4.")
        if self.min_abs_reversal_return_pct < 0 or self.min_reversal_zscore < 0:
            raise ValueError("minimum reversal thresholds must be non-negative.")

from __future__ import annotations

from pathlib import Path
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.cftc_tff_hedging_pressure import _load_feature_by_date
from propstack.utils.time import parse_time


class CftcTffTieredHedgingPressureEntry:
    name = "cftc_tff_tiered_hedging_pressure"

    def __init__(self, params: dict):
        self.params = params
        self.feature_file = Path(params.get("feature_file", "data/external/cftc_tff_hedging_pressure_features.csv"))
        self.feature_name = str(params.get("feature_name", "SPX_open_interest_chg13"))
        self.direction = str(params.get("direction", "long")).lower()
        self.high_threshold = float(params.get("high_threshold", 98748.0))
        self.broad_threshold = float(params.get("broad_threshold", 47442.0))
        self.high_entry_time = parse_time(params.get("high_entry_time", "09:35:00"))
        self.broad_entry_time = parse_time(params.get("broad_entry_time", "11:00:00"))
        self.high_stop_pct = float(params.get("high_stop_pct", 0.008))
        self.broad_stop_pct = float(params.get("broad_stop_pct", 0.006))
        self.high_target_r_multiple = float(params.get("high_target_r_multiple", 2.0))
        self.broad_target_r_multiple = float(params.get("broad_target_r_multiple", 4.0))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict[pd.Timestamp, dict] = {}
        self.feature_by_date = _load_feature_by_date(self.feature_file, self.feature_name)
        if self.direction not in {"long", "short"}:
            raise ValueError("cftc_tff_tiered_hedging_pressure direction must be long or short.")
        if min(self.high_stop_pct, self.broad_stop_pct) <= 0:
            raise ValueError("CFTC tiered stop percentages must be greater than 0.")
        if min(self.high_target_r_multiple, self.broad_target_r_multiple) <= 0:
            raise ValueError("CFTC tiered target multiples must be greater than 0.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")

    def _state(self, session_date: pd.Timestamp) -> dict:
        return self.state_by_day.setdefault(session_date, self._initial_state(session_date))

    def _initial_state(self, session_date: pd.Timestamp) -> dict:
        feature_value = self.feature_by_date.get(session_date)
        selected_tier = None
        if feature_value is not None and math.isfinite(feature_value):
            if feature_value >= self.high_threshold:
                selected_tier = "high"
            elif feature_value >= self.broad_threshold:
                selected_tier = "broad"
        return {
            "signaled": False,
            "selected_tier": selected_tier,
            "feature_value": feature_value,
        }

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = pd.Timestamp(bar["session_date"]).normalize()
        state = self._state(session_date)
        if state["signaled"] or state["selected_tier"] is None:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        selected_tier = str(state["selected_tier"])
        entry_time = self.high_entry_time if selected_tier == "high" else self.broad_entry_time
        if bar_close.time() != entry_time:
            return None

        state["signaled"] = True
        feature_value = float(state["feature_value"])
        stop_pct = self.high_stop_pct if selected_tier == "high" else self.broad_stop_pct
        target_r = self.high_target_r_multiple if selected_tier == "high" else self.broad_target_r_multiple
        threshold = self.high_threshold if selected_tier == "high" else self.broad_threshold
        report_fields = {
            "academic_source_key": "de_roon_nijman_veld_2000_hedging_pressure",
            "external_dataset": "cftc_tff_financial_futures_combined",
            "external_feature_file": str(self.feature_file),
            "feature_name": self.feature_name,
            "feature_operator": ">=",
            "feature_threshold": threshold,
            "feature_value": feature_value,
            "feature_trade_date": session_date.date().isoformat(),
            "feature_availability_rule": "Tuesday CFTC TFF positions traded no earlier than following Monday RTH",
            "selected_tier": selected_tier,
            "high_threshold": self.high_threshold,
            "broad_threshold": self.broad_threshold,
            "signal_stop_pct": stop_pct,
            "signal_target_r_multiple": target_r,
            "signal_timestamp": bar_close,
        }
        return Signal(
            direction=self.direction,
            level_type=f"cftc_tff_tiered_{selected_tier}_{self.feature_name}",
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
                "selected_tier": selected_tier,
                "stop_pct": stop_pct,
                "target_r_multiple": target_r,
            },
            report_fields=report_fields,
        )

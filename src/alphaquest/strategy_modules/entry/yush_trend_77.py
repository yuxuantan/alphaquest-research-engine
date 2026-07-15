from __future__ import annotations

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_trend_74 import YushTrend74Entry


class YushTrend77Entry(YushTrend74Entry):
    name = "yush_trend_77"

    _LONG_EDGE_LEVELS = {"PDH", "ONH", "ORH"}
    _SHORT_EDGE_LEVELS = {"PDL", "ONL", "ORL"}

    def _update_breakout_state(self, direction: str, level: dict, tick_state: dict) -> dict | None:
        if not self._level_direction_allowed(direction, str(level["type"])):
            return None
        return super()._update_breakout_state(direction, level, tick_state)

    def _level_direction_allowed(self, direction: str, level_type: str) -> bool:
        if direction == "long":
            return level_type in self._LONG_EDGE_LEVELS
        if direction == "short":
            return level_type in self._SHORT_EDGE_LEVELS
        return False

    def _signal_for_breakout(
        self,
        *,
        direction: str,
        bar,
        tick_state: dict,
        pending: dict,
        confirmation: dict,
        risk_points: float,
    ) -> Signal:
        signal = super()._signal_for_breakout(
            direction=direction,
            bar=bar,
            tick_state=tick_state,
            pending=pending,
            confirmation=confirmation,
            risk_points=risk_points,
        )
        fields = {
            "directional_level_filter": "outside_public_edge_only",
            "long_allowed_level_types": ",".join(sorted(self._LONG_EDGE_LEVELS)),
            "short_allowed_level_types": ",".join(sorted(self._SHORT_EDGE_LEVELS)),
        }
        signal.metadata.update(fields)
        signal.report_fields.update(fields)
        return signal

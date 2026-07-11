from __future__ import annotations

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.yush_trend_74 import YushTrend74Entry


class YushTrend76Entry(YushTrend74Entry):
    name = "yush_trend_76"

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
        if self._opening_range_high is None or self._opening_range_low is None:
            return signal
        width = float(self._opening_range_high) - float(self._opening_range_low)
        fields = {
            "opening_range_high": float(self._opening_range_high),
            "opening_range_low": float(self._opening_range_low),
            "opening_range_width": float(width),
            "opening_range_seconds": self.opening_range_seconds,
            "target_reference": "opening_range_extension",
            "stop_reference": "opening_range_retest_boundary",
        }
        signal.opening_range_high = fields["opening_range_high"]
        signal.opening_range_low = fields["opening_range_low"]
        signal.opening_range_width = fields["opening_range_width"]
        signal.metadata.update(fields)
        signal.report_fields.update(fields)
        return signal

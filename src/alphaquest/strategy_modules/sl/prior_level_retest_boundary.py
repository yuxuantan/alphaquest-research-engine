from __future__ import annotations

from alphaquest.strategy_modules.sl.opening_range_retest_boundary import (
    opening_range_retest_boundary_stop,
)


class PriorLevelRetestBoundaryStop:
    name = "prior_level_retest_boundary"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        return opening_range_retest_boundary_stop(
            signal,
            direction,
            tick_size,
            self.params.get("max_stop_points", 14.0),
            entry_price,
            int(self.params.get("stop_offset_ticks", 4)),
        )

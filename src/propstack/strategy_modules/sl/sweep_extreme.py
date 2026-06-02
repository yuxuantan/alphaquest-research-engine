from __future__ import annotations


def sweep_stop(signal, direction: str, tick_size: float, stop_offset_ticks: int) -> float:
    offset = tick_size * stop_offset_ticks
    if direction == "long":
        return signal.sweep_low - offset
    return signal.sweep_high + offset


class SweepExtremeStop:
    name = "sweep_extreme"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float:
        return sweep_stop(
            signal,
            direction,
            tick_size,
            int(self.params.get("stop_offset_ticks", 1)),
        )

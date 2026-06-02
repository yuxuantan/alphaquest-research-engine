from __future__ import annotations


def opening_range_edge_stop(
    signal,
    direction: str,
    tick_size: float,
    max_stop_points: float | None = 14.0,
    entry_price: float | None = None,
    stop_offset_ticks: int = 0,
) -> float:
    offset = tick_size * stop_offset_ticks
    if direction == "long":
        natural_stop = _signal_value(signal, "opening_range_low", "sweep_low") - offset
        if entry_price is not None and max_stop_points is not None:
            return max(natural_stop, float(entry_price) - float(max_stop_points))
        return natural_stop

    natural_stop = _signal_value(signal, "opening_range_high", "sweep_high") + offset
    if entry_price is not None and max_stop_points is not None:
        return min(natural_stop, float(entry_price) + float(max_stop_points))
    return natural_stop


class OpeningRangeEdgeStop:
    name = "opening_range_edge"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float:
        return opening_range_edge_stop(
            signal,
            direction,
            tick_size,
            self.params.get("max_stop_points", 14.0),
            entry_price,
            int(self.params.get("stop_offset_ticks", 0)),
        )


def _signal_value(signal, primary: str, fallback: str) -> float:
    value = getattr(signal, primary, None)
    if value is None:
        value = getattr(signal, fallback)
    return float(value)

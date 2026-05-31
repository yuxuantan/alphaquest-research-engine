from __future__ import annotations


def sweep_stop(signal, direction: str, tick_size: float, stop_offset_ticks: int) -> float:
    offset = tick_size * stop_offset_ticks
    if direction == "long":
        return signal.sweep_low - offset
    return signal.sweep_high + offset

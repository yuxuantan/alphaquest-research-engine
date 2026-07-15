from __future__ import annotations

from datetime import time


def parse_time(value: str | time) -> time:
    if isinstance(value, time):
        return value
    parts = [int(x) for x in value.split(":")]
    if len(parts) == 2:
        return time(parts[0], parts[1])
    return time(parts[0], parts[1], parts[2])

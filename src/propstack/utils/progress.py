from __future__ import annotations

import sys
import time
from collections.abc import Callable


class ProgressBar:
    def __init__(
        self,
        total: int,
        label: str,
        width: int = 28,
        enabled: bool = True,
        show_timing: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.total = max(int(total), 0)
        self.label = label
        self.width = width
        self.enabled = enabled and self.total > 0
        self.show_timing = show_timing
        self.clock = clock
        self.started_at = self.clock()
        self.last_percent = -1
        self.last_line_length = 0

    def update(self, current: int, force: bool = False) -> None:
        if not self.enabled:
            return
        current = min(max(int(current), 0), self.total)
        percent = int((current / self.total) * 100)
        if not force and percent == self.last_percent and current != self.total:
            return
        self.last_percent = percent
        filled = int(self.width * current / self.total)
        bar = "#" * filled + "-" * (self.width - filled)
        line = f"{self.label} [{bar}] {current}/{self.total} {percent:3d}%"
        if self.show_timing:
            line = f"{line} | {_timing_text(self.clock() - self.started_at, current, self.total)}"
        padding = " " * max(0, self.last_line_length - len(line))
        self.last_line_length = len(line)
        sys.stdout.write(f"\r{line}{padding}")
        sys.stdout.flush()
        if current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()


def progress_bar(
    total: int,
    label: str,
    enabled: bool = True,
    show_timing: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> ProgressBar:
    return ProgressBar(total=total, label=label, enabled=enabled, show_timing=show_timing, clock=clock)


def _timing_text(elapsed_seconds: float, current: int, total: int) -> str:
    if current <= 0:
        remaining = "--"
    else:
        seconds_per_item = elapsed_seconds / current
        remaining = _format_duration(seconds_per_item * max(total - current, 0))
    return f"elapsed {_format_duration(elapsed_seconds)} | remaining {remaining}"


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

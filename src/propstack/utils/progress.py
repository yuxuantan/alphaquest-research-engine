from __future__ import annotations

import sys


class ProgressBar:
    def __init__(self, total: int, label: str, width: int = 28, enabled: bool = True):
        self.total = max(int(total), 0)
        self.label = label
        self.width = width
        self.enabled = enabled and self.total > 0
        self.last_percent = -1

    def update(self, current: int) -> None:
        if not self.enabled:
            return
        current = min(max(int(current), 0), self.total)
        percent = int((current / self.total) * 100)
        if percent == self.last_percent and current != self.total:
            return
        self.last_percent = percent
        filled = int(self.width * current / self.total)
        bar = "#" * filled + "-" * (self.width - filled)
        sys.stdout.write(f"\r{self.label} [{bar}] {current}/{self.total} {percent:3d}%")
        sys.stdout.flush()
        if current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()


def progress_bar(total: int, label: str, enabled: bool = True) -> ProgressBar:
    return ProgressBar(total=total, label=label, enabled=enabled)

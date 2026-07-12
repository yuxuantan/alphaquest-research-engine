"""Compatibility entry point for the packaged preflight implementation."""

from __future__ import annotations

import sys

from propstack.research import preflight as _implementation


if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation

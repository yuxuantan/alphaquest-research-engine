#!/usr/bin/env python3
"""
Compatibility wrapper for the Databento signal engine.

The old strategy execution bridge routed IBKR data through Apex/Tradovate
plumbing. Execution is now alert-only and Databento-backed; keep this filename
so existing commands can move to the new engine without relearning the entry
point.
"""

from databento_signal_engine import run


if __name__ == "__main__":
    raise SystemExit(run())

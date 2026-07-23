"""Deprecated imports for the pre-reset Yush prototype.

The implementation now lives with strategy modules.  Campaign execution must
use the registered canonical event lane rather than a strategy-specific runner.
"""

from alphaquest.strategy_modules.event.yush_orderflow_primitives import *  # noqa: F401,F403

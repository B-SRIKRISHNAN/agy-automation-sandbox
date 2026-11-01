"""Sandbox facade for agy-automation.

Re-exports sandbox lifecycle and runner from agy_automation.core.sandbox for backward compatibility.
"""

import sys
from .core import sandbox as _sandbox
from .core.sandbox import *  # noqa: F401, F403

sys.modules[__name__] = _sandbox

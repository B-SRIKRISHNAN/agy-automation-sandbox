"""Cleanup facade for agy-automation.

Re-exports cleanup functionality from agy_automation.core.cleanup for backward compatibility.
"""

import sys
from .core import cleanup as _cleanup
from .core.cleanup import *  # noqa: F401, F403

sys.modules[__name__] = _cleanup

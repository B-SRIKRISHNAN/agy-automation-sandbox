"""Configuration facade for agy-automation.

Re-exports configuration functionality from agy_automation.core.config for backward compatibility.
"""

import sys
from .core import config as _config
from .core.config import *  # noqa: F401, F403

sys.modules[__name__] = _config

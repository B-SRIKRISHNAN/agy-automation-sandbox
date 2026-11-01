"""Engine detection facade for agy-automation.

Re-exports engine detection and resolution from agy_automation.core.engine.
"""

import sys
from .core import engine as _engine
from .core.engine import *  # noqa: F401, F403

sys.modules[__name__] = _engine

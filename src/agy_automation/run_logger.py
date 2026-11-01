"""Run logging facade for agy-automation.

Re-exports logging and telemetry from agy_automation.core.logging for backward compatibility.
"""

import sys
from .core import logging as _logging
from .core.logging import *  # noqa: F401, F403

sys.modules[__name__] = _logging

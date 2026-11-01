"""Orchestrator facade for agy-automation.

Re-exports pipeline coordination from agy_automation.core.orchestrator for backward compatibility.
"""

import sys
from .core import orchestrator as _orchestrator
from .core.orchestrator import *  # noqa: F401, F403

sys.modules[__name__] = _orchestrator
